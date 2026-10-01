from typing import Annotated

from pydantic import BaseModel, Field

from toqqi.core.validacao import EmailOpcional, Telefone, Texto, TextoAte

Nome = Annotated[Texto, Field(min_length=1, max_length=120)]
Curto = TextoAte(120)


class ContatoIn(BaseModel):
    nome: Nome
    email: EmailOpcional = None
    telefone: Telefone = None
    empresa_id: int | None = None
    cargo_id: int | None = None
    perfil_id: int | None = None
    codigo_externo: TextoAte(100) = None
    recebe_pesquisas: bool = True
    ativo: bool = True


class ContatoAlterarIn(BaseModel):
    nome: Nome | None = None
    email: EmailOpcional = None
    telefone: Telefone = None
    empresa_id: int | None = None
    cargo_id: int | None = None
    perfil_id: int | None = None
    codigo_externo: TextoAte(100) = None
    recebe_pesquisas: bool | None = None
    ativo: bool | None = None


class ContextoIn(BaseModel):
    pedido: Curto = None
    nota_fiscal: Curto = None
    rota: Curto = None
    motorista: Curto = None
    filial: Curto = None
    transportadora: Curto = None


class LinkPesquisaIn(BaseModel):
    formulario_id: int | None = None
    contexto: ContextoIn | None = None
    assunto: Curto = None
    referencia: Curto = None
