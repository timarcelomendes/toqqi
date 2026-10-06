from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from toqqi.core.validacao import Documento, Texto, TextoAte

Nome = Annotated[Texto, Field(min_length=1, max_length=200)]
Renovacao = Annotated[date, Field(ge=date(2000, 1, 1), le=date(2100, 12, 31))] | None
Motivo = Literal["preco", "concorrente", "atendimento", "produto", "encerrou", "outro"]
Valor = Annotated[Decimal, Field(ge=0, lt=Decimal("10000000000"), max_digits=12, decimal_places=2)]


class EmpresaIn(BaseModel):
    nome: Nome
    documento: Documento = None
    grupo_id: int | None = None
    segmento_id: int | None = None
    responsavel_id: int | None = None
    valor_mensal: Valor | None = None
    cliente_desde: date | None = None
    codigo_externo: TextoAte(100) = None
    ativa: bool = True
    renovacao_em: Renovacao = None  # etapa 5i


class EmpresaAlterarIn(BaseModel):
    nome: Nome | None = None
    documento: Documento = None
    grupo_id: int | None = None
    segmento_id: int | None = None
    responsavel_id: int | None = None
    valor_mensal: Valor | None = None
    cliente_desde: date | None = None
    codigo_externo: TextoAte(100) = None
    ativa: bool | None = None
    renovacao_em: Renovacao = None  # etapa 5i


class PerdaIn(BaseModel):
    """Etapa 5i: "Marcar como perdida"."""
    perdida_em: date | None = None  # sem ela: hoje
    motivo_perda: Motivo
    motivo_detalhe: TextoAte(300) = None


class PerdaAlterarIn(BaseModel):
    """Corrigir a perda já marcada (data, motivo, detalhe): só os campos enviados mudam."""
    perdida_em: date | None = None
    motivo_perda: Motivo | None = None
    motivo_detalhe: TextoAte(300) = None


class RetornoIn(BaseModel):
    """Etapa 5i: "Voltou a ser cliente" (campos ausentes ficam como estão)."""
    valor_mensal: Valor | None = None
    renovacao_em: Renovacao = None
    reativar_contatos: bool = True
