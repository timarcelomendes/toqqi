"""Utilitários dos testes."""
import itertools
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

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


# ---- etapa 2 ----------------------------------------------------------------

API = "/api/v1"


_seq = itertools.count(1)


def criar_contato(client, h: dict, **campos) -> dict:
    corpo = {"nome": "Carlos Souza", "email": None, **campos}
    if corpo.get("email") is None and not corpo.get("telefone"):
        corpo["email"] = f"contato{next(_seq)}@cliente.com.br"
    r = client.post(f"{API}/contatos", headers=h, json=corpo)
    assert r.status_code == 201, r.text
    return r.json()


def criar_empresa(client, h: dict, nome: str = "Mercado Bom Preço", **campos) -> dict:
    r = client.post(f"{API}/empresas", headers=h, json={"nome": nome, **campos})
    assert r.status_code == 201, r.text
    return r.json()


def formularios(client, h: dict) -> dict:
    """{nome: formulario} dos formulários da conta."""
    r = client.get(f"{API}/formularios", headers=h)
    assert r.status_code == 200, r.text
    return {f["nome"]: f for f in r.json()}


def form_padrao(client, h: dict, uso: str = "nps") -> dict:
    f = next(f for f in formularios(client, h).values() if f[f"padrao_{uso}"])
    return client.get(f"{API}/formularios/{f['id']}", headers=h).json()


def criar_form(client, h: dict, perguntas: list, nome: str = "Pesquisa teste", **extra) -> dict:
    r = client.post(f"{API}/formularios", headers=h, json={"nome": nome, "perguntas": perguntas, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def link_pesquisa(client, h: dict, contato_id: int, **corpo) -> str:
    r = client.post(f"{API}/contatos/{contato_id}/link-pesquisa", headers=h, json=corpo)
    assert r.status_code == 201, r.text
    return r.json()["token"]


_ips = itertools.count(1)


def responder_link(client, codigo: str, respostas: dict, ip: str | None = None, **extra):
    """Responde o link público. Cada chamada vem de um IP diferente, a menos que `ip` seja dado
    (a mesma resposta do mesmo IP em 10 minutos não é gravada de novo)."""
    from fastapi.testclient import TestClient

    ip = ip or f"198.51.{next(_ips) // 250}.{next(_ips) % 250 + 1}"
    with TestClient(client.app, client=(ip, 50000)) as outro:
        return outro.post(f"{API}/publico/formularios/{codigo}/responder", json={"respostas": respostas, **extra})


def definir_plano(dono, conta_id: int, plano: str, situacao: str = "ativa") -> None:
    sql(dono, "update contas set plano = :p, situacao = :s where id = :c", p=plano, s=situacao, c=conta_id)


def encher_contatos(dono, conta_id: int, n: int, ativo: bool = True) -> None:
    """Insere n contatos direto no banco (rápido), respeitando o gatilho de limite."""
    sql(dono, """
        insert into contatos (conta_id, codigo, nome, email, ativo)
        select :c, (100000000 + g)::text, 'Contato ' || g, 'lote' || g || '@c' || :c || '.com.br', :a
          from generate_series(1, :n) g
    """, c=conta_id, n=n, a=ativo)


# ---- etapa 3a ---------------------------------------------------------------

def ligar_envios(client, h: dict, **extra) -> dict:
    r = client.put(f"{API}/envios/configuracao", headers=h, json={"envios_ativos": True, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def emails_para(para: str) -> list:
    return [m for m in caixa_memoria if m.para == para]


def token_do_convite(m) -> str:
    """Token do link /r/{token} de um e-mail de pesquisa."""
    return re.search(r"/r/([\w-]+)", m.texto).group(1)


def token_de_saida(m) -> str:
    return re.search(r"/sair/([\w.-]+)", m.texto).group(1)


def disparar(client, h: dict, ids: list, **extra):
    return client.post(f"{API}/envios/disparar", headers=h, json={"contato_ids": ids, **extra})


def fila(client, h: dict, **filtros) -> dict:
    """{contato_id: ContatoEnvio} da fila (com os filtros dados)."""
    r = client.get(f"{API}/envios/contatos", headers=h, params={"por_pagina": 200, **filtros})
    assert r.status_code == 200, r.text
    return {c["id"]: c for c in r.json()["itens"]}


def historico(client, h: dict, **filtros) -> list:
    r = client.get(f"{API}/envios/historico", headers=h, params=filtros)
    assert r.status_code == 200, r.text
    return r.json()["itens"]


def falhar_provedor(monkeypatch, erro, para: str | None = None) -> None:
    """Faz o provedor em memória levantar `erro` (para `para`, ou para todos)."""
    from toqqi.core.email import Memoria

    original = Memoria.enviar

    def enviar(self, m):
        if para is None or m.para == para:
            raise erro
        original(self, m)

    monkeypatch.setattr(Memoria, "enviar", enviar)


def erro_http(status: int):
    import httpx

    return httpx.HTTPStatusError("falha", request=httpx.Request("POST", "https://provedor.teste"),
                                 response=httpx.Response(status, text="detalhe técnico do provedor"))


FUSO = ZoneInfo("America/Sao_Paulo")


def segunda(hora: int = 11, minuto: int = 0, mais_dias: int = 0) -> datetime:
    """Próxima segunda-feira (ou hoje, se for segunda) às `hora`, em São Paulo, + `mais_dias`."""
    hoje = datetime.now(FUSO).date()
    d = hoje + timedelta(days=(7 - hoje.weekday()) % 7) + timedelta(days=mais_dias)
    return datetime.combine(d, time(hora, minuto), tzinfo=FUSO)


def fixar_relogio(monkeypatch, momento: datetime) -> None:
    from toqqi.core import relogio

    monkeypatch.setattr(relogio, "agora", lambda: momento)


def data_iso(d: date | datetime) -> str:
    return (d.date() if isinstance(d, datetime) else d).isoformat()
