"""Resumo do painel e parecer dos relatórios (etapa 5d): IA sob demanda que gasta da cota do plano, por geração, as
análises do nível de modelo da conta (`ia_texto.analises_do_nivel`: 1, ou 2 no Mais detalhado), como uma pergunta
ao assistente (a que falha devolve as mesmas).

Os dois funcionam igual; o que muda (dados, instruções, formato e limpeza) vem num `Tipo`: `painel.resumo_ia.TIPO`
e `relatorios.parecer_ia.TIPO`. As permissões ficam nas rotas (`painel.ver` e `relatorios.ver`).

Recorte (`Recorte`): os filtros da tela (`de`, `ate`, `grupo_id`, `so_ativos`; vazio = true), com a chave canônica
`de=AAAA-MM-DD|ate=AAAA-MM-DD|grupo=ID|ativos=1` (vazio quando não há) e os mesmos valores em JSON (`filtros`). O
último resumo/parecer de cada chave fica em `ia_pareceres` até alguém gerar de novo (upsert pela chave).

GET (`estado`): {disponivel, motivo, cota, custo, item, pode_gerar_em}. `disponivel`/`motivo` como GET /assistente
(sem IA na plataforma: "ia_indisponivel", `cota` e `custo` null; conta não liberada: "conta_pausada"; nenhuma análise
restante: "cota_esgotada"; restam menos que o custo do nível: "cota_insuficiente"); `custo` = as análises de uma
geração no nível da conta; `item` = o salvo para a chave (vem mesmo sem IA); `pode_gerar_em` = `gerado_em` da última
geração do tipo na conta (qualquer chave) + 30 s, se ainda no futuro.

POST (`gerar`), nesta ordem: validação → vagas (`assistente.limite.em_andamento`: 2 por usuário → 429 `aguarde`; 6 no
processo → 503, sem esperar) → IA disponível (409 `ia_indisponivel`) → conta liberada (409 `conta_pausada`; o nível,
o estilo e o nome da conta são lidos aqui, uma vez só) → em andamento (trava em memória do processo por (conta, tipo):
429 `aguarde`) e 30 s desde a última geração do tipo na conta (pelo `gerado_em` no banco: 429 `aguarde` com os
segundos que faltam, 1 ou mais) → dados (nenhuma resposta NPS nem CSAT no recorte: 409 `sem_dados`, sem chamar a IA
nem gastar) → reservar o custo do nível lido (transação curta, commit antes da IA; sem saldo: 409 `cota_esgotada`
ou `cota_insuficiente`) → chamada única (`ia_texto.gerar`, com o mesmo nível e o estilo, fora de transação) →
limpeza (§2.5) → salvar → somar os tokens em `cota_tokens_*`. Falhou depois de reservar (inclusive texto obrigatório
vazio depois da limpeza): devolve as análises reservadas, soma os tokens já gastos e responde 503
`ia_indisponivel`. As vagas e a trava voltam sempre (finally). Só uma geração bem-sucedida conta para os 30 s. O
200 traz {item, cota, custo, pode_gerar_em} (`custo` = o desta geração).

Limpeza depois da IA: sem controles, sem `**` e sem endereços (`assistente.servico.sem_enderecos`), uma linha por
texto, cortado com "…" (`ia.cortar`).

Nada vai para a auditoria; o log leva só o tipo, o status, o tipo de falha e os tokens (nunca os dados nem o texto).
"""
import logging
import math
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core import ia, ia_texto, relogio
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.core.log_seguro import descrever_erro
from toqqi.modelos import Conta, IaParecer, Usuario
from toqqi.modulos.assinatura.regras import liberada
from toqqi.modulos.assistente.limite import MAX_SIMULTANEAS, em_andamento
from toqqi.modulos.assistente.servico import sem_enderecos
from toqqi.modulos.ia import cota
from toqqi.modulos.painel.servico import _validar_periodo

log = logging.getLogger("toqqi.ia")

INTERVALO = timedelta(seconds=30)
MSG_INDISPONIVEL = "A IA não está disponível no momento."
MSG_PAUSADA = "A IA volta quando a assinatura estiver em dia."
MSG_SEM_DADOS = "Não há respostas neste período para analisar."
MSG_VAGAS = "Você já tem pedidos à IA em andamento. Aguarde alguns segundos e tente de novo."


