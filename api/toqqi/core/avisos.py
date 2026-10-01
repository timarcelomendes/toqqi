"""Avisos por e-mail aos administradores da conta da transação, enviados depois do commit."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from toqqi.core import email
from toqqi.core.db import apos_commit
from toqqi.modelos import Usuario


def avisar_admins(s: Session, assunto: str, paragrafos: list[str], botao: tuple[str, str] | None = None) -> None:
    para = s.scalars(select(Usuario.email).where(Usuario.perfil == "admin", Usuario.situacao == "ativo")).all()

    def enviar() -> None:
        for endereco in para:
            email.enviar(endereco, assunto, paragrafos, botao)

    apos_commit(s, enviar)
