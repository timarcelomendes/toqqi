"""Auditoria › E-mails enviados (etapa 5e): o registro `emails_enviados` da conta (`auditoria.ver`) e a limpeza.

Quem grava é `core.email` (`registrar_envio`, depois de cada tentativa). Aqui:
- `listar`: mais novos primeiro, paginado; filtros de período (dias de São Paulo; padrão: os 30 dias até hoje — só `de`
  vai até hoje, só `ate` pega os 30 dias até ele; no máximo 90 dias, o que o registro guarda), situação, tipo e busca
  (no destinatário e no assunto, sem acento e sem diferenciar maiúsculas). `falhas_7_dias`: as falhas da conta de
  hoje − 6 dias até agora, sem os filtros — o mesmo recorte de "Ver só as falhas" (situação falhou, de hoje − 6 a hoje).
- `limpar` (tarefa `limpeza`): apaga as linhas com mais de 90 dias, em lotes (uma transação por lote), em modo sistema:
  a limpeza passa por todas as contas.

As consultas levam `conta_id` explícito além do RLS, para o banco usar os índices por conta.
"""
from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field
from sqlalchemy import Text, cast, delete, func, or_, select

from toqqi.core import relogio
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.email import TIPOS
from toqqi.core.errors import AppError
from toqqi.core.filtros import DataFiltro, entre_datas, inicio_do_dia
from toqqi.core.paginacao import Pagina
from toqqi.core.texto import sem_acento
from toqqi.modelos import EmailEnviado

DIAS_PADRAO = 30
MAX_DIAS = 90
DIAS_GUARDADOS = 90
DIAS_FALHAS = 7
LOTE_LIMPEZA = 5000
# busca sem acento (como a das indicações): translate + lower no banco, sem_acento no termo
SEM_ACENTO_DE = "áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ"
SEM_ACENTO_PARA = "aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN"


def _vazio_none(v):
    return None if v == "" else v


Opcional = BeforeValidator(_vazio_none)


class FiltrosEmails(BaseModel):
    de: DataFiltro = None
    ate: DataFiltro = None
    situacao: Annotated[Literal["enviado", "falhou"] | None, Opcional] = None
    tipo: Annotated[Literal[tuple(TIPOS)] | None, Opcional] = None  # type: ignore[valid-type]
    busca: Annotated[Annotated[str, Field(max_length=100)] | None, Opcional] = None


def periodo(de: date | None, ate: date | None) -> tuple[date, date]:
    """(de, ate) com os padrões; 422 no campo `de` se o início vem depois do fim ou se passa de 90 dias."""
    fim = ate or relogio.hoje()
    inicio = de or fim - timedelta(days=DIAS_PADRAO - 1)
    if inicio > fim:
        msg = "A data inicial precisa ser igual ou anterior à final."
        raise AppError(422, "dados_invalidos", "Confira o período.", {"de": msg})
    if (fim - inicio).days + 1 > MAX_DIAS:
        msg = f"O período pode ter no máximo {MAX_DIAS} dias."
        raise AppError(422, "dados_invalidos", "Confira o período.", {"de": msg})
    return inicio, fim


def _sem_acento_sql(coluna):
    return func.lower(func.translate(cast(coluna, Text), SEM_ACENTO_DE, SEM_ACENTO_PARA))


def _busca(termo: str):
    t = sem_acento(termo).lower()
    return or_(*(_sem_acento_sql(c).contains(t, autoescape=True)
                 for c in (EmailEnviado.destinatario, EmailEnviado.assunto)))


def item_json(e: EmailEnviado) -> dict:
    return {"id": e.id, "tipo": e.tipo, "tipo_rotulo": TIPOS.get(e.tipo, e.tipo), "destinatario": e.destinatario,
            "assunto": e.assunto, "situacao": e.situacao, "erro": e.erro, "criado_em": e.criado_em}


def listar(ctx: Contexto, f: FiltrosEmails, pg: Pagina) -> dict:
    """Página do registro + `falhas_7_dias` (sem os filtros) e o período usado (`periodo: {de, ate}`)."""
    de, ate = periodo(f.de, f.ate)
    conds = [EmailEnviado.conta_id == ctx.conta_id, *entre_datas(EmailEnviado.criado_em, de, ate)]
    if f.situacao:
        conds.append(EmailEnviado.situacao == f.situacao)
    if f.tipo:
        conds.append(EmailEnviado.tipo == f.tipo)
    if f.busca and f.busca.strip():
        conds.append(_busca(f.busca.strip()))
    desde = inicio_do_dia(relogio.hoje() - timedelta(days=DIAS_FALHAS - 1))
    with em_conta(ctx.conta_id) as s:
        total = s.scalar(select(func.count()).select_from(EmailEnviado).where(*conds))
        linhas = s.scalars(select(EmailEnviado).where(*conds)
                           .order_by(EmailEnviado.criado_em.desc(), EmailEnviado.id.desc())
                           .limit(pg.por_pagina).offset(pg.offset)).all()
        falhas = s.scalar(select(func.count()).select_from(EmailEnviado).where(
            EmailEnviado.conta_id == ctx.conta_id, EmailEnviado.situacao == "falhou", EmailEnviado.criado_em >= desde))
    return {**pg.resultado([item_json(e) for e in linhas], total), "falhas_7_dias": falhas,
            "periodo": {"de": de, "ate": ate}}


def limpar(agora: datetime | None = None) -> int:
    """Apaga os registros com mais de 90 dias (todas as contas), em lotes. Devolve quantos apagou."""
    limite = (agora or relogio.agora()) - timedelta(days=DIAS_GUARDADOS)
    apagados = 0
    while True:
        with modo_sistema() as s:  # a limpeza passa por todas as contas
            lote = (select(EmailEnviado.id).where(EmailEnviado.criado_em < limite).limit(LOTE_LIMPEZA)
                    .scalar_subquery())
            n = s.execute(delete(EmailEnviado).where(EmailEnviado.id.in_(lote))
                          .execution_options(synchronize_session=False)).rowcount
        apagados += n
        if n < LOTE_LIMPEZA:
            return apagados
