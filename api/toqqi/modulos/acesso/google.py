"""Entrar com o Google (pedido do Marcelo em 08/10/2026, 10h56: "implementar login com google"). Contrato:
docs/api-login-google.md.

O site mostra o botão oficial do Google (Google Identity Services) e manda à API o token de identidade (um JWT assinado
pelo Google) que o botão devolve. Aqui ele é conferido com as chaves públicas do Google: assinatura RS256, emissor
accounts.google.com, destinatário igual a GOOGLE_CLIENT_ID e validade (com 60 s de tolerância de relógio). Só vale
e-mail verificado pelo Google. Não há segredo do cliente nem token do Google guardado: do Google, o Toqqi guarda só o
`sub` (o identificador da conta do Google) no usuário, na primeira entrada.

Quem ainda não tem conta recebe um token de cadastro (15 minutos, assinado com uma chave derivada do JWT_SECRET, que não
vale como sessão) para terminar o cadastro com o nome da empresa e o aceite dos termos, sem precisar do Google de novo.
"""
import hashlib
import hmac
import re
import threading
import time

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from toqqi.core.config import config
from toqqi.core.errors import AppError

EMISSORES = ("accounts.google.com", "https://accounts.google.com")
TOLERANCIA = 60  # segundos de diferença de relógio aceitos
CACHE_PADRAO = 3600  # sem Cache-Control, as chaves valem 1 hora
CACHE_MAXIMO = 86400
INTERVALO_MINIMO = 60  # chave desconhecida não baixa as chaves de novo mais de uma vez por minuto
VALIDADE_CADASTRO = 15 * 60
MAX_NOME = 120

MSG_INVALIDO = "Não deu para confirmar sua conta do Google. Tente de novo."
MSG_FORA = "O Google não respondeu agora. Tente de novo em instantes ou entre com e-mail e senha."
MSG_NAO_VERIFICADO = "O Google não confirmou este e-mail. Entre com e-mail e senha."
MSG_DESLIGADO = "Entrar com o Google não está disponível."
MSG_CADASTRO_VENCIDO = "O tempo para terminar o cadastro acabou. Clique em “Continuar com o Google” de novo."

transporte: httpx.BaseTransport | None = None  # testes: as chaves vêm de um transporte falso
_trava = threading.Lock()
_cache: dict = {"chaves": {}, "ate": 0.0, "baixadas_em": -INTERVALO_MINIMO}


def client_id() -> str:
    return config().GOOGLE_CLIENT_ID.strip()


def limpar_cache() -> None:
    with _trava:
        _cache.update(chaves={}, ate=0.0, baixadas_em=-INTERVALO_MINIMO)


def _max_age(cache_control: str) -> int:
    m = re.search(r"max-age=(\d+)", cache_control or "")
    return min(int(m.group(1)), CACHE_MAXIMO) if m else CACHE_PADRAO


def _baixar() -> None:
    """Baixa as chaves públicas do Google (JWKS) para o cache. Falhou → 503 (e o cache fica como estava)."""
    try:
        with httpx.Client(timeout=10, transport=transporte, follow_redirects=False) as c:
            r = c.get(config().GOOGLE_CHAVES_URL)
            r.raise_for_status()
            dados = r.json()
        chaves = {k["kid"]: RSAAlgorithm.from_jwk(k) for k in dados.get("keys", [])
                  if isinstance(k, dict) and k.get("kty") == "RSA" and k.get("kid")}
    except (httpx.HTTPError, ValueError, KeyError, TypeError, jwt.PyJWTError):
        raise AppError(503, "google_fora_do_ar", MSG_FORA)
    agora = time.monotonic()
    _cache.update(chaves=chaves, ate=agora + _max_age(r.headers.get("cache-control", "")), baixadas_em=agora)


def _chave(kid: str):
    with _trava:
        agora = time.monotonic()
        vencido = agora >= _cache["ate"]
        # O Google troca as chaves de tempos em tempos: chave desconhecida baixa de novo (no máximo 1 vez por minuto)
        desconhecida = kid not in _cache["chaves"] and agora - _cache["baixadas_em"] >= INTERVALO_MINIMO
        if vencido or desconhecida:
            _baixar()
        return _cache["chaves"].get(kid)


def _invalido() -> AppError:
    return AppError(401, "google_invalido", MSG_INVALIDO)


def verificar(credencial: str) -> dict:
    """Confere o token de identidade do Google → {sub, email, nome}. 404 sem GOOGLE_CLIENT_ID; 401 token inválido;
    403 e-mail não verificado; 503 sem as chaves do Google."""
    cid = client_id()
    if not cid:
        raise AppError(404, "google_desligado", MSG_DESLIGADO)
    try:
        cabecalho = jwt.get_unverified_header(credencial)
    except jwt.PyJWTError:
        raise _invalido()
    if cabecalho.get("alg") != "RS256" or not isinstance(cabecalho.get("kid"), str):
        raise _invalido()
    chave = _chave(cabecalho["kid"])
    if chave is None:
        raise _invalido()
    try:
        dados = jwt.decode(credencial, chave, algorithms=["RS256"], audience=cid, issuer=EMISSORES, leeway=TOLERANCIA,
                           options={"require": ["exp", "iat", "iss", "aud", "sub"]})
    except jwt.PyJWTError:
        raise _invalido()
    email = str(dados.get("email") or "").strip().lower()
    if not email or dados.get("email_verified") not in (True, "true"):
        raise AppError(403, "google_email_nao_verificado", MSG_NAO_VERIFICADO)
    sub = str(dados["sub"])
    if not sub or len(sub) > 255:
        raise _invalido()
    return {"sub": sub, "email": email, "nome": " ".join(str(dados.get("name") or "").split())[:MAX_NOME]}


# ---- token de cadastro (quem entrou pelo Google e ainda não tem conta) --------------------------------------------

def _chave_cadastro() -> bytes:
    """Chave própria do token de cadastro (derivada do JWT_SECRET): ele nunca vale como token de sessão."""
    return hmac.new(config().JWT_SECRET.encode(), b"toqqi|cadastro-google", hashlib.sha256).digest()


def token_cadastro(g: dict) -> str:
    agora = int(time.time())
    return jwt.encode({"sub": g["sub"], "email": g["email"], "nome": g["nome"], "fin": "cadastro_google",
                       "iat": agora, "exp": agora + VALIDADE_CADASTRO}, _chave_cadastro(), algorithm="HS256")


def ler_cadastro(token: str) -> dict:
    """{sub, email, nome} do token de cadastro; 400 `cadastro_vencido` se inválido ou vencido."""
    try:
        p = jwt.decode(token, _chave_cadastro(), algorithms=["HS256"],
                       options={"require": ["exp", "sub", "email", "fin"]})
    except jwt.PyJWTError:
        raise AppError(400, "cadastro_vencido", MSG_CADASTRO_VENCIDO)
    if p.get("fin") != "cadastro_google":
        raise AppError(400, "cadastro_vencido", MSG_CADASTRO_VENCIDO)
    return {"sub": str(p["sub"]), "email": str(p["email"]), "nome": str(p.get("nome") or "")}
