"""Utilitários dos testes."""
import re

from toqqi.core.email import caixa_memoria

SENHA = "Senha@123"


# ---- utilitários ------------------------------------------------------------

def token_do_email(para: str, caminho: str) -> str:
    for m in reversed(caixa_memoria):
        if m.para == para:
            achou = re.search(rf"/{caminho}\?token=([\w\-%]+)", m.texto)
            if achou:
                return achou.group(1)
    raise AssertionError(f"nenhum e-mail com link {caminho} para {para}")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def cadastrar(client, email: str, empresa: str = "Empresa", nome: str = "Pessoa", senha: str = SENHA):
    r = client.post("/api/v1/auth/cadastro", json={
        "empresa": empresa, "nome": nome, "email": email, "senha": senha, "aceite_termos": True,
    })
    assert r.status_code == 201, r.text
    return r


def entrar(client, email: str, senha: str = SENHA, lembrar: bool = False, ua: str | None = None):
    headers = {"User-Agent": ua} if ua else {}
    return client.post("/api/v1/auth/entrar", json={"email": email, "senha": senha, "lembrar": lembrar},
                       headers=headers)


def conta_pronta(client, email: str, empresa: str = "Empresa") -> dict:
    """Cadastra, confirma o e-mail e entra. Devolve a Sessao + headers."""
    cadastrar(client, email, empresa=empresa)
    r = client.post("/api/v1/auth/confirmar-email", json={"token": token_do_email(email, "confirmar-email")})
    assert r.status_code == 200, r.text
    r = entrar(client, email)
    assert r.status_code == 200, r.text
    dados = r.json()
    dados["h"] = auth(dados["token"])
    return dados


def membro(client, admin_h: dict, email: str, perfil: str = "consulta", senha: str = SENHA) -> dict:
    """Admin cria um membro; o membro entra. Devolve a Sessao + headers."""
    r = client.post("/api/v1/equipe", headers=admin_h,
                    json={"nome": "Membro " + perfil, "email": email, "perfil": perfil, "senha": senha})
    assert r.status_code == 201, r.text
    r = entrar(client, email, senha)
    assert r.status_code == 200, r.text
    dados = r.json()
    dados["h"] = auth(dados["token"])
    return dados


def sql(dono, consulta: str, **params):
    """Executa SQL como dono em modo sistema (o dono também está sujeito ao RLS: FORCE)."""
    from sqlalchemy import text

    with dono.begin() as c:
        c.execute(text("select set_config('app.sistema', 'on', true)"))
        r = c.execute(text(consulta), params)
        return r.all() if r.returns_rows else r.rowcount
