"""Sua marca nas pesquisas (etapa 5h, §1): a cor da conta e se ela já tem logo.

A cor fica em `config_envios.email_cor` (a cor dos e-mails, #RRGGBB em maiúsculas) e é a cor dos formulários novos
(`formularios.servico.criar`). Ao escolher a cor, os formulários da conta (não arquivados) que ainda estão na cor dos
modelos (`TEMA_PADRAO["cor"]`, #1f6feb, sem diferenciar maiúsculas) passam para ela; os que já têm outra cor ficam como
estão. O logo é o da conta (`PUT /conta/logo`, que já existia).
"""
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.modelos import ConfigEnvios, Formulario
from toqqi.modulos.envios import configuracao as config_envios
from toqqi.modulos.formularios.modelos import TEMA_PADRAO
from toqqi.modulos.imagens import servico as imagens

COR_DOS_MODELOS = TEMA_PADRAO["cor"].lower()


def cor_da_conta(s: Session) -> str | None:
    """A cor da marca (`email_cor`) da conta da transação, ou None."""
    return s.scalar(select(ConfigEnvios.email_cor))


def obter(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return {"cor": cor_da_conta(s), "tem_logo": imagens.logo_da_conta(s, ctx.conta_id) is not None}


def salvar(ctx: Contexto, cor: str) -> dict:
    """`cor` já validada (#RRGGBB em maiúsculas). Auditoria só quando algo mudou."""
    with em_conta(ctx.conta_id) as s:
        cfg = config_envios.obter(s, travar=True)
        antes = cfg.email_cor
        cfg.email_cor = cor
        if antes != cor:
            cfg.atualizado_em = relogio.agora()
        atualizados = s.execute(
            update(Formulario)
            .where(Formulario.conta_id == ctx.conta_id, Formulario.arquivado.is_(False),
                   func.lower(Formulario.tema["cor"].astext) == COR_DOS_MODELOS)
            .values(tema=Formulario.tema.op("||")(func.jsonb_build_object("cor", cor.lower())),
                    atualizado_em=func.now())
            .execution_options(synchronize_session=False)).rowcount
        if antes != cor or atualizados:
            registrar(s, "marca_alterada", "info", {"cor": cor, "formularios_atualizados": atualizados},
                      usuario_id=ctx.usuario_id)
        return {"cor": cor, "formularios_atualizados": atualizados}
