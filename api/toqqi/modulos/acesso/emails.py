"""Textos dos e-mails de acesso."""
from urllib.parse import quote

from toqqi.core.config import config
from toqqi.core.email import enviar


def _link(caminho: str, token: str | None = None) -> str:
    base = config().FRONTEND_URL.rstrip("/")
    return f"{base}/{caminho}" + (f"?token={quote(token)}" if token else "")


def confirmar_email(nome: str, email: str, token: str) -> None:
    enviar(
        email,
        "Confirme seu e-mail no Toqqi",
        [
            f"Olá, {nome}!",
            "Falta só um passo: confirme seu e-mail para liberar o acesso ao Toqqi.",
            "O link vale por 24 horas. Se não foi você que pediu, pode ignorar esta mensagem.",
        ],
        ("Confirmar meu e-mail", _link("confirmar-email", token)),
    )


def ja_tem_conta(nome: str, email: str) -> None:
    enviar(
        email,
        "Você já tem uma conta no Toqqi",
        [
            f"Olá, {nome}!",
            "Alguém tentou criar uma conta no Toqqi com este e-mail, mas ele já está cadastrado.",
            "Se foi você, é só entrar. Se esqueceu a senha, use a opção “Esqueci minha senha” na tela de entrada.",
            "Se não foi você, pode ignorar esta mensagem: nada foi alterado.",
        ],
        ("Entrar no Toqqi", _link("entrar")),
    )


def redefinir_senha(nome: str, email: str, token: str) -> None:
    enviar(
        email,
        "Redefina sua senha do Toqqi",
        [
            f"Olá, {nome}!",
            "Recebemos um pedido para criar uma nova senha para sua conta.",
            "O link vale por 30 minutos e só pode ser usado uma vez. "
            "Se não foi você que pediu, ignore esta mensagem: sua senha continua a mesma.",
        ],
        ("Criar nova senha", _link("redefinir-senha", token)),
    )
