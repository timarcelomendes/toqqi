"""Regras comuns das ações: selo de prazo e ordem de urgência (quadro, lista, painel e respostas)."""
from datetime import date, timedelta

from sqlalchemy import and_, case

from toqqi.modelos import Acao

SITUACOES = ("a_fazer", "em_andamento", "concluida")
ABERTAS = ("a_fazer", "em_andamento")
PRIORIDADES = ("alta", "media", "baixa")


def prazo_selo(situacao: str | None, prazo: date | None, hoje: date) -> str | None:
    """Só para ação não concluída com prazo: vencido (prazo < hoje), hoje, amanha; senão None."""
    if situacao is None or situacao == "concluida" or prazo is None:
        return None
    if prazo < hoje:
        return "vencido"
    if prazo == hoje:
        return "hoje"
    if prazo == hoje + timedelta(days=1):
        return "amanha"
    return None


def aberta():
    return Acao.situacao.in_(ABERTAS)


def vencida(hoje: date):
    return and_(aberta(), Acao.prazo < hoje)


def peso_prioridade():
    return case((Acao.prioridade == "alta", 0), (Acao.prioridade == "media", 1), else_=2)


def ordem_urgencia(hoje: date) -> list:
    """Vencidas primeiro, depois prazo (vazio por último), prioridade (alta → baixa) e criação."""
    return [case((Acao.prazo < hoje, 0), else_=1), Acao.prazo.asc().nulls_last(), peso_prioridade(),
            Acao.criada_em.asc(), Acao.id.asc()]