# ---- recorte e tipo ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Recorte:
    de: date | None
    ate: date | None
    grupo_id: int | None
    so_ativos: bool

    @classmethod
    def dos_filtros(cls, f) -> "Recorte":
        """De um modelo de filtros com `de`, `ate`, `grupo_id` e `so_ativos` (vazio = true)."""
        return cls(f.de, f.ate, f.grupo_id, f.so_ativos is not False)

    @property
    def chave(self) -> str:
        de = self.de.isoformat() if self.de else ""
        ate = self.ate.isoformat() if self.ate else ""
        grupo = "" if self.grupo_id is None else str(self.grupo_id)
        return f"de={de}|ate={ate}|grupo={grupo}|ativos={1 if self.so_ativos else 0}"

    def json(self) -> dict:
        return {"de": self.de.isoformat() if self.de else None, "ate": self.ate.isoformat() if self.ate else None,
                "grupo_id": self.grupo_id, "so_ativos": self.so_ativos}


@dataclass(frozen=True)
class Tipo:
    nome: str  # coluna `tipo`: painel | relatorios
    nome_formato: str  # `text.format.name` da chamada
    esquema: dict  # JSON Schema estrito do formato
    dados: Callable[[Session, Contexto, Recorte, date], dict | None]  # None = sem respostas NPS nem CSAT
    instrucoes: Callable[[str, date], str]  # (nome da conta, hoje) → instruções, sem a linha do estilo
    normalizar: Callable[[dict], dict]  # conteúdo da IA → conteúdo limpo (levanta ia.FalhaIA transitória)
    msg_andamento: str  # 429 com outra geração deste tipo em andamento na conta
    msg_falha: str  # 503


def linha(texto, limite: int) -> str:
    """Texto da IA numa linha: sem controles, sem `**`, sem endereços e cortado em `limite` com "…"."""
    if not isinstance(texto, str):
        return ""
    texto = " ".join(sem_enderecos(ia.sem_controle(texto)).split())
    return ia.cortar(texto, limite) if texto else ""


def falha_de_formato(detalhe: str) -> ia.FalhaIA:
    return ia.FalhaIA("transitoria", detalhe)


# ---- trava "em andamento" (memória do processo) -------------------------------------------------

class EmGeracao:
    """(conta, tipo) com uma geração em andamento neste processo."""

    def __init__(self):
        self._chaves: set[tuple[int, str]] = set()
        self._trava = threading.Lock()

    def entrar(self, chave: tuple[int, str]) -> bool:
        with self._trava:
            if chave in self._chaves:
                return False
            self._chaves.add(chave)
            return True

    def sair(self, chave: tuple[int, str]) -> None:
        with self._trava:
            self._chaves.discard(chave)

    def ocupada(self, chave: tuple[int, str]) -> bool:
        with self._trava:
            return chave in self._chaves


em_geracao = EmGeracao()


# ---- leitura ---------------------------------------------------------------------------------------

def _ultima_geracao(s: Session, conta_id: int, tipo: str) -> datetime | None:
    return s.scalar(select(func.max(IaParecer.gerado_em))
                    .where(IaParecer.conta_id == conta_id, IaParecer.tipo == tipo))


def _pode_gerar_em(ultima: datetime | None, agora: datetime) -> datetime | None:
    if ultima is None or ultima + INTERVALO <= agora:
        return None
    return ultima + INTERVALO


def _item(s: Session, conta_id: int, tipo: str, chave: str) -> dict | None:
    x = s.execute(select(IaParecer, Usuario.nome.label("usuario_nome"))
                  .outerjoin(Usuario, Usuario.id == IaParecer.gerado_por)
                  .where(IaParecer.conta_id == conta_id, IaParecer.tipo == tipo, IaParecer.chave == chave)
                  .execution_options(populate_existing=True)).one_or_none()
    if x is None:
        return None
    p: IaParecer = x.IaParecer
    return {"conteudo": p.conteudo, "filtros": p.filtros, "gerado_em": p.gerado_em,
            "gerado_por": {"id": p.gerado_por, "nome": x.usuario_nome} if p.gerado_por else None,
            "modelo": p.modelo, "modelo_rotulo": ia_texto.rotulo_do_nivel(p.modelo), "estilo": p.estilo}


