"""Conversão de modelos para o formato JSON do contrato."""
from toqqi.core.config import config
from toqqi.modelos import Conta, Usuario
from toqqi.modulos.assinatura.regras import cobranca_json
from toqqi.modulos.ia.regras import ia_ativa


def eh_superadmin(email: str) -> bool:
    return email.lower() in config().superadmins


def usuario_json(u: Usuario, preferencias: bool = False) -> dict:
    """`preferencias` (o próprio usuário: /eu e login): e-mails do Toqqi que ele recebe."""
    dados = {
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
    if preferencias:
        dados.update(recebe_resumo_semanal=u.recebe_resumo_semanal, recebe_alertas=u.recebe_alertas)
    return dados


def conta_json(c: Conta) -> dict:
    """`cobranca` (etapa 5a): {liberada, pago_ate, atrasada_desde, pausa_em, aviso} — regras em assinatura.regras."""
    return {"id": c.id, "nome": c.nome, "plano": c.plano, "situacao": c.situacao, "teste_ate": c.teste_ate,
            "ia_ativa": ia_ativa(c), "cobranca": cobranca_json(c)}
