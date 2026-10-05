"""Etapa 5i: a saúde da carteira no Início (`GET /painel/saude`) e as renovações dos próximos 60 dias em Relatórios ›
Desfecho (`GET /relatorios/renovacoes`). A saúde de uma empresa e a da lista ficam em `empresas`."""
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select

from toqqi.core import relogio
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto, requer
from toqqi.modelos import Empresa, Responsavel
from toqqi.modulos.saude.calculo import saude_das_empresas
from toqqi.modulos.saude.regras import FAIXAS, RENOVACAO_DIAS

router = APIRouter(tags=["saude"])
ZERO = Decimal("0.00")
PESO = {"risco": 0, "atencao": 1, "saudavel": 2, "sem_dados": 3}


def _ativas(s, grupo_id: int | None):
    consulta = select(Empresa.id, Empresa.nome, Empresa.valor_mensal, Empresa.renovacao_em, Empresa.responsavel_id,
                      Responsavel.nome).outerjoin(Responsavel, Responsavel.id == Empresa.responsavel_id)\
        .where(Empresa.ativa.is_(True))
    if grupo_id:
        consulta = consulta.where(Empresa.grupo_id == grupo_id)
    return s.execute(consulta).all()


@router.get("/painel/saude")
def carteira(grupo_id: int | None = None, ctx: Contexto = Depends(requer("painel.ver"))):
    """Quantas empresas ativas (e quanto de receita) em cada faixa agora, e as renovações em Risco nos próximos 60
    dias. Não usa o período: é o estado de hoje."""
    hoje = relogio.hoje()
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        linhas = _ativas(s, grupo_id)
        saudes = saude_das_empresas(s, hoje, [x[0] for x in linhas])
    faixas = {f: {"empresas": 0, "receita": ZERO} for f in FAIXAS}
    risco_renova = []
    for e_id, nome, valor, renovacao, _, _ in linhas:
        sd = saudes[e_id]
        faixas[sd["faixa"]]["empresas"] += 1
        faixas[sd["faixa"]]["receita"] += valor or ZERO
        if sd["faixa"] == "risco" and sd["renovacao"]:
            risco_renova.append({"empresa": {"id": e_id, "nome": nome}, "renovacao_em": renovacao,
                                 "dias": sd["renovacao"]["dias"], "valor_mensal": valor})
    risco_renova.sort(key=lambda r: r["dias"])
    return {"faixas": faixas, "empresas": len(linhas), "receita": sum((x[2] or ZERO for x in linhas), ZERO),
            "sem_valor": sum(1 for x in linhas if not x[2]),
            "renovacoes_em_risco": {"empresas": len(risco_renova),
                                    "receita": sum((r["valor_mensal"] or ZERO for r in risco_renova), ZERO),
                                    "primeira": risco_renova[0] if risco_renova else None}}


@router.get("/relatorios/renovacoes")
def renovacoes(grupo_id: int | None = None, ctx: Contexto = Depends(requer("relatorios.ver"))):
    """Empresas ativas com renovação de 30 dias atrás até 60 dias à frente, com a saúde; as em Risco ou Atenção que
    renovam nos 60 dias (`destaque`) primeiro."""
    hoje = relogio.hoje()
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        linhas = [x for x in _ativas(s, grupo_id)
                  if x[3] is not None and -30 <= (x[3] - hoje).days <= RENOVACAO_DIAS]
        saudes = saude_das_empresas(s, hoje, [x[0] for x in linhas])
    itens = []
    for e_id, nome, valor, renovacao, resp_id, resp_nome in linhas:
        sd = saudes[e_id]
        itens.append({"empresa": {"id": e_id, "nome": nome}, "renovacao_em": renovacao,
                      "dias": (renovacao - hoje).days, "valor_mensal": valor,
                      "responsavel": {"id": resp_id, "nome": resp_nome} if resp_id else None,
                      "saude": {"faixa": sd["faixa"], "nota": sd["nota"], "porques": sd["porques"][:2]},
                      "destaque": sd["destaque"]})
    itens.sort(key=lambda i: (not i["destaque"], PESO[i["saude"]["faixa"]] if i["destaque"] else 0, i["dias"]))
    return {"itens": itens, "resumo": {"empresas": len(itens),
                                       "receita": sum((i["valor_mensal"] or ZERO for i in itens), ZERO)}}
