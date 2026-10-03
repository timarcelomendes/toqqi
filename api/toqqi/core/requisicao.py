"""Dados da requisição atual (id e IP) acessíveis fora das rotas, ex.: na auditoria, e o IP do cliente atrás do proxy.

IP do cliente (etapa 5f): no Render, o uvicorn roda com `--no-proxy-headers` (o `X-Forwarded-For` chega como "o que o
cliente mandou, cliente, borda da Cloudflare": usar o primeiro endereço deixaria qualquer um trocar o IP do limite de
tentativas, da auditoria, das sessões e do aceite). O middleware ASGI `IpDoCliente`, o mais externo, troca
`scope["client"]` por `(ip, 0)`:
- com `IP_CLIENTE_CABECALHO` (no Render, `CF-Connecting-IP`, que a Cloudflare sobrescreve com o IP real): o cabeçalho
  com **um** IP válido (até 45 caracteres; IPv4 mapeado em IPv6 vira IPv4; forma canônica) → ele; ausente, repetido,
  lista, texto ou longo demais → o endereço da conexão (aviso no log uma vez por processo);
- sem o cabeçalho configurado (desenvolvimento e testes): o endereço da conexão.
Nunca lê `X-Forwarded-For` nem `X-Real-IP`. Quem lê `request.client.host` (limite, auditoria, sessões, aceite,
registros de acesso) recebe o IP certo; a porta de origem não chega ao Toqqi.
"""
import ipaddress
import logging
from contextvars import ContextVar

from starlette.types import ASGIApp, Receive, Scope, Send

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
ip_cliente: ContextVar[str | None] = ContextVar("ip_cliente", default=None)

MAX_IP = 45  # o maior IPv6 em texto (IPv4 mapeado por extenso)
log = logging.getLogger("toqqi")


def ip_valido(valor: str | None) -> str | None:
    """O IP em forma canônica (IPv4 mapeado → IPv4), ou None se `valor` não for exatamente um endereço IP."""
    v = (valor or "").strip()
    if not v or len(v) > MAX_IP or "%" in v:
        return None
    try:
        ip = ipaddress.ip_address(v)
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return str(ip.ipv4_mapped)
    return str(ip)


class IpDoCliente:
    """Middleware ASGI: `scope["client"]` = (IP do cliente, 0). `cabecalho` vazio = o endereço da conexão."""

    def __init__(self, app: ASGIApp, cabecalho: str = ""):
        self.app = app
        self.cabecalho = cabecalho.strip().lower().encode("latin-1")
        self._avisou = False

    def _ip(self, scope: Scope) -> str | None:
        conexao = scope.get("client")
        host = conexao[0] if conexao else None
        if not self.cabecalho:
            return ip_valido(host) or host
        valores = [v for k, v in scope.get("headers") or [] if k == self.cabecalho]
        ip = ip_valido(valores[0].decode("latin-1")) if len(valores) == 1 else None
        if ip is None:
            if not self._avisou:
                self._avisou = True
                log.warning("IP do cliente: cabeçalho %s ausente ou inválido; usando o endereço da conexão.",
                            self.cabecalho.decode("latin-1"))
            return ip_valido(host) or host
        return ip

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            ip = self._ip(scope)
            scope = {**scope, "client": (ip, 0) if ip is not None else None}
        await self.app(scope, receive, send)
