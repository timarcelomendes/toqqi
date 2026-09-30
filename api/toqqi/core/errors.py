"""Formato único de erro: {"erro": {"codigo", "mensagem", "campos"}}."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from toqqi.core.requisicao import request_id

log = logging.getLogger("toqqi")


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
        }
        codigo, msg = mapa.get(exc.status_code, ("erro_http", "Não foi possível concluir o pedido."))
        return resposta_erro(exc.status_code, codigo, msg, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _inesperado(_: Request, exc: Exception):
        log.exception("Erro inesperado (request_id=%s)", request_id.get())
        return resposta_erro(
            500, "erro_interno", "Algo deu errado do nosso lado. Tente de novo em instantes."
        )


def nao_encontrado(mensagem: str = "Não encontramos o que você procurou.") -> AppError:
    return AppError(404, "nao_encontrado", mensagem)
