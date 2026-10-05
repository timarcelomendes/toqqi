"""Formato único de erro: {"erro": {"codigo", "mensagem", "campos"}}.

Valor que o banco recusa por ser inválido para a coluna (id fora do bigint, texto que não vira número, caractere
inválido, texto longo demais) é dado de quem chamou, não erro nosso: vira 422 `dados_invalidos` em qualquer rota (as
rotas validam antes; isto é a rede de proteção das que esqueceram). O log registra o erro pelo `core.log_seguro`
(classe e SQLSTATE, sem os dados).

Etapa 5h (aviso de erros): os dois tratadores de 500 (`_inesperado` e o do banco) registram a falha em `erros`
(`core.erros`, origem `api`) antes de responder (numa thread; o registro nunca lança): o local é o método e o **modelo**
da rota (`GET /api/v1/acoes/{acao_id}`, nunca o caminho de verdade, que pode ter um token), a conta sai do token de
acesso, quando há um válido (sem ir ao banco), e o request id e o modelo da rota vêm do `request.state` quando o
tratador roda fora do middleware que os conhece (o de `Exception` roda fora de todos). Os 4xx não registram. A
resposta do 500 leva o `X-Request-ID`."""
import logging

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException

from toqqi.core.requisicao import request_id

log = logging.getLogger("toqqi")

# 22003 número fora do intervalo (ex.: id além do bigint), 22P02 representação inválida (texto que não vira número),
# 22021 caractere inválido para a codificação (ex.: NUL), 22001 texto longo demais para a coluna
SQLSTATES_DADO_INVALIDO = frozenset({"22003", "22P02", "22021", "22001"})
MSG_DADO_INVALIDO = "Confira os dados enviados."
# etapa 5i: contato ativo em empresa perdida (gatilho `contatos_empresa_perdida`, SQLSTATE TQ409)
MSG_EMPRESA_PERDIDA = ("Esta empresa foi marcada como perdida. Para voltar a pesquisar este contato, marque “Voltou a "
                       "ser cliente” na empresa.")


class AppError(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str, campos: dict[str, str] | None = None):
        super().__init__(mensagem)
        self.status = status
        self.codigo = codigo
        self.mensagem = mensagem
        self.campos = campos or {}


def resposta_erro(status: int, codigo: str, mensagem: str, campos: dict | None = None, headers=None):
    return JSONResponse(
        status_code=status,
        content={"erro": {"codigo": codigo, "mensagem": mensagem, "campos": campos or {}}},
        headers=headers,
    )


# Mensagens em português para os erros de validação mais comuns do Pydantic.
_MENSAGENS = {
    "missing": "Preencha este campo.",
    "string_too_short": "Está curto demais.",
    "string_too_long": "Está longo demais.",
    "string_type": "Informe um texto.",
    "int_parsing": "Informe um número inteiro.",
    "int_type": "Informe um número inteiro.",
    "bool_parsing": "Informe verdadeiro ou falso.",
    "bool_type": "Informe verdadeiro ou falso.",
    "greater_than_equal": "Valor abaixo do mínimo permitido.",
    "less_than_equal": "Valor acima do máximo permitido.",
    "literal_error": "Opção inválida.",
    "enum": "Opção inválida.",
    "list_type": "Informe uma lista.",
    "uuid_parsing": "Identificador inválido.",
    "date_from_datetime_parsing": "Informe uma data no formato AAAA-MM-DD.",
    "date_parsing": "Informe uma data no formato AAAA-MM-DD.",
    "json_invalid": "O corpo da requisição não é um JSON válido.",
    "model_attributes_type": "Formato inválido.",
    "dict_type": "Formato inválido.",
}


def _campos_de_validacao(exc: RequestValidationError) -> dict[str, str]:
    campos: dict[str, str] = {}
    for e in exc.errors():
        loc = [str(p) for p in e.get("loc", ()) if p not in ("body", "query", "path")]
        nome = ".".join(loc) or "geral"
        tipo = e.get("type", "")
        if tipo.startswith("toqqi_"):  # erros criados por nós já vêm em português
            msg = e.get("msg", "Valor inválido.")
        else:
            msg = _MENSAGENS.get(tipo, "Valor inválido.")
        campos.setdefault(nome, msg)
    return campos


MSG_INTERNO = "Algo deu errado do nosso lado. Tente de novo em instantes."


def id_do_pedido(request: Request) -> str | None:
    """O request id do pedido: o do contexto (dentro do middleware) ou o guardado no `request.state` (fora dele)."""
    return request_id.get() or getattr(request.state, "request_id", None)


def modelo_da_rota(scope) -> str | None:
    """O caminho do pedido com cada parâmetro da rota trocado pelo nome ("/api/v1/acoes/{acao_id}"), quando o roteador
    já achou a rota (`scope["route"]` e `scope["path_params"]`); senão None. Monta a partir do caminho de verdade
    porque, com os roteadores incluídos, o `path` da rota não traz o prefixo `/api/v1`."""
    if scope.get("route") is None:
        return None
    nomes = {str(v): k for k, v in (scope.get("path_params") or {}).items()}
    return "/".join(f"{{{nomes[p]}}}" if p in nomes else p for p in str(scope.get("path") or "").split("/"))


def local_do_pedido(request: Request) -> str:
    """Método e modelo da rota ("GET /api/v1/acoes/{acao_id}"); sem rota conhecida, "GET (rota desconhecida)". Nunca o
    caminho de verdade (pode trazer um token, como o do link da pesquisa). O tratador de 500 roda fora do roteador: o
    modelo vem do `request.state`, guardado pelo middleware do request id quando a exceção passou por ele."""
    try:
        modelo = modelo_da_rota(request.scope) or getattr(request.state, "rota_modelo", None)
    except Exception:  # noqa: BLE001 - só para o registro: na dúvida, sem rota
        modelo = None
    return f"{request.method} {modelo or '(rota desconhecida)'}"