def estado(ctx: Contexto, tipo: Tipo, recorte: Recorte) -> dict:
    """GET: {disponivel, motivo, cota, custo, item, pode_gerar_em}."""
    _validar_periodo(recorte.de, recorte.ate)
    with em_conta(ctx.conta_id) as s:
        conta = s.get(Conta, ctx.conta_id)
        item = _item(s, ctx.conta_id, tipo.nome, recorte.chave)
        pode = _pode_gerar_em(_ultima_geracao(s, ctx.conta_id, tipo.nome), relogio.agora())
        uso = cota.estado(s, conta) if ia.disponivel() else None
        custo = ia_texto.analises_do_nivel(conta.ia_modelo) if uso is not None else None
        livre = liberada(conta)
    base = {"cota": uso, "custo": custo, "item": item, "pode_gerar_em": pode}
    if uso is None:
        return {"disponivel": False, "motivo": "ia_indisponivel", **base}
    if not livre:
        return {"disponivel": False, "motivo": "conta_pausada", **base}
    sem_saldo = cota.motivo_sem_saldo(uso, custo)
    if sem_saldo:
        return {"disponivel": False, "motivo": sem_saldo, **base}
    return {"disponivel": True, "motivo": None, **base}


# ---- geração ---------------------------------------------------------------------------------------

def gerar(ctx: Contexto, tipo: Tipo, recorte: Recorte) -> dict:
    """POST: {item, cota, pode_gerar_em}."""
    _validar_periodo(recorte.de, recorte.ate)
    recusada = em_andamento.entrar(ctx.usuario_id)  # as vagas do assistente, sem esperar
    if recusada == "usuario":
        raise AppError(429, "aguarde", MSG_VAGAS)
    if recusada == "processo":
        log.warning("IA sob demanda: as %d vagas do processo estão ocupadas; %s da conta %s recusado.",
                    MAX_SIMULTANEAS, tipo.nome, ctx.conta_id)
        raise AppError(503, "ia_indisponivel", tipo.msg_falha)
    try:
        return _gerar(ctx, tipo, recorte)
    finally:
        em_andamento.sair(ctx.usuario_id)


def _gerar(ctx: Contexto, tipo: Tipo, recorte: Recorte) -> dict:
    if not ia.disponivel():
        raise AppError(409, "ia_indisponivel", MSG_INDISPONIVEL)
    with em_conta(ctx.conta_id) as s:
        conta = s.get(Conta, ctx.conta_id)
        livre = liberada(conta)
        # o nível é lido uma vez só: a reserva gasta o custo dele e a chamada usa o mesmo modelo (trocar o nível no
        # meio não cobra 1 e roda o Mais detalhado)
        nome_conta, nivel, estilo = conta.nome, conta.ia_modelo, conta.ia_estilo
    if not livre:
        raise AppError(409, "conta_pausada", MSG_PAUSADA)
    trava = (ctx.conta_id, tipo.nome)
    if not em_geracao.entrar(trava):
        raise AppError(429, "aguarde", tipo.msg_andamento)
    try:
        hoje = relogio.hoje()
        with em_conta(ctx.conta_id) as s:  # a última geração é lida já com a trava (nenhuma outra termina no meio)
            pode = _pode_gerar_em(_ultima_geracao(s, ctx.conta_id, tipo.nome), relogio.agora())
            if pode is not None:
                segundos = max(1, math.ceil((pode - relogio.agora()).total_seconds()))
                raise AppError(429, "aguarde", f"Aguarde {segundos} s para gerar de novo.")
            sem_jit(s)
            dados = tipo.dados(s, ctx, recorte, hoje)
        if dados is None:
            raise AppError(409, "sem_dados", MSG_SEM_DADOS)
        with em_conta(ctx.conta_id) as s:
            conta = s.get(Conta, ctx.conta_id)
            reserva = cota.reservar(s, conta, ia_texto.analises_do_nivel(nivel))
            if reserva is None:
                raise cota.erro_sem_saldo(s, conta, nivel)
        instrucoes = ia_texto.com_estilo(tipo.instrucoes(nome_conta, hoje), estilo)
        return _chamar_e_salvar(ctx, tipo, recorte, reserva, instrucoes, dados, nivel, estilo)
    finally:
        em_geracao.sair(trava)


