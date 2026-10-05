"""IA por resposta: quem passa pela IA, a fila (`ia_situacao = pendente`), o processamento e a configuração da conta.

Quem passa: resposta de origem `pesquisa` ou `manual` com texto do cliente de 3 letras ou mais, numa conta com
`ia_analise_respostas` ligado e liberada (assinatura em dia, `assinatura.regras.liberada`), com a IA disponível. Ao
gravar (ponto único `ao_registrar_resposta`), essas ficam `pendente`; quem grava envolve o trabalho em `coletar_analises()` e agenda
`analisar(pares)` depois do commit (sem coletor, fica para a tarefa `ia`). As importadas ficam de fora, salvo por
"Analisar comentários dos últimos 90 dias".

Cada resposta: (1) reserva numa transação curta (`ia_reservada_em`, só se pendente e sem reserva nos últimos 5
minutos) e consome o teto do mês (`ia_uso_mensal`, atualização condicional; sem saldo → `limite`); (2) chama a IA
fora da transação; (3) grava numa transação nova só se o texto enviado ainda é o atual (mesmo hash). Falha (inclusive
o banco recusar o resultado) devolve o saldo e limpa a reserva; a transitória soma uma tentativa e, na 3ª, vira
`falhou`; a de configuração para a rodada e não conta tentativa quando é chave ou modelo (401/403/404). O mês do
teto é o de São Paulo.

`ia_reservada_em` preenchido = há um consumo do teto ainda não devolvido para a resposta, e o valor é a marca de
quem reservou: só quem tem a marca devolve o saldo e solta a reserva (outros fluxos, como desligar a IA ou editar o
comentário, não mexem nela). Uma reserva vencida (processo derrubado no meio, ex.: deploy durante a tarefa) já
consumiu o teto e nunca devolveu: quem a assume não consome de novo (herda o consumo e o mês dele).

Logo depois de gravar (`analisar`), no máximo 4 análises ao mesmo tempo por processo, sem esperar vaga (sem vaga, a
resposta fica para a tarefa `ia`) e com tempo limite de 15 s, para não segurar as threads da API; a tarefa usa 30 s.

A análise de cada resposta não gasta a cota de IA do plano (etapa 5): só o teto de segurança mensal abaixo. A cota
do plano (`ia.cota`, gasta pelo assistente, pelo resumo do painel e pelo parecer dos relatórios) aparece em
Configurações › IA (`cota`).

Configurações › IA (etapa 5d): o estado ganha o nível do modelo e o estilo da conta (com as opções e os textos de
`ia_texto`; cada nível em `modelos` traz também `analises`, o que uma geração ou pergunta gasta da cota) e o
interruptor dos passos das ações. O PUT é parcial (só os campos enviados mudam); desligar a análise
cancela as respostas pendentes e desligar os passos cancela as ações pendentes; a auditoria `config_ia` leva só os
campos que mudaram (nada mudou, nada vai).

Etapa 5h (IA nos importados): "analisar os últimos 90 dias" tem um núcleo sem erros (`marcar_recentes`, a mesma regra
e o mesmo saldo), usado também ao concluir a importação de respostas (`marcar_importadas`: só as importadas agora, e só
com a IA ativa na conta). Depois do commit, `processar_conta` analisa a fila daquela conta já (até 100 análises ou
120 s, no máximo 4 ao mesmo tempo no processo, cada uma por `processar`); o resto fica para a tarefa `ia`.
"""
import logging
import threading
import time as relogio_real
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import BigInteger, any_, bindparam, func, or_, select, update
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.orm import Session

from toqqi.core import ia, ia_texto, relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.core.filtros import inicio_do_dia
from toqqi.core.log_seguro import descrever_erro
from toqqi.modelos import Acao, Conta, Formulario, IaUsoMensal, Resposta
from toqqi.modulos.assinatura.regras import liberada
from toqqi.modulos.ia import cota
from toqqi.modulos.ia.regras import MIN_LETRAS, ia_ativa, passa_pela_ia, teto_mensal, texto_qualifica
from toqqi.modulos.respostas import temas as temas_mod
from toqqi.modulos.respostas.eventos import GANCHOS
from toqqi.modulos.respostas.registro import escolhas_do_cliente, temas_da_resposta

