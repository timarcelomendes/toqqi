"""Utilitários dos testes."""
import itertools
import json
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
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


# ---- etapa 5a: assinatura e Asaas -----------------------------------------------------

CHAVE_ASAAS = "$aact_hmlg_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OjAwMDAwMDAwMDA6OiRhYWNoXzAwMDA="
TOKEN_WEBHOOK = "token-do-webhook-do-asaas-0123456789abcdef"
CNPJ_COBRANCA = "11222333000181"
CPF_COBRANCA = "52998224725"
DADOS_COBRANCA = {"razao_social": "Alfa Distribuidora Ltda", "documento": "11.222.333/0001-81",
                  "email_cobranca": "Financeiro@Alfa.com.br", "telefone": "(11) 98765-4321"}


class AsaasFalso:
    """O Asaas falso de `scripts/asaas_falso.py` em memória, atrás do transporte do adaptador (httpx.MockTransport).
    - `pedidos`: o que chegou (httpx.Request);
    - `falhar(resposta, metodo, trecho, depois, pular)`: a próxima chamada que bate (método e trecho do caminho; com
      `pular=n`, a n+1ª) recebe `resposta` (httpx.Response ou exceção a levantar); com `depois=True`, o Asaas falso faz
      o pedido antes (a resposta é que se perde, como num tempo esgotado depois de o Asaas gravar);
    - os webhooks que ele mandaria ficam em `avisos`; `entregar()` manda os pendentes para a API de teste."""

    def __init__(self, client):
        from fastapi.testclient import TestClient
        from scripts import asaas_falso

        from toqqi.core import relogio

        self.client = client
        self.avisos: list[dict] = []
        self.pedidos: list = []
        self.falhas: list = []
        self.app = asaas_falso.criar_app(webhook_url="http://api.teste/api/v1/asaas/webhook",
                                         webhook_token=TOKEN_WEBHOOK, url_publica="https://asaas.teste",
                                         enviar=self._guardar, hoje=lambda: relogio.hoje())
        self.http = TestClient(self.app)

    def _guardar(self, url, token, corpo) -> int:
        self.avisos.append(corpo)
        return 200

    def __call__(self, request):
        self.pedidos.append(request)
        for i, falha in enumerate(self.falhas):
            metodo, trecho, resposta, depois, pular = falha
            if (metodo is None or metodo == request.method) and trecho in request.url.path:
                if pular:
                    falha[4] -= 1
                    break
                del self.falhas[i]
                if depois:
                    self._repassar(request)
                if isinstance(resposta, Exception):
                    raise resposta
                return resposta
        return self._repassar(request)

    def _repassar(self, request):
        import httpx

        cabecalhos = {k: v for k, v in request.headers.items() if k in ("access_token", "user-agent", "content-type")}
        r = self.http.request(request.method, request.url.path, params=request.url.params, content=request.content,
                              headers=cabecalhos)
        return httpx.Response(r.status_code, content=r.content, headers={"content-type": "application/json"})

    def falhar(self, resposta, metodo: str | None = None, trecho: str = "", depois: bool = False,
               pular: int = 0) -> None:
        self.falhas.append([metodo, trecho, resposta, depois, pular])

    @property
    def dados(self) -> dict:
        return self.app.state.dados

    def vivas(self) -> list[dict]:
        """Assinaturas que seguem cobrando (não removidas nem INACTIVE/EXPIRED)."""
        return [a for a in self.dados["assinaturas"].values()
                if not a["deleted"] and a["status"] not in ("INACTIVE", "EXPIRED")]

    def assinatura(self) -> dict:
        """A única assinatura não removida."""
        vivas = [a for a in self.dados["assinaturas"].values() if not a["deleted"]]
        assert len(vivas) == 1, vivas
        return vivas[0]

    def criar_direto(self, conta_id: int, valor: float = 349.0, vencimento: str = "2026-10-15",
                     cliente: str | None = None) -> dict:
        """Assinatura criada no Asaas sem a API saber (o pedido esgotou o tempo ou o processo caiu antes de gravar),
        com a referência da conta. Usa o cliente dado ou o primeiro da conta (criando um, se não houver)."""
        ref = f"toqqi-conta-{conta_id}"
        if cliente is None:
            cliente = next((c["id"] for c in self.dados["clientes"].values() if c.get("externalReference") == ref),
                           None)
        if cliente is None:
            r = self.http.post("/v3/customers", headers={"access_token": "x"}, json={
                "name": "Alfa Distribuidora Ltda", "cpfCnpj": CNPJ_COBRANCA, "email": "financeiro@alfa.com.br",
                "mobilePhone": "11987654321", "phone": "", "externalReference": ref})
            assert r.status_code == 200, r.text
            cliente = r.json()["id"]
        r = self.http.post("/v3/subscriptions", headers={"access_token": "x"}, json={
            "customer": cliente, "billingType": "UNDEFINED", "value": valor, "nextDueDate": vencimento,
            "cycle": "MONTHLY", "description": "Toqqi", "externalReference": ref})
        assert r.status_code == 200, r.text
        return r.json()

    def cobrancas(self, assinatura_id: str | None = None) -> list[dict]:
        """Cobranças (não removidas) da assinatura, da mais antiga para a mais nova."""
        sid = assinatura_id or self.assinatura()["id"]
        return sorted((p for p in self.dados["cobrancas"].values() if p["subscription"] == sid and not p["deleted"]),
                      key=lambda p: (p["dueDate"], p["id"]))

    def simular(self, acao: str, alvo: str, entregar: bool = True, **params) -> dict:
        r = self.http.post(f"/simular/{acao}/{alvo}", params=params)
        assert r.status_code == 200, r.text
        if entregar:
            self.entregar()
        return r.json()

    def entregar(self) -> list:
        """Manda para a API os webhooks guardados (na ordem) e devolve as respostas."""
        respostas = [aviso_asaas(self.client, a) for a in self.avisos]
        self.avisos.clear()
        return respostas


