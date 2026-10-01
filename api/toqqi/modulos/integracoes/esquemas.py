from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field
from pydantic_core import PydanticCustomError

from toqqi.core.validacao import Documento, EmailOpcional, Telefone, TextoAte
from toqqi.modulos.contatos.esquemas import ContextoIn
from toqqi.modulos.integracoes.webhooks import EVENTOS


class EmpresaEventoIn(BaseModel):
    nome: TextoAte(120) = None
    documento: Documento = None
    codigo_externo: TextoAte(100) = None


class PesquisaIn(BaseModel):
    email: EmailOpcional = None
    telefone: Telefone = None
    nome: TextoAte(120) = None
    empresa: EmpresaEventoIn | None = None
    codigo_externo: TextoAte(100) = None
    evento: TextoAte(60) = None
    referencia: TextoAte(120) = None
    contexto: ContextoIn | None = None
    formulario_id: int | None = None
    tipo: Literal["nps", "csat"] | None = None
    canal: Literal["auto", "email", "whatsapp", "link"] = "auto"
    enviar: bool = True
    ignorar_descanso: bool = False
    id_evento: TextoAte(100) = None


class CsatIn(PesquisaIn):
    """Compatível com a API do Rakiti: `enviar_email` = `enviar`; `assunto` vai para o convite."""
    enviar_email: bool | None = None
    assunto: TextoAte(120) = None


def _sem_repetir(eventos: list[str]) -> list[str]:
    if len(set(eventos)) != len(eventos):
        raise PydanticCustomError("toqqi_eventos", "Não repita eventos.")
    return eventos


Eventos = Annotated[list[Literal[EVENTOS]], Field(min_length=1, max_length=len(EVENTOS)), AfterValidator(_sem_repetir)]
Url = Annotated[str, Field(min_length=1, max_length=500)]


class WebhookIn(BaseModel):
    url: Url
    eventos: Eventos


class WebhookAlterarIn(BaseModel):
    url: Url | None = None
    eventos: Eventos | None = None
    ativo: bool | None = None