log = logging.getLogger("toqqi.ia")

RESERVA = timedelta(minutes=5)
MAX_TENTATIVAS = 3
LOTE_TAREFA = 300
TEMPO_TAREFA = 240  # segundos por rodada
DIAS_RECENTES = 90
MAX_SEGUNDO_PLANO = 4  # análises logo depois de gravar, ao mesmo tempo, por processo
TEMPO_SEGUNDO_PLANO = 15  # segundos por chamada nesse caminho (a tarefa usa ia.TEMPO_LIMITE)
_vagas = threading.BoundedSemaphore(MAX_SEGUNDO_PLANO)
# etapa 5h: a fila de uma conta logo depois de importar respostas (vagas próprias, também 4 por processo)
MAX_FILA_CONTA = 100  # análises por importação
TEMPO_FILA_CONTA = 120  # segundos
_vagas_fila_conta = threading.BoundedSemaphore(MAX_SEGUNDO_PLANO)


# ---- regras -------------------------------------------------------------------

def mes_atual() -> date:
    return relogio.hoje().replace(day=1)


def temas_automaticos(r: Resposta, perguntas: list[dict] | None) -> list[str]:
    """Temas quando não são escolhidos à mão: os da IA (se analisou) mais os de "o que faltou" (escrito na análise,
    que a IA não vê); sem análise, pelas palavras-chave do texto do cliente, opções marcadas e "o que faltou"."""
    if r.ia_situacao == "analisada":
        return temas_mod.ordenar([t["tema"] for t in r.ia_temas or []] + temas_mod.detectar(r.o_que_faltou or ""))
    return temas_da_resposta(r.comentario_cliente, r.o_que_faltou, perguntas, r.respostas)


def limpar_analise(r: Resposta, situacao: str | None) -> None:
    """Troca a situação e apaga a análise anterior (que descrevia outro texto)."""
    r.ia_situacao = situacao
    r.ia_temas = r.ia_sentimento = r.ia_resumo = r.ia_modelo = r.ia_em = None
    r.ia_tentativas = 0


def entrada_da_resposta(s: Session, r: Resposta) -> ia.Entrada:
    """O que vai para a IA: texto do cliente, opções marcadas (respostas de pesquisa) e a nota. Nada mais."""
    opcoes: list[str] = []
    if r.origem == "pesquisa":
        f = s.get(Formulario, r.formulario_id)
        opcoes = escolhas_do_cliente(f.perguntas if f else [], r.respostas)
    return ia.Entrada(r.tipo_nota, r.nota, r.comentario_cliente or "", tuple(opcoes))


# ---- coletor (análise depois do commit) ----------------------------------------

_coletadas: ContextVar[list | None] = ContextVar("analises_apos_commit", default=None)


@contextmanager
def coletar_analises() -> Iterator[list[tuple[int, int]]]:
    """Junta (conta, resposta) marcadas como pendentes durante o bloco, para `analisar` depois do commit."""
    lista: list[tuple[int, int]] = []
    marca = _coletadas.set(lista)
    try:
        yield lista
    finally:
        _coletadas.reset(marca)


def marcar_pendente(s: Session, r: Resposta) -> None:
    limpar_analise(r, "pendente")
    s.flush()
    lista = _coletadas.get()
    if lista is not None:
        lista.append((r.conta_id, r.id))


def _ao_registrar_resposta(s: Session, r: Resposta) -> None:
    conta = s.get(Conta, r.conta_id)
    if conta is not None and passa_pela_ia(conta, r):
        marcar_pendente(s, r)


GANCHOS.append(_ao_registrar_resposta)


# ---- processamento --------------------------------------------------------------

@dataclass
class Reserva:
    conta_id: int
    resposta_id: int
    entrada: ia.Entrada
    hash: str
    mes: date  # mês do consumo do teto (o da reserva vencida, quando esta a assumiu)
    marca: datetime  # valor gravado em `ia_reservada_em`: identifica quem reservou


def _mes_de(momento: datetime) -> date:
    return momento.astimezone(relogio.FUSO).date().replace(day=1)


