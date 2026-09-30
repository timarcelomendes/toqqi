"""Dados da requisição atual (id e IP) acessíveis fora das rotas, ex.: na auditoria."""
from contextvars import ContextVar

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
ip_cliente: ContextVar[str | None] = ContextVar("ip_cliente", default=None)
