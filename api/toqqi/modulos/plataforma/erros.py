"""Plataforma › Erros e o e-mail diário de erros (etapa 5h, docs/api-etapa-5h.md §4). O registro em si fica em
`core.erros`. Modo sistema de propósito (a tabela `erros` não é de conta alguma).

Rotas (`requer_superadmin`):
- GET /plataforma/erros?origem=&situacao=abertos|resolvidos|todos&dias=7|30 → lista (até 500) dos erros com a última
  ocorrência nos últimos `dias` dias (padrão: abertos, 7 dias, todas as origens), da última ocorrência mais recente
  para a mais antiga: {id, origem, tipo, mensagem, local, pilha, versao, ocorrencias, primeira_em, ultima_em,
  ultimo_request_id, conta_id, conta_nome (null sem conta ou com a conta já excluída), resolvido_em}.
- POST /plataforma/erros/{id}/resolver e /reabrir → o erro (como na lista); 404 se não existe. Resolver um resolvido
  mantém a data; uma ocorrência nova reabre sozinha (`core.erros.registrar`).

E-mail diário (tarefa `erros`, no `tudo` antes da `limpeza`): a partir das 8h de São Paulo, no máximo uma vez por dia
(a marca é o evento global `erros_avisados` do dia, como a rodada da exclusão automática na `limpeza`; com a trava
`aviso_erros`, duas rodadas ao mesmo tempo não mandam dois). Só quando há erro aberto com ocorrência nas últimas 24 h:
"Toqqi: N erros nas últimas 24 h" com os 10 mais frequentes (tipo, onde, origem, quantas vezes e a última vez) e o botão
para Plataforma › Erros, aos superadmins (e-mails de `SUPERADMIN_EMAILS`) com usuário de e-mail confirmado e ativo
(quem está bloqueado não abre a Plataforma). Sem erro aberto, sem superadmin confirmado ou sem provedor de e-mail
(`provedor_ok`), o dia não é marcado e a próxima rodada confere de novo: o primeiro erro depois das 8h vira e-mail na
rodada seguinte (a rotina roda a cada 30 min), e só um e-mail por dia. A marca é gravada depois de mandar (uma queda
entre os dois manda de novo na próxima rodada, em vez de perder o aviso). Devolve {erros, emails}, ou null quando pulou
(antes das 8h, já mandou hoje, outra rodada em andamento ou sem provedor de e-mail).
"""
import logging
from datetime import datetime, time

from sqlalchemy import exists, func, select, text, update
from sqlalchemy.orm import Session

from toqqi.core import email, relogio
from toqqi.core.auditoria import registrar
from toqqi.core.config import config
from toqqi.core.db import engine, modo_sistema
from toqqi.core.errors import nao_encontrado
from toqqi.modelos import Auditoria, Conta, Erro, Usuario
from toqqi.modulos.assinatura.regras import inicio_do_dia
from toqqi.modulos.envios.configuracao import provedor_ok

log = logging.getLogger("toqqi.erros")

ORIGENS = ("api", "site", "tarefa")
SITUACOES = ("abertos", "resolvidos", "todos")
DIAS = (7, 30)
MAX_LISTA = 500
A_PARTIR_DE = time(8, 0)
TRAVA = "aviso_erros"
MAX_NO_EMAIL = 10
CAMINHO = "/plataforma/erros"
ROTULOS_ORIGEM = {"api": "API", "site": "site", "tarefa": "tarefa"}


# ---- lista, resolver e reabrir ----------------------------------------------------------------------------------

def _erro_json(e: Erro, conta_nome: str | None) -> dict:
    return {"id": e.id, "origem": e.origem, "tipo": e.tipo, "mensagem": e.mensagem, "local": e.local,
            "pilha": e.pilha, "versao": e.versao, "ocorrencias": e.ocorrencias, "primeira_em": e.primeira_em,
            "ultima_em": e.ultima_em, "ultimo_request_id": e.ultimo_request_id, "conta_id": e.conta_id,
            "conta_nome": conta_nome, "resolvido_em": e.resolvido_em}


def _com_conta():
    return select(Erro, Conta.nome).outerjoin(Conta, Conta.id == Erro.conta_id)


def listar(origem: str | None, situacao: str, dias: int) -> list[dict]:
    consulta = _com_conta().where(Erro.ultima_em >= func.now() - func.make_interval(0, 0, 0, dias))
    if origem:
        consulta = consulta.where(Erro.origem == origem)
    if situacao == "abertos":
        consulta = consulta.where(Erro.resolvido_em.is_(None))
    elif situacao == "resolvidos":
        consulta = consulta.where(Erro.resolvido_em.is_not(None))
    with modo_sistema() as s:
        linhas = s.execute(consulta.order_by(Erro.ultima_em.desc(), Erro.id.desc()).limit(MAX_LISTA)).all()
    return [_erro_json(e, nome) for e, nome in linhas]


def _mudar(erro_id: int, resolvido_em) -> dict:
    with modo_sistema() as s:
        s.execute(update(Erro).where(Erro.id == erro_id).values(resolvido_em=resolvido_em)
                  .execution_options(synchronize_session=False))
        linha = s.execute(_com_conta().where(Erro.id == erro_id)).one_or_none()
        if linha is None:
            raise nao_encontrado("Erro não encontrado.")
        return _erro_json(*linha)