def _devolver(s: Session, conta_id: int, mes: date) -> None:
    s.execute(update(IaUsoMensal).where(IaUsoMensal.conta_id == conta_id, IaUsoMensal.mes == mes,
                                        IaUsoMensal.analises > 0)
              .values(analises=IaUsoMensal.analises - 1))


def _somar_tokens(s: Session, conta_id: int, mes: date, analise: ia.Analise) -> None:
    s.execute(update(IaUsoMensal).where(IaUsoMensal.conta_id == conta_id, IaUsoMensal.mes == mes)
              .values(tokens_entrada=IaUsoMensal.tokens_entrada + analise.tokens_entrada,
                      tokens_saida=IaUsoMensal.tokens_saida + analise.tokens_saida))


def _reservar(conta_id: int, resposta_id: int) -> Reserva | str | None:
    """Reserva + consumo do teto. Devolve a Reserva, "limite" (sem saldo no mês) ou None (nada a fazer).
    Reserva vencida: não consome de novo (o consumo dela nunca foi devolvido)."""
    with em_conta(conta_id) as s:
        agora = relogio.agora()
        r = s.scalar(select(Resposta).where(
            Resposta.id == resposta_id, Resposta.ia_situacao == "pendente",
            or_(Resposta.ia_reservada_em.is_(None), Resposta.ia_reservada_em < agora - RESERVA),
        ).with_for_update(skip_locked=True))
        if r is None:
            return None
        conta = s.get(Conta, conta_id)
        if not ia_ativa(conta):
            return None  # assinatura vencida: fica pendente (a tarefa só busca contas em dia)
        vencida = r.ia_reservada_em  # reserva anterior que ninguém soltou: o consumo dela continua valendo
        if not texto_qualifica(r.comentario_cliente):
            if vencida is not None:
                _devolver(s, conta_id, _mes_de(vencida))
                r.ia_reservada_em = None
            limpar_analise(r, None)  # o texto mudou e não passa mais pela IA
            return None
        if vencida is not None:
            mes = _mes_de(vencida)
        else:
            mes = mes_atual()
            consumo = s.execute(
                insert(IaUsoMensal).values(conta_id=conta_id, mes=mes, analises=1)
                .on_conflict_do_update(index_elements=[IaUsoMensal.conta_id, IaUsoMensal.mes],
                                       set_={"analises": IaUsoMensal.analises + 1},
                                       where=IaUsoMensal.analises < teto_mensal(conta))
                .returning(IaUsoMensal.analises)).first()
            if consumo is None:
                limpar_analise(r, "limite")
                r.ia_em = agora
                return "limite"
        entrada = entrada_da_resposta(s, r)
        r.ia_reservada_em = agora
        r.ia_texto_hash = entrada.hash()
        return Reserva(conta_id, resposta_id, entrada, r.ia_texto_hash, mes, agora)


def _soltar(s: Session, r: Resposta | None, reserva: Reserva) -> bool:
    """Quem ainda tem a reserva (ou a resposta foi excluída) devolve o saldo do teto e solta a reserva. False se
    outra rodada assumiu a resposta depois que esta reserva venceu (aí o consumo passou para ela)."""
    if r is not None and r.ia_reservada_em != reserva.marca:
        return False
    _devolver(s, reserva.conta_id, reserva.mes)
    if r is not None:
        r.ia_reservada_em = None
    return True


def _gravar(reserva: Reserva, analise: ia.Analise) -> str:
    with em_conta(reserva.conta_id) as s:
        r = s.get(Resposta, reserva.resposta_id, with_for_update=True)
        _somar_tokens(s, reserva.conta_id, reserva.mes, analise)
        if r is None or r.ia_situacao != "pendente" or entrada_da_resposta(s, r).hash() != reserva.hash:
            # mudou no meio do caminho (comentário editado, IA desligada, resposta excluída): descarta
            _soltar(s, r, reserva)
            return "descartada"
        r.ia_situacao = "analisada"
        r.ia_temas = analise.temas
        r.ia_sentimento = analise.sentimento
        r.ia_resumo = analise.resumo or None
        r.ia_modelo = analise.modelo
        r.ia_em = relogio.agora()
        r.ia_reservada_em = None
        if not r.temas_manuais:
            r.temas = temas_automaticos(r, None)
        return "analisada"


