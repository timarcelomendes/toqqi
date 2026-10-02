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

A análise de cada resposta não gasta a cota de IA do plano (etapa 5): só o teto de segurança mensal abaixo.
"""
import logging
import threading
import time as relogio_real
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core import ia, relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.core.filtros import inicio_do_dia
from toqqi.core.log_seguro import descrever_erro
from toqqi.modelos import Conta, Formulario, IaUsoMensal, Resposta
from toqqi.modulos.assinatura.regras import liberada
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
            "falharam_no_mes": falharam}


def obter(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return _estado(s, s.get(Conta, ctx.conta_id))


def salvar(ctx: Contexto, ligar: bool) -> dict:
    """Liga ou desliga a análise da conta; desligar cancela as pendentes (voltam a não passar pela IA)."""
    with em_conta(ctx.conta_id) as s:
        conta = s.get(Conta, ctx.conta_id, with_for_update=True)
        if conta.ia_analise_respostas != ligar:
            conta.ia_analise_respostas = ligar
            if not ligar:
                s.execute(update(Resposta).where(Resposta.conta_id == ctx.conta_id, Resposta.ia_situacao == "pendente")
                          .values(ia_situacao=None, ia_tentativas=0))
            registrar(s, "config_ia", "info", {"analise_respostas": ligar}, usuario_id=ctx.usuario_id)
            s.flush()
        return _estado(s, conta)


def _indisponivel(msg: str) -> AppError:
    return AppError(409, "ia_indisponivel", msg)


def analisar_recentes(ctx: Contexto) -> dict:
    """Marca como pendentes as respostas dos últimos 90 dias (todas as origens, inclusive importadas) com texto do
    cliente de 3+ letras, não arquivadas e sem análise (nunca analisadas, falhou ou limite), das mais recentes para
    as mais antigas, até o saldo do teto do mês menos as pendentes."""
    with em_conta(ctx.conta_id) as s:
        conta = s.get(Conta, ctx.conta_id, with_for_update=True)  # uma marcação por vez
        if not ia.disponivel():
            raise _indisponivel("A análise de comentários com IA não está ligada na plataforma.")
        if not conta.ia_analise_respostas:
            raise _indisponivel("Ligue \"Analisar comentários com IA\" antes.")
        if not liberada(conta):
            raise _indisponivel("A análise com IA volta a funcionar quando a assinatura estiver em dia.")
        estado = _estado(s, conta)
        saldo = estado["limite"] - estado["analises"] - estado["pendentes"]
        marcadas = 0
        if saldo > 0:
            letras = func.length(func.regexp_replace(Resposta.comentario_cliente, "[^[:alpha:]]", "", "g"))
            ids = (select(Resposta.id)
                   .where(Resposta.conta_id == ctx.conta_id, Resposta.arquivada.is_(False),
                          Resposta.data_resposta >= inicio_do_dia(relogio.hoje() - timedelta(days=DIAS_RECENTES - 1)),
                          or_(Resposta.ia_situacao.is_(None), Resposta.ia_situacao.in_(("falhou", "limite"))),
                          letras >= MIN_LETRAS)
                   .order_by(Resposta.data_resposta.desc(), Resposta.id.desc()).limit(saldo))
            marcadas = s.execute(
                update(Resposta).where(Resposta.id.in_(ids))
                .values(ia_situacao="pendente", ia_tentativas=0, ia_temas=None,
                        ia_sentimento=None, ia_resumo=None, ia_modelo=None, ia_em=None)
                .execution_options(synchronize_session=False)).rowcount
        registrar(s, "ia_analisar_recentes", "info", {"marcadas": marcadas}, usuario_id=ctx.usuario_id)
        restantes = max(0, estado["limite"] - estado["analises"] - estado["pendentes"] - marcadas)
        return {"marcadas": marcadas, "restantes_no_mes": restantes}