def resolver(erro_id: int) -> dict:
    """Marca como resolvido agora (um já resolvido mantém a data)."""
    return _mudar(erro_id, func.coalesce(Erro.resolvido_em, func.now()))


def reabrir(erro_id: int) -> dict:
    return _mudar(erro_id, None)


# ---- e-mail diário ----------------------------------------------------------------------------------------------

def superadmins_confirmados(s: Session) -> list[str]:
    """E-mails de `SUPERADMIN_EMAILS` com usuário de e-mail confirmado e ativo."""
    emails = sorted(config().superadmins)
    if not emails:
        return []
    return list(s.scalars(select(Usuario.email).where(
        func.lower(Usuario.email).in_(emails), Usuario.email_confirmado.is_(True), Usuario.situacao == "ativo")
        .order_by(Usuario.email)))


def _ja_avisou_hoje(s: Session, agora: datetime) -> bool:
    return bool(s.scalar(select(exists().where(Auditoria.conta_id.is_(None), Auditoria.evento == "erros_avisados",
                                               Auditoria.criado_em >= inicio_do_dia(agora.date())))))


def _quando(momento: datetime) -> str:
    local = momento.astimezone(relogio.FUSO)
    return f"{local:%d/%m} às {local:%H:%M}"


def _vezes(n: int) -> str:
    return "1 vez" if n == 1 else f"{n} vezes"


def conteudo(abertos: list[Erro]) -> tuple[str, list]:
    """(assunto, parágrafos) do e-mail: os 10 mais frequentes primeiro."""
    n = len(abertos)
    assunto = f"Toqqi: {n} {'erro' if n == 1 else 'erros'} nas últimas 24 h"
    if n == 1:
        abertura = "Nas últimas 24 horas, 1 erro aconteceu e segue aberto em Plataforma › Erros."
    else:
        abertura = f"Nas últimas 24 horas, {n} erros aconteceram e seguem abertos em Plataforma › Erros."
    paragrafos: list = [abertura, email.Titulo("Os mais frequentes" if n <= MAX_NO_EMAIL
                                               else f"Os {MAX_NO_EMAIL} mais frequentes")]
    for e in abertos[:MAX_NO_EMAIL]:
        onde = e.local or "local desconhecido"
        paragrafos.append(f"{e.tipo} em {onde} ({ROTULOS_ORIGEM.get(e.origem, e.origem)}): "
                          f"{_vezes(e.ocorrencias)}, a última em {_quando(e.ultima_em)}.")
    if n > MAX_NO_EMAIL:
        resto = n - MAX_NO_EMAIL
        paragrafos.append(f"E mais {resto} {'erro' if resto == 1 else 'erros'} na lista.")
    return assunto, paragrafos


def rodape() -> tuple[str, str, str]:
    """(texto, trecho que vira link, link) do rodapé do e-mail."""
    return ("Você recebe este aviso por fazer parte da equipe Toqqi (SUPERADMIN_EMAILS). Ele sai no máximo uma vez por "
            "dia, só quando há erro aberto em Plataforma › Erros.", "Plataforma › Erros", _url())


def _url() -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}{CAMINHO}"


def _abertos_24h(s: Session) -> list[Erro]:
    return list(s.scalars(select(Erro).where(Erro.resolvido_em.is_(None),
                                             Erro.ultima_em >= func.now() - text("interval '24 hours'"))
                          .order_by(Erro.ocorrencias.desc(), Erro.ultima_em.desc(), Erro.id.desc())))


def _rodada(agora: datetime) -> dict | None:
    with modo_sistema() as s:
        if _ja_avisou_hoje(s, agora):
            return None
        abertos = _abertos_24h(s)
        para = superadmins_confirmados(s) if abertos else []
    if not abertos:
        return {"erros": 0, "emails": 0}
    if not para:
        log.warning("Aviso de erros: %d erro(s) aberto(s) nas últimas 24 h e nenhum superadmin com o e-mail "
                    "confirmado para avisar (SUPERADMIN_EMAILS).", len(abertos))
        return {"erros": len(abertos), "emails": 0}
    assunto, paragrafos = conteudo(abertos)
    for destino in para:
        email.enviar(destino, assunto, paragrafos, ("Abrir Plataforma › Erros", _url()), rodape())
    resumo = {"erros": len(abertos), "emails": len(para)}
    with modo_sistema() as s:
        registrar(s, "erros_avisados", "info", resumo)  # global (sem conta): a marca do dia
    log.info("Aviso de erros: e-mail diário enviado (%s).", resumo)
    return resumo


def aviso_diario(agora: datetime | None = None) -> dict | None:
    """Tarefa `erros` (regras no cabeçalho)."""
    agora = (agora or relogio.agora()).astimezone(relogio.FUSO)  # hora e dia de São Paulo
    if agora.time() < A_PARTIR_DE or not provedor_ok():
        return None
    with engine().connect().execution_options(isolation_level="AUTOCOMMIT") as conexao:
        if not conexao.scalar(text("select pg_try_advisory_lock(hashtextextended(:k, 0))"), {"k": TRAVA}):
            log.info("Aviso de erros: outra rodada em andamento; esta pula.")
            return None
        try:
            return _rodada(agora)
        finally:
            conexao.execute(text("select pg_advisory_unlock(hashtextextended(:k, 0))"), {"k": TRAVA})