def _registrar_falha(reserva: Reserva, falha: ia.FalhaIA) -> str:
    with em_conta(reserva.conta_id) as s:
        r = s.get(Resposta, reserva.resposta_id, with_for_update=True)
        if not _soltar(s, r, reserva) or r is None or r.ia_situacao != "pendente":
            return "descartada"
        sem_tentativa = falha.tipo == "configuracao" and not falha.conta_tentativa
        if sem_tentativa or entrada_da_resposta(s, r).hash() != reserva.hash:
            return "pendente"  # não conta tentativa (chave/modelo, ou o texto já mudou)
        r.ia_tentativas += 1
        if falha.tipo == "definitiva" or r.ia_tentativas >= MAX_TENTATIVAS:
            r.ia_situacao = "falhou"
            r.ia_em = relogio.agora()
        return "falhou"


def processar(conta_id: int, resposta_id: int, tempo_limite: float = ia.TEMPO_LIMITE) -> str | None:
    """Analisa uma resposta pendente. Devolve analisada | falhou | limite | descartada | pendente | None.
    Levanta FalhaIA de configuração (depois de devolver o saldo) para quem chamou parar a rodada."""
    reserva = _reservar(conta_id, resposta_id)
    if not isinstance(reserva, Reserva):
        return reserva
    try:
        analise = ia.analisar(reserva.entrada, tempo_limite)
    except ia.FalhaIA as falha:
        resultado = _registrar_falha(reserva, falha)
        if falha.tipo == "configuracao":
            raise
        log.warning("IA: falha %s na resposta %s da conta %s (%s).", falha.tipo, resposta_id, conta_id,
                    falha.detalhe)
        return resultado
    except Exception:
        _registrar_falha(reserva, ia.FalhaIA("transitoria", "erro inesperado"))
        raise
    try:
        return _gravar(reserva, analise)
    except Exception as erro:  # noqa: BLE001 - o banco recusou o resultado: falha transitória (sem o texto do erro)
        log.error("IA: não foi possível gravar a análise da resposta %s da conta %s (%s); conta como tentativa.",
                  resposta_id, conta_id, descrever_erro(erro))
        return _registrar_falha(reserva, ia.FalhaIA("transitoria", "erro ao gravar o resultado"))


def _avisar_configuracao(falha: ia.FalhaIA) -> None:
    log.error("IA: a OpenAI recusou a chamada (%s). Confira OPENAI_API_KEY, IA_MODELO e IA_ESFORCO; as respostas "
              "continuam pendentes.", falha.detalhe)


def analisar(pares: Iterable[tuple[int, int]]) -> None:
    """Depois do commit (BackgroundTasks): analisa as respostas coletadas, no máximo `MAX_SEGUNDO_PLANO` ao mesmo
    tempo no processo e sem esperar vaga (sem vaga, ficam pendentes para a tarefa `ia`). Não levanta exceção."""
    if not ia.disponivel():
        return
    for conta_id, resposta_id in pares:
        if not _vagas.acquire(blocking=False):
            return  # outras análises em segundo plano ocupam as vagas: a tarefa `ia` pega esta
        try:
            processar(conta_id, resposta_id, TEMPO_SEGUNDO_PLANO)
        except ia.FalhaIA as falha:
            _avisar_configuracao(falha)
            return
        except Exception:  # noqa: BLE001 - segundo plano: registra e segue; a tarefa retoma
            log.exception("IA: erro ao analisar a resposta %s da conta %s", resposta_id, conta_id)
        finally:
            _vagas.release()