def aviso_asaas(client, corpo: dict, token: str = TOKEN_WEBHOOK):
    """POST no webhook do Asaas com o cabeçalho do token."""
    return client.post(f"{API}/asaas/webhook", json=corpo, headers={"asaas-access-token": token})


def assinar(client, h: dict, plano: str = "profissional", **dados):
    return client.post(f"{API}/assinatura", headers=h, json={"plano": plano, **DADOS_COBRANCA, **dados})


def situacao_conta(dono, conta_id: int) -> tuple:
    """(situacao, pago_ate, atrasada_desde, primeiro_vencimento) direto do banco."""
    return tuple(sql(dono, "select situacao, pago_ate, atrasada_desde, primeiro_vencimento from contas where id = :c",
                     c=conta_id)[0])


# ---- etapa 5b: Ajuda e assistente -----------------------------------------------------

AJUDA_EXEMPLO = Path(__file__).with_name("dados") / "ajuda_exemplo.json"


def perguntar(client, h: dict, pergunta: str = "Como importo meus contatos?", historico: list | None = None):
    corpo = {"pergunta": pergunta}
    if historico is not None:
        corpo["historico"] = historico
    return client.post(f"{API}/assistente/perguntar", headers=h, json=corpo)


def contexto_de(sessao: dict, permissoes: list[str] | None = None):
    """Contexto de quem entrou (`conta_pronta`/`membro`), para chamar os serviços direto. Sem `permissoes`, as do
    perfil padrão (admin: todas)."""
    import uuid

    from toqqi.core.deps import Contexto
    from toqqi.core.permissoes import PADRAO, TODAS

    perfil = sessao["usuario"]["perfil"]
    if permissoes is None:
        permissoes = list(TODAS) if perfil == "admin" else list(PADRAO[perfil])
    return Contexto(usuario_id=sessao["usuario"]["id"], conta_id=sessao["conta"]["id"], sessao_id=uuid.uuid4(),
                    email=sessao["usuario"]["email"], perfil=perfil, superadmin=False, permissoes=permissoes)


def cota_do_mes(dono, conta_id: int, mes: date | None = None) -> tuple[int, int, int]:
    """(cota_usada, cota_tokens_entrada, cota_tokens_saida) do mês (padrão: o atual, São Paulo)."""
    from toqqi.core import relogio

    mes = mes or relogio.hoje().replace(day=1)
    linhas = sql(dono, "select cota_usada, cota_tokens_entrada, cota_tokens_saida from ia_uso_mensal "
                       "where conta_id = :c and mes = :m", c=conta_id, m=mes)
    return tuple(linhas[0]) if linhas else (0, 0, 0)


def usar_cota(dono, conta_id: int, usadas: int, mes: date | None = None) -> None:
    from toqqi.core import relogio

    sql(dono, "insert into ia_uso_mensal (conta_id, mes, cota_usada) values (:c, :m, :u) on conflict (conta_id, mes) "
              "do update set cota_usada = excluded.cota_usada", c=conta_id, m=mes or relogio.hoje().replace(day=1),
        u=usadas)


