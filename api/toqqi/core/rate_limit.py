"""Limite de tentativas por IP (slowapi; algumas rotas contam por usuário ou por chave). Desligável com
RATE_LIMIT_ENABLED=0."""
from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from toqqi.core.config import config
from toqqi.core.errors import resposta_erro
from toqqi.core.security import ler_token_acesso

limiter = Limiter(key_func=get_remote_address, enabled=config().RATE_LIMIT_ENABLED, headers_enabled=False)

LIMITE_ENTRAR = "5/minute"
LIMITE_SENSIVEL = "3/minute"  # cadastro, esqueci, reenviar, pedir-acesso, redefinir


def limite_por_usuario(request: Request) -> str:
    """Chave do limite das rotas do usuário logado: o id do usuário do token (sem token válido, o IP; a rota responde
    401 sem chegar a contar)."""
    esquema, _, token = (request.headers.get("authorization") or "").partition(" ")
    dados = ler_token_acesso(token.strip()) if esquema.lower() == "bearer" and token.strip() else None
    return f"usuario:{dados['usuario_id']}" if dados else f"ip:{get_remote_address(request)}"


async def ao_exceder(_: Request, __: RateLimitExceeded):
    return resposta_erro(429, "muitas_tentativas", "Muitas tentativas. Aguarde um minuto.")
LIMITE_PUBLICO_ABRIR = "30/minute"       # abrir página pública de pesquisa
LIMITE_RESPONDER_CONVITE = "10/minute"   # responder convite individual
LIMITE_RESPONDER_LINK = "5/minute"       # responder link público do formulário
LIMITE_DESCADASTRO = "20/minute"       # página pública de descadastro (abrir e confirmar)
LIMITE_INTEGRACAO = "120/minute"       # rotas da chave de integração (por chave)
LIMITE_IMAGEM = "600/minute"           # imagens públicas (logo): os e-mails abrem pelo proxy de imagens do Gmail
LIMITE_ASAAS_WEBHOOK = "300/minute"    # avisos do Asaas (poucos IPs, rajadas na madrugada)
LIMITE_ACEITE = "20/minute"          # POST /eu/aceite (por usuário)