def executar() -> dict:
    """Tarefa `ia`: as pendentes mais antigas (até 300 ou 4 minutos por rodada), de contas com a IA ligada e
    liberadas (assinatura em dia: a regra de `assinatura.regras.liberada`, aplicada às contas com pendentes). Devolve
    {analisadas, falharam, limite}."""
    resumo = {"analisadas": 0, "falharam": 0, "limite": 0}
    if not ia.disponivel():
        return resumo
    inicio = relogio_real.monotonic()
    agora = relogio.agora()
    with modo_sistema() as s:  # só ids; o trabalho de cada resposta roda em em_conta(conta)
        com_pendentes = select(Resposta.conta_id).where(Resposta.ia_situacao == "pendente").distinct()
        contas = [c.id for c in s.scalars(select(Conta).where(Conta.ia_analise_respostas.is_(True),
                                                              Conta.id.in_(com_pendentes)))
                  if liberada(c, agora)]
        pares = s.execute(
            select(Resposta.conta_id, Resposta.id)
            .where(Resposta.ia_situacao == "pendente",
                   or_(Resposta.ia_reservada_em.is_(None), Resposta.ia_reservada_em < agora - RESERVA),
                   Resposta.conta_id.in_(contas))
            .order_by(Resposta.ia_reservada_em.asc().nulls_first(), Resposta.criada_em, Resposta.id)
            .limit(LOTE_TAREFA)).all() if contas else []
    for conta_id, resposta_id in pares:
        if relogio_real.monotonic() - inicio > TEMPO_TAREFA:
            break
        try:
            resultado = processar(conta_id, resposta_id)
        except ia.FalhaIA as falha:
            _avisar_configuracao(falha)
            break
        except Exception:  # noqa: BLE001 - uma resposta (ou conta) não derruba as outras
            log.exception("IA: erro ao analisar a resposta %s da conta %s", resposta_id, conta_id)
            resumo["falharam"] += 1
            continue
        if resultado == "analisada":
            resumo["analisadas"] += 1
        elif resultado == "falhou":
            resumo["falharam"] += 1
        elif resultado == "limite":
            resumo["limite"] += 1
    return resumo


CHAVES_RESUMO = {"analisada": "analisadas", "falhou": "falharam", "limite": "limite"}


def processar_conta(conta_id: int) -> dict:
    """Etapa 5h, depois de importar respostas (BackgroundTasks, depois do commit): a fila desta conta já, das respostas
    mais recentes para as mais antigas, até 100 análises ou 120 s, no máximo 4 ao mesmo tempo no processo (sem vaga,
    espera até o fim do tempo). Cada uma como na tarefa (`processar`: reserva, teto e tentativas), com o tempo limite
    do segundo plano; falha de configuração para a rodada. O resto fica pendente para a tarefa `ia`. Não levanta
    exceção. Devolve {analisadas, falharam, limite}."""
    resumo = {"analisadas": 0, "falharam": 0, "limite": 0}
    try:
        if not ia.disponivel():
            return resumo
        inicio = relogio_real.monotonic()
        agora = relogio.agora()
        with em_conta(conta_id) as s:
            conta = s.get(Conta, conta_id)
            if conta is None or not ia_ativa(conta):
                return resumo
            ids = s.scalars(
                select(Resposta.id)
                .where(Resposta.conta_id == conta_id, Resposta.ia_situacao == "pendente",
                       or_(Resposta.ia_reservada_em.is_(None), Resposta.ia_reservada_em < agora - RESERVA))
                .order_by(Resposta.data_resposta.desc(), Resposta.id.desc()).limit(MAX_FILA_CONTA)).all()
        parar = threading.Event()
        trava = threading.Lock()

        def uma(resposta_id: int) -> None:
            restante = TEMPO_FILA_CONTA - (relogio_real.monotonic() - inicio)
            if parar.is_set() or restante <= 0 or not _vagas_fila_conta.acquire(timeout=restante):
                return
            try:
                if parar.is_set():
                    return
                resultado = processar(conta_id, resposta_id, TEMPO_SEGUNDO_PLANO)
            except ia.FalhaIA as falha:
                parar.set()
                _avisar_configuracao(falha)
                return
            except Exception:  # noqa: BLE001 - uma resposta não derruba as outras
                log.exception("IA: erro ao analisar a resposta %s da conta %s", resposta_id, conta_id)
                resultado = "falhou"
            finally:
                _vagas_fila_conta.release()
            if resultado in CHAVES_RESUMO:
                with trava:
                    resumo[CHAVES_RESUMO[resultado]] += 1

        with ThreadPoolExecutor(max_workers=MAX_SEGUNDO_PLANO, thread_name_prefix="ia-fila-conta") as executor:
            list(executor.map(uma, ids))
    except Exception:  # noqa: BLE001 - segundo plano: registra e segue; a tarefa retoma
        log.exception("IA: erro ao analisar a fila da conta %s", conta_id)
    return resumo


