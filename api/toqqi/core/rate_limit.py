"""Limite de tentativas por IP (slowapi). Desligável com RATE_LIMIT_ENABLED=0."""
from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from toqqi.core.config import config
from toqqi.core.errors import resposta_erro

limiter = Limiter(key_func=get_remote_address, enabled=config().RATE_LIMIT_ENABLED, headers_enabled=False)

LIMITE_ENTRAR = "5/minute"
LIMITE_SENSIVEL = "3/minute"  # cadastro, esqueci, reenviar, pedir-acesso, redefinir


async def ao_exceder(_: Request, __: RateLimitExceeded):
    return resposta_erro(429, "muitas_tentativas", "Muitas tentativas. Aguarde um minuto.")
LIMITE_PUBLICO_ABRIR = "30/minute"       # abrir página pública de pesquisa
LIMITE_RESPONDER_CONVITE = "10/minute"   # responder convite individual
LIMITE_RESPONDER_LINK = "5/minute"       # responder link público do formulário
LIMITE_DESCADASTRO = "20/minute"       # página pública de descadastro (abrir e confirmar)
LIMITE_INTEGRACAO = "120/minute"       # rotas da chave de integração (por chave)
