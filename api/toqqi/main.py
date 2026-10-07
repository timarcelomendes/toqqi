"""Aplicação FastAPI do Toqqi (etapas 1 a 5f: acesso, equipe, cadastros, formulários, páginas públicas, envios,
integrações, WhatsApp automático, respostas, planos de ação, painel, IA por resposta, relatórios, assinatura, Ajuda,
assistente, crescimento, IA sob demanda, e-mails: banco de imagens e e-mails enviados, e dados da conta: exportação,
zona de risco, registros de acesso e exclusão automática; 5g: parâmetros da plataforma; 5h: aviso de erros e
`GET /saude` com o banco, para o monitor externo)."""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from toqqi.core import erros, log_seguro, logs
from toqqi.core.config import config
from toqqi.core.db import engine, migrar
from toqqi.core.errors import modelo_da_rota, registrar_handlers
from toqqi.core.limite_corpo import LimiteDeCorpo
from toqqi.core.rate_limit import LIMITE_SAUDE, ao_exceder, limiter
from toqqi.core.requisicao import IpDoCliente, ip_cliente, request_id
from toqqi.modulos.acesso.rotas import router as acesso
from toqqi.modulos.acoes.rotas import router as acoes
from toqqi.modulos.ajuda.rotas import router as ajuda
from toqqi.modulos.assinatura.rotas import router as assinatura
from toqqi.modulos.assinatura.rotas import router_asaas as asaas_webhook
from toqqi.modulos.assistente.rotas import router as assistente
from toqqi.modulos.auditoria.rotas import router as auditoria
from toqqi.modulos.cadastros.rotas import router as cadastros
from toqqi.modulos.conta.rotas import router as conta
from toqqi.modulos.contatos.rotas import router as contatos
from toqqi.modulos.contatos.rotas import router_csv as contatos_csv
from toqqi.modulos.crescimento.rotas import router as crescimento
from toqqi.modulos.dados.rotas import router as dados
from toqqi.modulos.empresas.rotas import router as empresas
from toqqi.modulos.empresas.rotas import router_csv as empresas_csv
from toqqi.modulos.envios.rotas import router as envios
from toqqi.modulos.envios.rotas import router_interno as interno
from toqqi.modulos.equipe.rotas import router as equipe
from toqqi.modulos.feedback.rotas import router as feedback
from toqqi.modulos.feedback.rotas import router_plataforma as feedback_plataforma
from toqqi.modulos.formularios.rotas import router as formularios
from toqqi.modulos.imagens.rotas import router as imagens
from toqqi.modulos.importacao.rotas import router as importacao
from toqqi.modulos.integracoes.rotas import router as integracoes
from toqqi.modulos.integracoes.rotas import router_chave as integracao
from toqqi.modulos.painel.rotas import router as painel
from toqqi.modulos.plataforma.parametros import router as parametros
from toqqi.modulos.plataforma.parametros import router_publico as planos_publicos
from toqqi.modulos.plataforma.rotas import router as plataforma
from toqqi.modulos.publico.rotas import router as publico
from toqqi.modulos.relatorios.rotas import router as relatorios
from toqqi.modulos.conectores.rotas import router as conectores
from toqqi.modulos.conectores.rotas import router_publico as conectores_publico
from toqqi.modulos.saude.rotas import router as saude_conta  # etapa 5i: saúde da conta (não é o /saude)
from toqqi.modulos.respostas.rotas import router as respostas
from toqqi.modulos.whatsapp.rotas import router as whatsapp
from toqqi.modulos.whatsapp.rotas import router_publico as whatsapp_publico