# ---- configuração da conta (Configurações › IA) --------------------------------

def _estado(s: Session, conta: Conta) -> dict:
    mes = mes_atual()
    uso = s.get(IaUsoMensal, (conta.id, mes))
    pendentes, falharam = s.execute(select(
        func.count().filter(Resposta.ia_situacao == "pendente"),
        func.count().filter(Resposta.ia_situacao == "falhou", Resposta.ia_em >= inicio_do_dia(mes)),
    ).where(Resposta.conta_id == conta.id, Resposta.ia_situacao.in_(("pendente", "falhou")))).one()
    return {"disponivel": ia.disponivel(), "provedor": ia.nome_provedor(),
            "analise_respostas": conta.ia_analise_respostas, "mes": mes.strftime("%Y-%m"),
            "analises": uso.analises if uso else 0, "limite": teto_mensal(conta), "pendentes": pendentes,
            "falharam_no_mes": falharam, "cota": cota.estado(s, conta),
            # etapa 5d: como a IA escreve e os passos das ações
            "modelo": conta.ia_modelo, "estilo": conta.ia_estilo, "passos_acoes": conta.ia_passos_acoes,
            "modelos": ia_texto.opcoes_json(ia_texto.MODELOS), "estilos": ia_texto.opcoes_json(ia_texto.ESTILOS)}


