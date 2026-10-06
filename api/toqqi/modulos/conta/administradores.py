"""Quem administra a conta (Minha conta › Administradores da conta): os administradores ativos, para qualquer perfil
saber a quem pedir outro perfil, mais permissões, um novo usuário ou a troca de plano."""
from sqlalchemy import select

from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.modelos import Usuario


def listar(ctx: Contexto) -> list[dict]:
    """[{id, nome, email, cargo, voce}] em ordem de nome; `voce`: é quem pergunta."""
    with em_conta(ctx.conta_id) as s:
        admins = s.scalars(
            select(Usuario)
            .where(Usuario.conta_id == ctx.conta_id, Usuario.perfil == "admin", Usuario.situacao == "ativo")
            .order_by(Usuario.nome, Usuario.id)
        ).all()
        return [{"id": u.id, "nome": u.nome, "email": u.email, "cargo": u.cargo, "voce": u.id == ctx.usuario_id}
                for u in admins]