PREFIXO = "/api/v1"
# Corpo maior que isto é recusado (413) sem ser lido inteiro. A indicação (pública) tem poucos campos curtos (nome,
# empresa, telefone, e-mail e observação de até 500 caracteres). Os envios de arquivo são lidos pelo FastAPI antes de o
# login ser conferido: o teto vale o limite do arquivo + folga do multipart (o arquivo um pouco acima do limite ainda
# chega à rota e recebe a mensagem de sempre; os enormes param aqui).
_FOLGA_MULTIPART = 64 * 1024
LIMITES_DE_CORPO = [
    ("POST", rf"{PREFIXO}/publico/convites/[^/]+/indicacoes", 20 * 1024),
    ("POST", rf"{PREFIXO}/imagens", 1024 * 1024 + _FOLGA_MULTIPART),
    ("PUT", rf"{PREFIXO}/conta/logo", 300 * 1024 + _FOLGA_MULTIPART),
    ("POST", rf"{PREFIXO}/formularios/[^/]+/logo", 300 * 1024 + _FOLGA_MULTIPART),
    ("POST", rf"{PREFIXO}/formularios/[^/]+/imagens", 1024 * 1024 + _FOLGA_MULTIPART),  # etapa 5l: conteúdo
    # etapa 5l: o documento do formulário (perguntas, HTML dos blocos e dos finais) vai até 1 MB
    ("POST", rf"{PREFIXO}/formularios(/.*)?", 1024 * 1024),
    ("PATCH", rf"{PREFIXO}/formularios/[^/]+", 1024 * 1024),
    ("PUT", rf"{PREFIXO}/formularios/[^/]+/rascunho", 1024 * 1024),
    ("POST", rf"{PREFIXO}/importacao/analisar", 5 * 1024 * 1024 + _FOLGA_MULTIPART),
    ("POST", rf"{PREFIXO}/publico/erros", 4 * 1024),  # etapa 5h: erros do site (tipo, mensagem, local, pilha, versão)
    # feedback: até 3 imagens de 1 MB, o texto (até 5.000 caracteres) e o contexto da tela (diagnóstico até 64 KB)
    ("POST", rf"{PREFIXO}/feedback", 3 * 1024 * 1024 + 128 * 1024),
    ("POST", rf"{PREFIXO}/feedback/[^/]+/mensagens", 3 * 1024 * 1024 + 64 * 1024),
    ("POST", rf"{PREFIXO}/plataforma/feedback/[^/]+/mensagens", 64 * 1024),
    ("PATCH", rf"{PREFIXO}/plataforma/feedback/[^/]+", 64 * 1024),
]
log = logging.getLogger("toqqi")
logs.configurar()  # mensagens da aplicação (inclusive INFO) aparecem no log do Render


@asynccontextmanager
async def _ciclo(app: FastAPI):
    from toqqi.core import parametros
    from toqqi.core.implantacao import garantir_admin_inicial, garantir_papel_app
    garantir_papel_app()          # antes das migrações: os GRANTs precisam do papel existindo
    if config().AUTO_MIGRATE:
        log.info("Aplicando migrações (AUTO_MIGRATE=1)...")
        migrar()
    garantir_admin_inicial()
    parametros.aquecer()          # etapa 5g: o cache dos parâmetros já lido (a primeira rota não espera o banco)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Toqqi API", version="1.0.0", lifespan=_ciclo,
                  docs_url=f"{PREFIXO}/docs", openapi_url=f"{PREFIXO}/openapi.json", redoc_url=None)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, ao_exceder)
    registrar_handlers(app)
    app.add_middleware(LimiteDeCorpo, rotas=LIMITES_DE_CORPO)

    @app.middleware("http")
    async def _id_da_requisicao(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        rid = rid[:64]
        request.state.request_id = rid  # etapa 5h: o tratador de 500 roda fora deste middleware (core.errors)
        t1 = request_id.set(rid)
        t2 = ip_cliente.set(request.client.host if request.client else None)
        try:
            resposta = await call_next(request)
        except Exception:
            # etapa 5h: o roteador escreveu a rota neste scope; o tratador de 500, fora daqui, só vê o state
            request.state.rota_modelo = modelo_da_rota(request.scope)
            raise
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
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Api-Key"],
        # Content-Disposition: o site (outra origem) lê o nome dos arquivos baixados (CSV, modelos).
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )
    # o mais externo (adicionado por último): todos os de dentro já recebem o IP do cliente em scope["client"]
    app.add_middleware(IpDoCliente, cabecalho=config().IP_CLIENTE_CABECALHO)

    for r in (acesso, equipe, conta, auditoria, parametros, feedback_plataforma, plataforma, feedback, cadastros,
              empresas_csv, empresas,
              contatos_csv, contatos, importacao,
              formularios, imagens, conectores_publico, publico, envios, interno, conectores, integracoes, whatsapp,
              integracao, whatsapp_publico,
              respostas, acoes, crescimento, saude_conta, painel, relatorios, assinatura, asaas_webhook, ajuda, assistente,
              dados, planos_publicos):
        app.include_router(r, prefix=PREFIXO)

    @app.get(f"{PREFIXO}/saude", tags=["infra"])
    @limiter.limit(LIMITE_SAUDE)
    def saude(request: Request):
        """Para o monitor externo (etapa 5h, README "Monitor externo"), sem login: a API respondeu e o banco também
        (`SELECT 1`, até 3 s). {ok, banco, versao}; com o banco fora, 503 com ok e banco false. Sem cache."""
        sem_cache = {"Cache-Control": "no-store"}
        versao = erros.versao_api()
        try:
            with engine().begin() as c:
                c.execute(text("SET LOCAL statement_timeout = '3s'"))
                c.execute(text("SELECT 1"))
        except Exception as e:  # noqa: BLE001 - qualquer falha do banco vira 503 para o monitor
            log.warning("Saúde: o banco não respondeu (%s).", log_seguro.descrever_erro(e) if log_seguro.do_banco(e)
                        else type(e).__name__)
            return JSONResponse({"ok": False, "banco": False, "versao": versao}, status_code=503, headers=sem_cache)
        return JSONResponse({"ok": True, "banco": True, "versao": versao}, headers=sem_cache)

    return app


app = create_app()