def obter(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return _estado(s, s.get(Conta, ctx.conta_id))


# campo do PUT /conta/ia → coluna de `contas`
CAMPOS_CONFIG = {"analise_respostas": "ia_analise_respostas", "modelo": "ia_modelo", "estilo": "ia_estilo",
                 "passos_acoes": "ia_passos_acoes"}


def salvar(ctx: Contexto, dados) -> dict:
    """PUT /conta/ia: só os campos enviados (não nulos) mudam. Desligar a análise cancela as respostas pendentes
    (voltam a não passar pela IA); desligar os passos cancela as ações pendentes. Auditoria só com o que mudou."""
    from toqqi.modulos.acoes.passos import cancelar_pendentes  # aqui: acoes.passos importa este módulo

    novos = {c: getattr(dados, c) for c in CAMPOS_CONFIG if getattr(dados, c, None) is not None}
    with em_conta(ctx.conta_id) as s:
        conta = s.get(Conta, ctx.conta_id, with_for_update=True)
        mudou = {}
        for campo, coluna in CAMPOS_CONFIG.items():
            if campo in novos and getattr(conta, coluna) != novos[campo]:
                setattr(conta, coluna, novos[campo])
                mudou[campo] = novos[campo]
        if mudou.get("analise_respostas") is False:
            s.execute(update(Resposta).where(Resposta.conta_id == ctx.conta_id, Resposta.ia_situacao == "pendente")
                      .values(ia_situacao=None, ia_tentativas=0))
        if mudou.get("passos_acoes") is False:
            cancelar_pendentes(s, ctx.conta_id)
        if mudou:
            registrar(s, "config_ia", "info", mudou, usuario_id=ctx.usuario_id)
            s.flush()
        return _estado(s, conta)


def _indisponivel(msg: str) -> AppError:
    return AppError(409, "ia_indisponivel", msg)


def texto_qualifica_no_banco(coluna=None):
    """A regra de `texto_qualifica` (texto com 3+ letras) numa consulta (padrão: o texto do cliente da resposta)."""
    coluna = Resposta.comentario_cliente if coluna is None else coluna
    return func.length(func.regexp_replace(coluna, "[^[:alpha:]]", "", "g")) >= MIN_LETRAS


def saldo_do_teto(s: Session, conta: Conta) -> int:
    """O que cabe no teto do mês: o limite menos as análises do mês, as respostas pendentes e os passos de ações
    pendentes (que vão consumir o mesmo teto, etapa 5d). Pode ser zero ou negativo."""
    uso = s.get(IaUsoMensal, (conta.id, mes_atual()))
    pendentes = s.scalar(select(func.count()).select_from(Resposta).where(
        Resposta.conta_id == conta.id, Resposta.ia_situacao == "pendente")) or 0
    passos_pendentes = s.scalar(select(func.count()).select_from(Acao).where(
        Acao.conta_id == conta.id, Acao.ia_passos_situacao == "pendente")) or 0
    return teto_mensal(conta) - (uso.analises if uso else 0) - pendentes - passos_pendentes


def marcar_recentes(s: Session, conta: Conta, ids: Iterable[int] | None = None) -> tuple[int, int]:
    """Núcleo de "analisar os últimos 90 dias", sem erros (quem chama confere a IA da conta): marca como pendentes as
    respostas dos últimos 90 dias (todas as origens, inclusive importadas) com texto do cliente de 3+ letras, não
    arquivadas e sem análise (nunca analisadas, falhou ou limite), das mais recentes para as mais antigas, até o saldo
    do teto (`saldo_do_teto`). `ids`: só entre estas respostas. Devolve (marcadas, saldo antes de marcar)."""
    saldo = saldo_do_teto(s, conta)
    ids = None if ids is None else list(ids)
    if saldo <= 0 or (ids is not None and not ids):
        return 0, saldo
    conds = [Resposta.conta_id == conta.id, Resposta.arquivada.is_(False),
             Resposta.data_resposta >= inicio_do_dia(relogio.hoje() - timedelta(days=DIAS_RECENTES - 1)),
             or_(Resposta.ia_situacao.is_(None), Resposta.ia_situacao.in_(("falhou", "limite"))),
             texto_qualifica_no_banco()]
    if ids is not None:
        conds.append(Resposta.id == any_(bindparam("ids_marcar", ids, type_=ARRAY(BigInteger))))
    escolhidas = (select(Resposta.id).where(*conds)
                  .order_by(Resposta.data_resposta.desc(), Resposta.id.desc()).limit(saldo))
    marcadas = s.execute(
        update(Resposta).where(Resposta.id.in_(escolhidas))
        .values(ia_situacao="pendente", ia_tentativas=0, ia_temas=None,
                ia_sentimento=None, ia_resumo=None, ia_modelo=None, ia_em=None)
        .execution_options(synchronize_session=False)).rowcount
    return marcadas, saldo


def marcar_importadas(s: Session, conta_id: int, ids: Iterable[int]) -> int:
    """Etapa 5h, ao concluir a importação de respostas (na transação dela): as importadas agora entram na fila pela
    regra e com o saldo de `marcar_recentes`. Só com a IA ativa na conta (disponível na plataforma, `ia_analise_respostas`
    e conta liberada); senão, nenhuma. Devolve quantas foram marcadas."""
    ids = list(ids)
    if not ids or not ia.disponivel():
        return 0
    conta = s.get(Conta, conta_id, with_for_update=True)  # uma marcação por vez (como em analisar_recentes)
    if conta is None or not ia_ativa(conta):
        return 0
    return marcar_recentes(s, conta, ids)[0]


def analisar_recentes(ctx: Contexto) -> dict:
    """POST /conta/ia/analisar-recentes: `marcar_recentes` na conta, com os erros de quando a IA não está ativa."""
    with em_conta(ctx.conta_id) as s:
        conta = s.get(Conta, ctx.conta_id, with_for_update=True)  # uma marcação por vez
        if not ia.disponivel():
            raise _indisponivel("A análise de comentários com IA não está ligada na plataforma.")
        if not conta.ia_analise_respostas:
            raise _indisponivel("Ligue \"Analisar comentários com IA\" antes.")
        if not liberada(conta):
            raise _indisponivel("A análise com IA volta a funcionar quando a assinatura estiver em dia.")
        marcadas, saldo = marcar_recentes(s, conta)
        registrar(s, "ia_analisar_recentes", "info", {"marcadas": marcadas}, usuario_id=ctx.usuario_id)
        restantes = max(0, saldo - marcadas)
        return {"marcadas": marcadas, "restantes_no_mes": restantes}
