"""Consulta do registro de atividades (auditoria) da conta."""
import unicodedata
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import String, cast, func, or_, select

from toqqi.core.auditoria import ROTULOS
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.modelos import Auditoria, Usuario

POR_PAGINA = 50
FUSO = ZoneInfo("America/Sao_Paulo")


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def _inicio_do_dia(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=FUSO)


def listar(ctx: Contexto, de: date | None, ate: date | None, gravidade: str | None,
           busca: str | None, pagina: int) -> dict:
    filtros = []
    if de:
        filtros.append(Auditoria.criado_em >= _inicio_do_dia(de))
    if ate:
        filtros.append(Auditoria.criado_em < _inicio_do_dia(ate + timedelta(days=1)))
    if gravidade:
        filtros.append(Auditoria.gravidade == gravidade)
    if busca:
        termo = f"%{busca}%"
        eventos_por_rotulo = [e for e, r in ROTULOS.items() if _sem_acento(busca) in _sem_acento(r)]
        condicoes = [
            Auditoria.evento.ilike(termo),
            cast(Auditoria.detalhe, String).ilike(termo),
            Auditoria.ip.ilike(termo),
            Usuario.nome.ilike(termo),
        ]
        if eventos_por_rotulo:
            condicoes.append(Auditoria.evento.in_(eventos_por_rotulo))
        filtros.append(or_(*condicoes))

    base = select(Auditoria, Usuario.id, Usuario.nome).outerjoin(Usuario, Usuario.id == Auditoria.usuario_id)
    with em_conta(ctx.conta_id) as s:
        total = s.scalar(
            select(func.count()).select_from(
                select(Auditoria.id).outerjoin(Usuario, Usuario.id == Auditoria.usuario_id).where(*filtros).subquery()
            )
        )
        linhas = s.execute(
            base.where(*filtros)
            .order_by(Auditoria.criado_em.desc(), Auditoria.id.desc())
            .limit(POR_PAGINA)
            .offset((pagina - 1) * POR_PAGINA)
        ).all()
    itens = [
        {
            "id": a.id,
            "criado_em": a.criado_em,
            "evento": a.evento,
            "rotulo": ROTULOS.get(a.evento, a.evento),
            "gravidade": a.gravidade,
            "usuario": {"id": uid, "nome": nome} if uid is not None else None,
            "detalhe": a.detalhe,
            "ip": a.ip,
        }
        for a, uid, nome in linhas
    ]
    return {"itens": itens, "total": total, "pagina": pagina, "por_pagina": POR_PAGINA}
