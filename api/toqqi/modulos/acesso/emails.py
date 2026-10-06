"""Textos dos e-mails de acesso. Todos saem em nome da conta da pessoa e entram no registro de e-mails enviados
(`conta_id` + tipo): confirmar o e-mail e o aviso de "você já tem uma conta" (`confirmacao`, os dois do cadastro),
redefinir a senha (`senha`) e o pedido de acesso aprovado (`boas_vindas`)."""
from urllib.parse import quote

from toqqi.core.config import config
from toqqi.core.email import enviar

ROTULOS_PERFIL = {"admin": "Administrador", "gestor": "Gestor", "consulta": "Consulta"}
MAX_ADMINS_NO_EMAIL = 5


def _link(caminho: str, token: str | None = None) -> str:
    base = config().FRONTEND_URL.rstrip("/")
    return f"{base}/{caminho}" + (f"?token={quote(token)}" if token else "")


def _juntar(itens: list[str]) -> str:
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def lista_de_admins(admins: list[tuple[str, str]]) -> str:
    """"Ana Souza (ana@alfa.com.br) e Bruno Lima (bruno@alfa.com.br)"; com mais de 5, "… e mais 2 administradores"."""
    nomes = [f"{nome} ({email})" if email else nome for nome, email in admins[:MAX_ADMINS_NO_EMAIL]]
    resto = len(admins) - MAX_ADMINS_NO_EMAIL
    if resto > 0:
        nomes.append(f"mais {resto} administrador" + ("es" if resto > 1 else ""))
    return _juntar(nomes)


def confirmar_email(nome: str, email: str, token: str, conta_id: int | None = None) -> None:
    enviar(
        email,
        "Confirme seu e-mail no Toqqi",
        [
            f"Olá, {nome}!",
            "Falta só um passo: confirme seu e-mail para liberar o acesso ao Toqqi.",
            "O link vale por 24 horas. Se não foi você que pediu, pode ignorar esta mensagem.",
        ],
        ("Confirmar meu e-mail", _link("confirmar-email", token)),
        conta_id=conta_id, tipo="confirmacao",
    )


def ja_tem_conta(nome: str, email: str, conta_id: int | None = None) -> None:
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
        conta_id=conta_id, tipo="confirmacao",
    )


def redefinir_senha(nome: str, email: str, token: str, conta_id: int | None = None) -> None:
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
        conta_id=conta_id, tipo="senha",
    )


def acesso_aprovado(nome: str, email: str, aprovador: str, empresa: str, perfil: str, admins: list[tuple[str, str]],
                    conta_id: int) -> None:
    """Pedido de acesso aprovado em Equipe: a pessoa fica sabendo, com o perfil e quem administra a conta."""
    conta = f"à conta {empresa} no Toqqi" if empresa else "ao Toqqi"
    paragrafos = [
        f"Olá, {nome}!",
        f"{aprovador} aprovou seu acesso {conta}. Entre com {email} e a senha que você criou ao pedir acesso.",
        f"Você entra com o perfil {ROTULOS_PERFIL.get(perfil, perfil)}.",
    ]
    if len(admins) == 1:
        paragrafos.append(f"Quem administra a conta é {lista_de_admins(admins)}. Fale com essa pessoa para mudar seu "
                          "perfil ou pedir mais permissões. Você também encontra esse contato em Minha conta.")
    elif admins:
        paragrafos.append(f"Quem administra a conta: {lista_de_admins(admins)}. Fale com uma dessas pessoas para "
                          "mudar seu perfil ou pedir mais permissões. Você também encontra essa lista em Minha conta.")
    enviar(email, "Seu acesso ao Toqqi foi aprovado", paragrafos, ("Entrar no Toqqi", _link("entrar")),
           conta_id=conta_id, tipo="boas_vindas")
