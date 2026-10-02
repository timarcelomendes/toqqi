"""Formato único de erro: {"erro": {"codigo", "mensagem", "campos"}}.

Valor que o banco recusa por ser inválido para a coluna (id fora do bigint, texto que não vira número, caractere
inválido, texto longo demais) é dado de quem chamou, não erro nosso: vira 422 `dados_invalidos` em qualquer rota (as
rotas validam antes; isto é a rede de proteção das que esqueceram). O log registra o erro pelo `core.log_seguro`
(classe e SQLSTATE, sem os dados)."""
import logging

from fastapi import FastAPI, Request
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
    async def _banco(_: Request, exc: DBAPIError):
        erro = erro_do_banco(exc)
        if erro is not None:
            if dado_invalido(exc):  # o log_seguro troca a mensagem do banco (que traz o valor) pelo resumo sem dados
                log.warning("Dado recusado pelo banco, respondido com 422 (request_id=%s)", request_id.get(),
                            exc_info=exc)
            return resposta_erro(erro.status, erro.codigo, erro.mensagem, erro.campos)
        log.exception("Erro de banco (request_id=%s)", request_id.get())
        return resposta_erro(
            500, "erro_interno", "Algo deu errado do nosso lado. Tente de novo em instantes."
        )

    @app.exception_handler(Exception)
    async def _inesperado(_: Request, exc: Exception):
        log.exception("Erro inesperado (request_id=%s)", request_id.get())
        return resposta_erro(
            500, "erro_interno", "Algo deu errado do nosso lado. Tente de novo em instantes."
        )


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
    limite em `campos.limite` (o gatilho manda no DETAIL), para a tela oferecer "Ver planos". Valor recusado pelo banco
    (`dado_invalido`) vira 422 `dados_invalidos`."""
    orig = getattr(exc, "orig", None)
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
