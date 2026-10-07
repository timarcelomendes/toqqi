"""Limite de tentativas por IP (slowapi; algumas rotas contam por usuário ou por chave). Desligável com
RATE_LIMIT_ENABLED=0.

Etapa 5f: a chave por IP é `chave_ip` (o IP já resolvido por `core.requisicao.IpDoCliente`): `ip:{IPv4}` ou, em IPv6,
o prefixo /64 (`ip6:2001:db8:1:2::/64`) — quem tem um IPv6 costuma ter o /64 inteiro e trocaria de endereço a cada
tentativa. Os registros (auditoria, sessões, aceites, registros de acesso) guardam o endereço inteiro."""
import ipaddress

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from toqqi.core.config import config
from toqqi.core.errors import resposta_erro
from toqqi.core.security import ler_token_acesso


def chave_ip(request: Request) -> str:
    """Chave do limite por IP: `ip:{IPv4}` ou `ip6:{prefixo /64}`."""
    host = request.client.host if request.client else ""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return f"ip:{host}"
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return f"ip:{ip.ipv4_mapped}"
        return f"ip6:{ipaddress.IPv6Network((int(ip) >> 64 << 64, 64))}"
    return f"ip:{ip}"


limiter = Limiter(key_func=chave_ip, enabled=config().RATE_LIMIT_ENABLED, headers_enabled=False)

LIMITE_ENTRAR = "5/minute"
LIMITE_SENSIVEL = "3/minute"  # cadastro, esqueci, reenviar, pedir-acesso, redefinir


def limite_por_usuario(request: Request) -> str:
    """Chave do limite das rotas do usuário logado: o id do usuário do token (sem token válido, o IP; a rota responde
    401 sem chegar a contar)."""
    esquema, _, token = (request.headers.get("authorization") or "").partition(" ")
    dados = ler_token_acesso(token.strip()) if esquema.lower() == "bearer" and token.strip() else None
    return f"usuario:{dados['usuario_id']}" if dados else chave_ip(request)


async def ao_exceder(_: Request, __: RateLimitExceeded):
    return resposta_erro(429, "muitas_tentativas", "Muitas tentativas. Aguarde um minuto.")
LIMITE_PUBLICO_ABRIR = "30/minute"       # abrir página pública de pesquisa
LIMITE_RESPONDER_CONVITE = "10/minute"   # responder convite individual
LIMITE_RESPONDER_LINK = "5/minute"       # responder link público do formulário
LIMITE_DESCADASTRO = "20/minute"       # página pública de descadastro (abrir e confirmar)
LIMITE_ERROS_SITE = "10/minute"        # POST /publico/erros (etapa 5h: erros do site, sem login)
LIMITE_SAUDE = "60/minute"             # GET /saude (etapa 5h: monitor externo)
LIMITE_INTEGRACAO = "120/minute"       # rotas da chave de integração (por chave)
LIMITE_IMAGEM = "600/minute"           # imagens públicas (logo): os e-mails abrem pelo proxy de imagens do Gmail
LIMITE_ASAAS_WEBHOOK = "300/minute"    # avisos do Asaas (poucos IPs, rajadas na madrugada)
LIMITE_ACEITE = "20/minute"          # POST /eu/aceite (por usuário)
LIMITE_PLANOS_PUBLICOS = "60/minute"  # GET /publico/planos (site da raiz, etapa 5g)
LIMITE_FEEDBACK = "5/minute;30/hour;100/day"      # POST /feedback (por usuário): cada um vira e-mail para a equipe
LIMITE_FEEDBACK_MENSAGEM = "10/minute;120/hour"   # POST /feedback/{id}/mensagens (por usuário)
