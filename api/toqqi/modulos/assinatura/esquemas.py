"""Entradas da assinatura. Dados de cobrança validados como em Dados da empresa (CPF/CNPJ pelos dígitos
verificadores, inclusive o CNPJ alfanumérico; e-mail; telefone com DDD), mas todos obrigatórios. O telefone segue a
regra brasileira, mais estrita que a dos Dados da empresa (o Asaas pede DDD + número, sem o 55): DDD de 11 a 99 e
celular com 9 dígitos começando com 9 ou fixo com 8 dígitos começando com 2 a 5.

Etapa 5g: assinar e trocar de plano mandam `preco`, o preço que a tela mostrou; diferente do atual → 409 `preco_mudou`
(assinatura.servico.conferir_preco). Obrigatório desde a revisão: sem ele (ou null), 422 no campo `preco` ("Recarregue
a página para ver o preço atual do plano.")."""
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field
from pydantic_core import PydanticCustomError

from toqqi.core.texto import normalizar_documento
from toqqi.core.validacao import _validar_email, telefone_br

Plano = Literal["essencial", "profissional", "empresa", "personalizado"]
Ciclo = Literal["mensal", "anual"]
Forma = Literal["pix", "qualquer"]
MAX_RAZAO_SOCIAL = 200


def _erro(tipo: str, msg: str) -> PydanticCustomError:
    return PydanticCustomError(f"toqqi_{tipo}", msg)


def _vazio(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _razao_social(v):
    if _vazio(v) or not isinstance(v, str):
        raise _erro("razao_social", "Informe a razão social (ou o nome completo, para CPF).")
    v = " ".join(v.split())
    if len(v) > MAX_RAZAO_SOCIAL:
        raise _erro("razao_social", f"Use no máximo {MAX_RAZAO_SOCIAL} caracteres.")
    return v


def _documento(v):
    if _vazio(v) or not isinstance(v, str):
        raise _erro("documento", "Informe o CPF ou o CNPJ.")
    try:
        return normalizar_documento(v)
    except ValueError as e:
        raise _erro("documento", str(e))


def _email(v):
    if _vazio(v) or not isinstance(v, str):
        raise _erro("email", "Informe o e-mail que recebe as faturas.")
    return _validar_email(v)


def _telefone(v):
    if _vazio(v) or not isinstance(v, (str, int)):
        raise _erro("telefone", "Informe o telefone com DDD.")
    try:
        return telefone_br(v)  # a regra brasileira de sempre (core.validacao)
    except ValueError as e:
        raise _erro("telefone", str(e))


class DadosCobrancaIn(BaseModel):
    """PUT /assinatura/dados (e a parte de cobrança de POST /assinatura)."""
    razao_social: Annotated[str, BeforeValidator(_razao_social)]
    documento: Annotated[str, BeforeValidator(_documento)]
    email_cobranca: Annotated[str, BeforeValidator(_email)]
    telefone: Annotated[str, BeforeValidator(_telefone)]


MSG_PRECO = "Recarregue a página para ver o preço atual do plano."


def _preco(v):
    """Obrigatório: sem ele (ou com null), quem assina ou troca não confere o `preco_mudou`."""
    if _vazio(v):
        raise _erro("preco", MSG_PRECO)
    return v


# O preço que a tela mostrou. Obrigatório (revisão da 5g): ausente ou null → 422 no campo `preco` (o padrão None só
# existe para a mensagem ser a nossa, e não o "Preencha este campo." do Pydantic).
PrecoMostrado = Annotated[Decimal, BeforeValidator(_preco), Field(ge=0, le=Decimal("99999.99"))]


class AssinarIn(DadosCobrancaIn):
    """Etapa 5k: `ciclo` (padrão mensal) e `forma` (padrão qualquer); no Personalizado, `contatos` e `cota_ia`. `preco`
    = o valor de cada fatura que a tela mostrou (por mês, ou o total do ano)."""
    plano: Plano
    ciclo: Ciclo = "mensal"
    forma: Forma = "qualquer"
    contatos: int | None = Field(default=None, ge=1, le=1_000_000)
    cota_ia: int | None = Field(default=None, ge=1, le=100_000)
    preco: PrecoMostrado = Field(default=None, validate_default=True)


class PlanoIn(BaseModel):
    plano: Plano
    contatos: int | None = Field(default=None, ge=1, le=1_000_000)
    cota_ia: int | None = Field(default=None, ge=1, le=100_000)
    preco: PrecoMostrado = Field(default=None, validate_default=True)
