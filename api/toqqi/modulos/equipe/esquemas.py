from typing import Annotated, Literal

from pydantic import BaseModel, Field

from toqqi.core.validacao import Email, SenhaForte, Texto

Nome = Annotated[Texto, Field(min_length=2, max_length=120)]
Cargo = Annotated[Texto, Field(max_length=80)]


class NovoUsuarioIn(BaseModel):
    nome: Nome
    email: Email
    cargo: Cargo | None = None
    perfil: Literal["admin", "gestor", "consulta"]
    senha: SenhaForte


class AlterarUsuarioIn(BaseModel):
    nome: Nome | None = None
    cargo: Cargo | None = None
    perfil: Literal["admin", "gestor", "consulta"] | None = None
    situacao: Literal["ativo", "pendente", "bloqueado"] | None = None


class PermissoesIn(BaseModel):
    gestor: list[Annotated[str, Field(max_length=60)]] = Field(max_length=100)
    consulta: list[Annotated[str, Field(max_length=60)]] = Field(max_length=100)
