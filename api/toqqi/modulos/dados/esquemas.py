from typing import Literal

from pydantic import BaseModel, Field


class ZonaIn(BaseModel):
    opcao: Literal["respostas", "contatos", "tudo"]
    # a conferência (APAGAR, sem espaços nas pontas, qualquer caixa) é do serviço: 422 no campo com a mensagem certa
    confirmacao: str | None = Field(default=None, max_length=100)
