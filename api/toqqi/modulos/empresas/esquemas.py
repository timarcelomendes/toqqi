from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from toqqi.core.validacao import Documento, Texto, TextoOpcional

Nome = Annotated[Texto, Field(min_length=1, max_length=200)]
Valor = Annotated[Decimal, Field(ge=0, lt=Decimal("10000000000"), max_digits=12, decimal_places=2)]


class EmpresaIn(BaseModel):
    nome: Nome
    documento: Documento = None
    grupo_id: int | None = None
    segmento_id: int | None = None
    responsavel_id: int | None = None
    valor_mensal: Valor | None = None
    cliente_desde: date | None = None
    codigo_externo: Annotated[TextoOpcional, Field(max_length=100)] = None
    ativa: bool = True


class EmpresaAlterarIn(BaseModel):
    nome: Nome | None = None
    documento: Documento = None
    grupo_id: int | None = None
    segmento_id: int | None = None
    responsavel_id: int | None = None
    valor_mensal: Valor | None = None
    cliente_desde: date | None = None
    codigo_externo: Annotated[TextoOpcional, Field(max_length=100)] = None
    ativa: bool | None = None
