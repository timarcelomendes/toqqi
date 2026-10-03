"""Avisos por e-mail aos administradores ativos da conta (webhook desativado, franquia do WhatsApp...), enviados
depois do commit. Entram no registro de e-mails enviados da conta com o tipo `aviso`."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from toqqi.core import email
from toqqi.core.db import apos_commit
from toqqi.modelos import Usuario


def admins_a_avisar(s: Session, conta_id: int) -> list[str]:
    """E-mails dos administradores ativos da conta: quem recebe os avisos."""
    return list(s.scalars(select(Usuario.email).where(Usuario.conta_id == conta_id, Usuario.perfil == "admin",
                                                      Usuario.situacao == "ativo", Usuario.email != "")))


def avisar_admins(s: Session, conta_id: int, assunto: str, paragrafos: list[str],
                  botao: tuple[str, str] | None = None) -> None:
    para = admins_a_avisar(s, conta_id)

    def enviar() -> None:
        for endereco in para:
            email.enviar(endereco, assunto, paragrafos, botao, conta_id=conta_id, tipo="aviso")

    apos_commit(s, enviar)
