"""Panorama dos Planos de ação (pedido do Marcelo em 08/10/2026: "… e planos de ação também", depois de "assuma o
papel de melhor arquiteto, design e gestor de produtos"): o topo do quadro diz como estão os prazos das ações abertas,
quem está com quantas (e quantas vencidas) e quanto a equipe concluiu nos últimos 30 dias, em quanto tempo e quantos
clientes souberam do que foi feito (docs/api-acoes-panorama.md).

Os mesmos filtros do quadro, menos "Só vencidas" (é um jeito de ver o quadro, não um recorte); a lista por
responsável ignora também o filtro de responsável (é onde se escolhe um).

- `prazos`: as abertas (a fazer e em andamento) por prazo: vencidas, vencem hoje, nos próximos 7 dias, depois e sem
  prazo.
- `responsaveis`: as abertas de cada responsável (e as sem responsável), com as vencidas; primeiro quem tem mais
  vencidas, depois mais abertas; até 8.
- `concluidas`: as concluídas nos últimos 30 dias, a mediana de dias da criação à conclusão, quantas tiveram retorno
  ao cliente (o e-mail "Avisar o cliente") e o mesmo nos 30 dias anteriores.
"""
from datetime import date, timedelta

from sqlalchemy import func, select

from toqqi.core import relogio
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto
from toqqi.core.filtros import entre_datas
from toqqi.modelos import Acao, Responsavel
from toqqi.modulos.acoes.regras import aberta
from toqqi.modulos.acoes.servico import _juntar, condicoes

DIAS_CONCLUIDAS = 30
MAX_RESPONSAVEIS = 8


def _concluidas(s, conds: list, de: date, ate: date) -> dict:
    total, mediana, retorno = s.execute(_juntar(select(
        func.count(),
        func.percentile_cont(0.5).within_group(func.extract("epoch", Acao.concluida_em - Acao.criada_em) / 86400),
        func.count().filter(Acao.retorno_em.is_not(None)),
    ).select_from(Acao)).where(*conds, Acao.situacao == "concluida", *entre_datas(Acao.concluida_em, de, ate))).one()
    return {"de": de, "ate": ate, "total": total, "mediana_dias": round(float(mediana), 1) if mediana is not None else None,
            "com_retorno": retorno}


def panorama(ctx: Contexto, f) -> dict:
    hoje = relogio.hoje()
    semana = hoje + timedelta(days=7)
    conds = [Acao.conta_id == ctx.conta_id, *condicoes(f.model_copy(update={"so_vencidas": None}), hoje)]
    conds_resp = [Acao.conta_id == ctx.conta_id,
                  *condicoes(f.model_copy(update={"so_vencidas": None, "responsavel_id": None}), hoje)]
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        p = s.execute(_juntar(select(
            func.count(),
            func.count().filter(Acao.prazo < hoje),
            func.count().filter(Acao.prazo == hoje),
            func.count().filter(Acao.prazo > hoje, Acao.prazo <= semana),
            func.count().filter(Acao.prazo > semana),
            func.count().filter(Acao.prazo.is_(None)),
        ).select_from(Acao)).where(*conds, aberta())).one()
        vencidas = func.count().filter(Acao.prazo < hoje)
        linhas = s.execute(
            _juntar(select(Acao.responsavel_id, Responsavel.nome, func.count(), vencidas).select_from(Acao))
            .outerjoin(Responsavel, Responsavel.id == Acao.responsavel_id)
            .where(*conds_resp, aberta())
            .group_by(Acao.responsavel_id, Responsavel.nome)
            .order_by(vencidas.desc(), func.count().desc(), Responsavel.nome.asc().nulls_last())
            .limit(MAX_RESPONSAVEIS)).all()
        dados = {
            "prazos": {"abertas": p[0], "vencidas": p[1], "hoje": p[2], "proximos_7_dias": p[3], "depois": p[4],
                       "sem_prazo": p[5]},
            "responsaveis": [{"responsavel": {"id": i, "nome": n} if i is not None else None, "abertas": q,
                              "vencidas": v} for i, n, q, v in linhas],
            "concluidas": {
                **_concluidas(s, conds, hoje - timedelta(days=DIAS_CONCLUIDAS - 1), hoje),
                "anterior": _concluidas(s, conds, hoje - timedelta(days=2 * DIAS_CONCLUIDAS - 1),
                                        hoje - timedelta(days=DIAS_CONCLUIDAS)),
            },
        }
    return dados
