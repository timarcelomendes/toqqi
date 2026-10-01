"""Utilitários dos testes."""
import itertools
import json
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


# ---- etapa 3b ---------------------------------------------------------------

APP_SECRET = "segredo-do-app-da-meta"
VERIFY_TOKEN = "token-de-verificacao"
PNID = "1234567890"
WABA = "9876543210"
TOKEN_META = "EAAGtokenpermanente" + "x" * 40


def gerar_chave(client, h: dict) -> str:
    r = client.post(f"{API}/integracoes/chave", headers=h)
    assert r.status_code == 201, r.text
    return r.json()["chave"]


def evento(client, chave: str, rota: str = "pesquisas", **corpo):
    return client.post(f"{API}/integracao/{rota}", headers={"X-Api-Key": chave}, json=corpo)


def modelo_meta(**extra) -> dict:
    """Modelo (template) aprovado como a Graph API devolve."""
    return {
        "name": "pesquisa_toqqi", "language": "pt_BR", "status": "APPROVED", "category": "UTILITY", "id": "1",
        "components": [
            {"type": "BODY", "text": "Olá, {{1}}! A {{2}} quer saber como foi {{3}}. Leva 1 minuto."},
            {"type": "BUTTONS", "buttons": [{"type": "QUICK_REPLY", "text": "Não quero receber"},
                                            {"type": "URL", "text": "Responder", "url": "http://app.teste/r/{{1}}"}]},
        ],
        **extra,
    }


class MetaFalsa:
    """Dublê da Graph API (usado com httpx.MockTransport)."""

    def __init__(self):
        self.pedidos = []
        self.mensagens = []          # corpos dos POST /{phone_number_id}/messages
        self.modelos = [modelo_meta()]
        self.erro_envio = None       # (status, {"code": ..., "message": ...})
        self.erro_numero = None
        self._n = 0

    def __call__(self, request):
        import httpx

        self.pedidos.append(request)
        partes = request.url.path.strip("/").split("/")[1:]
        if request.method == "POST" and partes[-1] == "messages":
            self.mensagens.append(json.loads(request.content))
            if self.erro_envio:
                status, erro = self.erro_envio
                return httpx.Response(status, json={"error": erro})
            self._n += 1
            return httpx.Response(200, json={"messages": [{"id": f"wamid.{self._n}"}]})
        if partes[-1] == "message_templates":
            return httpx.Response(200, json={"data": self.modelos})
        if self.erro_numero:
            status, erro = self.erro_numero
            return httpx.Response(status, json={"error": erro})
        return httpx.Response(200, json={"display_phone_number": "+55 11 4000-1234",
                                         "verified_name": "Alfa Distribuidora", "id": partes[0]})


def conectar_whatsapp(client, h: dict, pnid: str = PNID, **extra):
    corpo = {"phone_number_id": pnid, "waba_id": WABA, "token": TOKEN_META, "modelo_nome": "pesquisa_toqqi",
             "modelo_idioma": "pt_BR", **extra}
    return client.put(f"{API}/integracoes/whatsapp", headers=h, json=corpo)


def aviso_meta(client, corpo: dict, segredo: str = APP_SECRET):
    """POST assinado no webhook público da Meta."""
    import hashlib
    import hmac

    bruto = json.dumps(corpo).encode()
    assinatura = "sha256=" + hmac.new(segredo.encode(), bruto, hashlib.sha256).hexdigest()
    return client.post(f"{API}/publico/whatsapp/webhook", content=bruto,
                       headers={"Content-Type": "application/json", "X-Hub-Signature-256": assinatura})


def _mudanca(pnid: str, valor: dict) -> dict:
    return {"object": "whatsapp_business_account", "entry": [{"id": WABA, "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"display_phone_number": "551140001234", "phone_number_id": pnid},
        **valor}}]}]}


def aviso_status(wamid: str, status: str, codigo: int | None = None, pnid: str = PNID) -> dict:
    st = {"id": wamid, "status": status, "timestamp": "1700000000", "recipient_id": "5511987654321"}
    if codigo:
        st["errors"] = [{"code": codigo, "title": "erro"}]
    return _mudanca(pnid, {"statuses": [st]})


def aviso_mensagem(de: str, texto: str, pnid: str = PNID) -> dict:
    return _mudanca(pnid, {"contacts": [{"wa_id": de, "profile": {"name": "Cliente"}}], "messages": [
        {"from": de, "id": "wamid.entrada", "timestamp": "1700000000", "type": "text", "text": {"body": texto}}]})


class DestinoFalso:
    """Substitui core.rede.enviar_post: registra cada POST e responde com `status`."""

    def __init__(self, status: int = 200):
        self.status = status
        self.recebidos = []

    def __call__(self, url, ip, host, corpo, cabecalhos=None):
        import httpx

        self.recebidos.append({"url": url, "ip": ip, "host": host, "corpo": corpo, "cabecalhos": cabecalhos or {}})
        return httpx.Response(self.status, text="ok")


# ---- etapa 4a ---------------------------------------------------------------

def registrar_resposta(client, h: dict, contato_id: int, nota: int, **extra):
    """POST /respostas (resposta registrada à mão)."""
    return client.post(f"{API}/respostas", headers=h, json={"contato_id": contato_id, "nota": nota, **extra})


def responder_convite(client, h: dict, contato_id: int, nota: int, comentario: str | None = None,
                      formulario: dict | None = None, **convite) -> dict:
    """Cria um link de pesquisa para o contato (formulário padrão de NPS, se não vier outro) e responde."""
    f = formulario or form_padrao(client, h)
    token = link_pesquisa(client, h, contato_id, formulario_id=f["id"], **convite)
    respostas = {f["perguntas"][0]["id"]: nota}
    if comentario:
        respostas[f["perguntas"][1]["id"]] = comentario
    r = client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": respostas})
    assert r.status_code == 201, r.text
    return r.json()


def lista_respostas(client, h: dict, **filtros) -> dict:
    r = client.get(f"{API}/respostas", headers=h, params={"por_pagina": 200, **filtros})
    assert r.status_code == 200, r.text
    return r.json()


def quadro(client, h: dict, **filtros) -> dict:
    r = client.get(f"{API}/acoes/quadro", headers=h, params=filtros)
    assert r.status_code == 200, r.text
    return r.json()


def criar_responsavel(client, h: dict, nome: str = "Rita Gomes", **campos) -> dict:
    r = client.post(f"{API}/responsaveis", headers=h, json={"nome": nome, **campos})
    assert r.status_code == 201, r.text
    return r.json()


def perfil_id(client, h: dict, nome: str = "Decisor") -> int:
    perfis = client.get(f"{API}/cadastros/perfis", headers=h).json()
    return next(p["id"] for p in perfis if p["nome"] == nome)


# ---- dados da empresa e imagens -----------------------------------------------

def png(cor: int = 0) -> bytes:
    """PNG 1x1 de verdade (a cor muda os bytes, e com eles o sha256)."""
    import struct
    import zlib

    def bloco(tipo: bytes, dados: bytes) -> bytes:
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados))

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    idat = zlib.compress(b"\x00" + bytes([cor, cor, cor, 255]))
    return b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", ihdr) + bloco(b"IDAT", idat) + bloco(b"IEND", b"")


def caminho_imagem(url: str) -> str:
    """URL pública de uma imagem da plataforma → caminho para o cliente de teste."""
    from toqqi.core.config import config

    prefixo = config().API_PUBLIC_URL.rstrip("/")
    assert url.startswith(prefixo + "/api/v1/publico/imagens/"), url
    return url[len(prefixo):]