def conta_do_pedido(request: Request) -> int | None:
    """A conta do token de acesso, quando há um válido (sem ir ao banco); senão None."""
    from toqqi.core.security import ler_token_acesso

    esquema, _, token = (request.headers.get("authorization") or "").partition(" ")
    if esquema.lower() != "bearer" or not token.strip():
        return None
    dados = ler_token_acesso(token.strip())
    return dados["conta_id"] if dados else None


def _registrar_500(request: Request, exc: BaseException, rid: str | None) -> None:
    """Registra o 500 em `erros` (nunca lança: o registro não muda a resposta)."""
    from toqqi.core import erros

    try:
        local, conta_id = local_do_pedido(request), conta_do_pedido(request)
    except Exception:  # noqa: BLE001
        local, conta_id = f"{request.method} (rota desconhecida)", None
    erros.registrar_excecao(exc, "api", local, conta_id=conta_id, request_id=rid)


async def resposta_500(request: Request, exc: BaseException, rid: str | None) -> JSONResponse:
    """O 500 de sempre, com o `X-Request-ID`, depois de registrar o erro (numa thread: o registro vai ao banco). Antes
    da resposta e não numa tarefa de fundo dela: um erro depois de a resposta começar a sair (numa tarefa de fundo do
    pedido) chega aqui sem a resposta ser mandada, e a tarefa de fundo dela nunca rodaria."""
    await run_in_threadpool(_registrar_500, request, exc, rid)
    return resposta_erro(500, "erro_interno", MSG_INTERNO, headers={"X-Request-ID": rid} if rid else None)


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return resposta_erro(exc.status, exc.codigo, exc.mensagem, exc.campos)

    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, exc: RequestValidationError):
        return resposta_erro(422, "dados_invalidos", "Confira os campos destacados.", _campos_de_validacao(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        mapa = {
            404: ("nao_encontrado", "Não encontramos o que você procurou."),
            405: ("metodo_nao_permitido", "Esta operação não é permitida aqui."),
            413: ("pedido_grande_demais", "Os dados enviados passam do tamanho permitido."),  # core.limite_corpo
        }
        codigo, msg = mapa.get(exc.status_code, ("erro_http", "Não foi possível concluir o pedido."))
        return resposta_erro(exc.status_code, codigo, msg, headers=getattr(exc, "headers", None))

    @app.exception_handler(DBAPIError)
    async def _banco(request: Request, exc: DBAPIError):
        erro = erro_do_banco(exc)
        rid = id_do_pedido(request)
        if erro is not None:
            if dado_invalido(exc):  # o log_seguro troca a mensagem do banco (que traz o valor) pelo resumo sem dados
                log.warning("Dado recusado pelo banco, respondido com 422 (request_id=%s)", rid, exc_info=exc)
            return resposta_erro(erro.status, erro.codigo, erro.mensagem, erro.campos)
        log.exception("Erro de banco (request_id=%s)", rid)
        return await resposta_500(request, exc, rid)

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception):
        rid = id_do_pedido(request)
        log.exception("Erro inesperado (request_id=%s)", rid)
        return await resposta_500(request, exc, rid)


def _tem_nul(valor) -> bool:
    if isinstance(valor, str):
        return "\x00" in valor
    if isinstance(valor, dict):
        return any(_tem_nul(v) for v in valor.values())
    if isinstance(valor, (list, tuple)):
        return any(_tem_nul(v) for v in valor)
    return False


def dado_invalido(exc: DBAPIError) -> bool:
    """O banco recusou um valor enviado (SQLSTATES_DADO_INVALIDO). O NUL (\\x00) nem chega ao banco: o psycopg recusa
    o texto antes de enviar, com um DataError sem SQLSTATE — vale como o 22021 quando algum parâmetro tem NUL."""
    if not isinstance(exc, DataError):
        return False
    codigo = getattr(exc.orig, "sqlstate", None)
    if codigo is not None:
        return codigo in SQLSTATES_DADO_INVALIDO
    return _tem_nul(exc.params)


def erro_do_banco(exc: DBAPIError) -> AppError | None:
    """Erros de regra levantados pelo próprio banco (gatilhos) viram AppError. O limite de contatos (TQ402) leva o
    limite em `campos.limite` (o gatilho manda no DETAIL), para a tela oferecer "Ver planos". Contato ativo em empresa
    perdida (TQ409, etapa 5i) vira 409 `empresa_perdida`. Valor recusado pelo banco (`dado_invalido`) vira 422
    `dados_invalidos`."""
    orig = getattr(exc, "orig", None)
    if getattr(orig, "sqlstate", None) == "TQ409":
        return AppError(409, "empresa_perdida", MSG_EMPRESA_PERDIDA)
    if getattr(orig, "sqlstate", None) == "TQ402":
        diag = getattr(orig, "diag", None)
        msg = getattr(diag, "message_primary", None) or "Você atingiu o limite de contatos ativos do seu plano."
        limite = getattr(diag, "message_detail", None) or ""
        return AppError(402, "limite_do_plano", msg, {"limite": limite} if limite.isdigit() else None)
    if dado_invalido(exc):
        return AppError(422, "dados_invalidos", MSG_DADO_INVALIDO)
    return None


def nao_encontrado(mensagem: str = "Não encontramos o que você procurou.") -> AppError:
    return AppError(404, "nao_encontrado", mensagem)
