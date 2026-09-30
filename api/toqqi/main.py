"""Aplicação FastAPI do Toqqi (etapas 1 e 2: acesso, equipe, cadastros, formulários, páginas públicas)."""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from toqqi.core.config import config
from toqqi.core.db import migrar
from toqqi.core.errors import registrar_handlers
from toqqi.core.rate_limit import ao_exceder, limiter
from toqqi.core.requisicao import ip_cliente, request_id
from toqqi.modulos.acesso.rotas import router as acesso
from toqqi.modulos.auditoria.rotas import router as auditoria
from toqqi.modulos.cadastros.rotas import router as cadastros
from toqqi.modulos.conta.rotas import router as conta
from toqqi.modulos.contatos.rotas import router as contatos
from toqqi.modulos.empresas.rotas import router as empresas
from toqqi.modulos.equipe.rotas import router as equipe
from toqqi.modulos.formularios.rotas import router as formularios
from toqqi.modulos.importacao.rotas import router as importacao
from toqqi.modulos.plataforma.rotas import router as plataforma
from toqqi.modulos.publico.rotas import router as publico

PREFIXO = "/api/v1"
log = logging.getLogger("toqqi")


@asynccontextmanager
async def _ciclo(app: FastAPI):
    from toqqi.core.implantacao import garantir_admin_inicial, garantir_papel_app
    garantir_papel_app()          # antes das migrações: os GRANTs precisam do papel existindo
    if config().AUTO_MIGRATE:
        log.info("Aplicando migrações (AUTO_MIGRATE=1)...")
        migrar()
    garantir_admin_inicial()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Toqqi API", version="1.0.0", lifespan=_ciclo,
                  docs_url=f"{PREFIXO}/docs", openapi_url=f"{PREFIXO}/openapi.json", redoc_url=None)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, ao_exceder)
    registrar_handlers(app)

    @app.middleware("http")
    async def _id_da_requisicao(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        rid = rid[:64]
        t1 = request_id.set(rid)
        t2 = ip_cliente.set(request.client.host if request.client else None)
        try:
            resposta = await call_next(request)
        finally:
            request_id.reset(t1)
            ip_cliente.reset(t2)
        resposta.headers["X-Request-ID"] = rid
        return resposta

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config().origens,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    for r in (acesso, equipe, conta, auditoria, plataforma, cadastros, empresas, contatos, importacao,
              formularios, publico):
        app.include_router(r, prefix=PREFIXO)

    @app.get(f"{PREFIXO}/saude", tags=["infra"])
    def saude():
        return {"ok": True}

    return app


app = create_app()