def _chamar_e_salvar(ctx: Contexto, tipo: Tipo, recorte: Recorte, reserva: cota.Reserva, instrucoes: str,
                     dados: dict, nivel: str, estilo: str) -> dict:
    """Com as análises reservadas: chamada, limpeza e gravação. Qualquer falha devolve as análises (as mesmas da
    reserva) com os tokens gastos."""
    tokens: tuple[int, int] | None = None
    try:
        bruto, entrada, saida, _modelo = ia_texto.gerar(tipo.nome_formato, instrucoes, dados, tipo.esquema, nivel)
        tokens = (entrada, saida)
        conteudo = tipo.normalizar(bruto)
        item = _salvar(ctx, tipo, recorte, conteudo, nivel, estilo)
    except ia.FalhaIA as falha:
        gastos = tokens or (getattr(falha, "tokens_entrada", 0), getattr(falha, "tokens_saida", 0))
        _devolver(ctx, reserva, gastos)
        nivel_log = logging.ERROR if falha.tipo == "configuracao" else logging.WARNING
        log.log(nivel_log, "IA sob demanda: falha %s (%s) no %s da conta %s; análises devolvidas: %d "
                "(tokens=%d/%d).%s", falha.tipo, falha.detalhe, tipo.nome, ctx.conta_id, reserva.quantidade, *gastos,
                " Confira OPENAI_API_KEY e os modelos em Plataforma › Parâmetros." if falha.tipo == "configuracao"
                else "")
        raise AppError(503, "ia_indisponivel", tipo.msg_falha) from None
    except Exception as erro:
        gastos = tokens or (0, 0)
        _devolver(ctx, reserva, gastos)
        log.error("IA sob demanda: erro inesperado no %s da conta %s; análises devolvidas: %d (tokens=%d/%d, %s).",
                  tipo.nome, ctx.conta_id, reserva.quantidade, *gastos, descrever_erro(erro))
        # §2.1: falhou depois de reservar → 503 (a tela oferece "Tentar de novo"); o detalhe fica só no log
        raise AppError(503, "ia_indisponivel", tipo.msg_falha) from None
    # pronto e salvo: daqui em diante, a contabilidade não derruba a resposta
    _somar_tokens(ctx, reserva, tokens)
    log.info("IA sob demanda: %s gerado na conta %s (nível %s, análises=%d, tokens=%d/%d).", tipo.nome,
             ctx.conta_id, nivel, reserva.quantidade, *tokens)
    # `custo`: o desta geração (o nível lido no começo), que é o da próxima enquanto ninguém trocar o nível
    return {"item": item, "cota": _cota_depois(ctx, reserva), "custo": reserva.quantidade,
            "pode_gerar_em": item["gerado_em"] + INTERVALO}


def _salvar(ctx: Contexto, tipo: Tipo, recorte: Recorte, conteudo: dict, nivel: str, estilo: str) -> dict:
    """Upsert pela chave (gerar de novo substitui) e o item como o GET devolve."""
    valores = {"filtros": recorte.json(), "conteudo": conteudo, "modelo": nivel, "estilo": estilo,
               "gerado_por": ctx.usuario_id, "gerado_em": relogio.agora()}
    with em_conta(ctx.conta_id) as s:
        s.execute(insert(IaParecer)
                  .values(conta_id=ctx.conta_id, tipo=tipo.nome, chave=recorte.chave, **valores)
                  .on_conflict_do_update(index_elements=[IaParecer.conta_id, IaParecer.tipo, IaParecer.chave],
                                         set_=valores))
        return _item(s, ctx.conta_id, tipo.nome, recorte.chave)


def _devolver(ctx: Contexto, reserva: cota.Reserva, tokens: tuple[int, int]) -> None:
    with em_conta(ctx.conta_id) as s:
        cota.devolver(reserva, s)
        cota.somar_tokens(reserva, *tokens, s)


def _somar_tokens(ctx: Contexto, reserva: cota.Reserva, tokens: tuple[int, int]) -> None:
    try:
        cota.somar_tokens(reserva, *tokens)
    except Exception as erro:  # noqa: BLE001 - o resultado já foi salvo: não o perde por causa da contabilidade
        log.error("IA sob demanda: não foi possível somar os tokens (%d/%d) na conta %s (%s).", *tokens,
                  ctx.conta_id, descrever_erro(erro))


def _cota_depois(ctx: Contexto, reserva: cota.Reserva) -> dict:
    try:
        with em_conta(ctx.conta_id) as s:
            return cota.estado(s, s.get(Conta, ctx.conta_id))
    except Exception as erro:  # noqa: BLE001 - o resultado já foi salvo: vai a cota calculada pela reserva
        log.error("IA sob demanda: não foi possível ler a cota da conta %s (%s); vai a da reserva.", ctx.conta_id,
                  descrever_erro(erro))
        return cota.estado_da_reserva(reserva)
