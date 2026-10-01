"""Reclamações por tema e picos de reclamação (painel, relatório de temas, alerta por e-mail e resumo semanal).

Reclamação = tema da resposta em `temas_reclamacao` (coluna gerada: sentimento negativo da IA sobre o tema ou, sem
análise da IA para o tema, nota de detrator/insatisfeito). Pico = tema com 3+ reclamações nos últimos 7 dias (o
último dia e os 6 anteriores) e pelo menos o dobro da média semanal das 4 semanas anteriores (dias −34 a −7, ÷ 4,
1 casa). Respostas não arquivadas, de empresas ativas ou sem empresa, NPS e CSAT; sem os filtros da tela.
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.filtros import inicio_do_dia
from toqqi.modelos import Empresa, Resposta
from toqqi.modulos.respostas.indicadores import arredondar
from toqqi.modulos.respostas.temas import CHAVES, ROTULOS

MIN_RECLAMACOES = 3
FATOR = 2


def contar(s: Session, conta_id: int, ultimo_dia: date) -> dict[str, tuple[int, int]]:
    """{tema: (reclamações nos 7 dias até `ultimo_dia`, reclamações nas 4 semanas antes deles)}."""
    inicio = inicio_do_dia(ultimo_dia - timedelta(days=34))
    corte = inicio_do_dia(ultimo_dia - timedelta(days=6))
    fim = inicio_do_dia(ultimo_dia + timedelta(days=1))
    sq = (select(func.unnest(Resposta.temas_reclamacao).label("tema"), Resposta.data_resposta.label("data"))
          .select_from(Resposta).outerjoin(Empresa, Empresa.id == Resposta.empresa_id)
          .where(Resposta.conta_id == conta_id, Resposta.arquivada.is_(False), Resposta.tipo_nota.in_(("nps", "csat")),
                 Resposta.data_resposta >= inicio, Resposta.data_resposta < fim,
                 or_(Resposta.empresa_id.is_(None), Empresa.ativa.is_(True)))
          .subquery())
    linhas = s.execute(select(sq.c.tema, func.count().filter(sq.c.data >= corte),
                              func.count().filter(sq.c.data < corte)).group_by(sq.c.tema)).all()
    return {tema: (recentes, anteriores) for tema, recentes, anteriores in linhas}


def media_semanal(anteriores: int) -> Decimal:
    return arredondar(Decimal(anteriores) / 4, 1)


def eh_pico(recentes: int, media: Decimal) -> bool:
    return recentes >= MIN_RECLAMACOES and recentes >= FATOR * media


def calcular(s: Session, conta_id: int, ultimo_dia: date | None = None) -> list[dict]:
    """Picos dos 7 dias até `ultimo_dia` (padrão: hoje), mais reclamações primeiro."""
    ultimo_dia = ultimo_dia or relogio.hoje()
    itens = []
    for tema, (recentes, anteriores) in contar(s, conta_id, ultimo_dia).items():
        media = media_semanal(anteriores)
        if tema in ROTULOS and eh_pico(recentes, media):
            itens.append({"tema": tema, "rotulo": ROTULOS[tema], "reclamacoes": recentes,
                          "media_anterior": float(media), "de": ultimo_dia - timedelta(days=6), "ate": ultimo_dia})
    return sorted(itens, key=lambda x: (-x["reclamacoes"], CHAVES.index(x["tema"])))