def inserir_resposta(dono, conta_id: int, formulario_id: int, contato: dict | None, nota: int, quando: date,
                     tipo: str = "nps", comentario: str = "", arquivada: bool = False, empresa_id: int | None = None
                     ) -> int:
    """Resposta direto no banco (dono, modo sistema), ao meio-dia (São Paulo) de `quando`."""
    from toqqi.modulos.formularios.validacao import grupo_da_nota
    from toqqi.modulos.respostas.registro import temas_da_resposta

    if empresa_id is None and contato and contato.get("empresa"):
        empresa_id = contato["empresa"]["id"]
    (rid,), = sql(dono, """
        insert into respostas (conta_id, formulario_id, contato_id, empresa_id, canal, origem, nota, tipo_nota,
                               grupo, comentario, comentario_cliente, temas, respondida_em, arquivada)
        values (:conta, :f, :c, :e, 'manual', 'manual', :n, :t, :g, :com, :com, :temas, :quando, :arq)
        returning id
    """, conta=conta_id, f=formulario_id, c=contato["id"] if contato else None, e=empresa_id, n=nota, t=tipo,
        g=grupo_da_nota(tipo, nota), com=comentario, temas=temas_da_resposta(comentario),
        quando=datetime.combine(quando, time(12), tzinfo=FUSO), arq=arquivada)
    return rid


# ---- etapa 5c: crescimento ------------------------------------------------------------

def ligar_indicacoes(client, h: dict, **extra) -> dict:
    r = client.put(f"{API}/crescimento/configuracao", headers=h, json={"indicacoes_ativas": True, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def convite_respondido(client, h: dict, contato_id: int, nota: int, formulario: dict | None = None
                       ) -> tuple[str, dict]:
    """Link de pesquisa do contato (formulário padrão de NPS, se não vier outro) respondido com `nota` na pergunta
    principal. Devolve (token do convite, corpo da resposta da página pública)."""
    f = formulario or form_padrao(client, h)
    token = link_pesquisa(client, h, contato_id, formulario_id=f["id"])
    r = client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {f["perguntas"][0]["id"]: nota}})
    assert r.status_code == 201, r.text
    return token, r.json()


def indicar(client, token: str, **campos):
    """POST da indicação pública (com a confirmação marcada, se não vier outra)."""
    corpo = {"nome": "João Silva", "empresa": "Padaria Real", "telefone": "(11) 98765-4321", "confirmo": True,
             **campos}
    return client.post(f"{API}/publico/convites/{token}/indicacoes", json=corpo)


def indicacoes(client, h: dict, **filtros) -> dict:
    r = client.get(f"{API}/crescimento/indicacoes", headers=h, params={"por_pagina": 200, **filtros})
    assert r.status_code == 200, r.text
    return r.json()


# ---- etapa 5d: IA sob demanda e passos das ações -----------------------------------------

SEM_PASSOS = {"prontas": 0, "falharam": 0, "limite": 0}


def sem_passos(dono, conta_id: int) -> None:
    """Desliga os passos da IA nas ações da conta direto no banco (sem auditoria): para os testes de outras partes
    da IA (análise por resposta) não contarem o teto gasto pelos passos."""
    sql(dono, "update contas set ia_passos_acoes = false where id = :c", c=conta_id)


def tarefa_ia() -> dict:
    """Tarefa `ia` sem os passos (que precisam estar parados): {analisadas, falharam, limite}."""
    from toqqi import tarefas

    r = tarefas.executar("ia")["ia"]
    assert r.pop("passos") == SEM_PASSOS
    return r


def estado_ia(client, h: dict, tipo: str = "painel", **filtros):
    """GET /painel/resumo-ia (tipo painel) ou /relatorios/parecer-ia (tipo relatorios)."""
    caminho = "painel/resumo-ia" if tipo == "painel" else "relatorios/parecer-ia"
    return client.get(f"{API}/{caminho}", headers=h, params=filtros)


def gerar_ia(client, h: dict, tipo: str = "painel", **corpo):
    """POST /painel/resumo-ia (tipo painel) ou /relatorios/parecer-ia (tipo relatorios), com os filtros no corpo."""
    caminho = "painel/resumo-ia" if tipo == "painel" else "relatorios/parecer-ia"
    return client.post(f"{API}/{caminho}", headers=h, json=corpo)


def acao(client, h: dict, acao_id: int) -> dict:
    r = client.get(f"{API}/acoes/{acao_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def passos_da_acao(dono, acao_id: int) -> dict:
    """{situacao, passos, tentativas, reservada, em} direto do banco."""
    (x,) = sql(dono, "select ia_passos_situacao, ia_passos, ia_passos_tentativas, ia_passos_reservada_em, "
                     "ia_passos_em from acoes where id = :a", a=acao_id)
    return dict(zip(("situacao", "passos", "tentativas", "reservada", "em"), x, strict=True))


def teto_do_mes(dono, conta_id: int) -> tuple[int, int, int]:
    """(analises, tokens_entrada, tokens_saida) do teto de segurança no mês atual (São Paulo)."""
    from toqqi.core import relogio

    linhas = sql(dono, "select analises, tokens_entrada, tokens_saida from ia_uso_mensal where conta_id = :c "
                       "and mes = :m", c=conta_id, m=relogio.hoje().replace(day=1))
    return tuple(linhas[0]) if linhas else (0, 0, 0)
