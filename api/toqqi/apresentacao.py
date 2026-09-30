"""Conversão de modelos para o formato JSON do contrato."""
from toqqi.core.config import config
from toqqi.modelos import Conta, Usuario


def eh_superadmin(email: str) -> bool:
    return email.lower() in config().superadmins


def usuario_json(u: Usuario) -> dict:
    return {
        "id": u.id,
        "nome": u.nome,
        "email": u.email,
        "cargo": u.cargo,
        "perfil": u.perfil,
        "situacao": u.situacao,
        "email_confirmado": u.email_confirmado,
        "ultimo_acesso": u.ultimo_acesso,
        "superadmin": eh_superadmin(u.email),
    }


def conta_json(c: Conta) -> dict:
    return {"id": c.id, "nome": c.nome, "plano": c.plano, "situacao": c.situacao, "teste_ate": c.teste_ate}
