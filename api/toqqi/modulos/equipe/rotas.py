from fastapi import APIRouter, Depends, Response

from toqqi.core.deps import Contexto, requer
from toqqi.modulos.equipe import servico
from toqqi.modulos.equipe.esquemas import AlterarUsuarioIn, NovoUsuarioIn, PermissoesIn

router = APIRouter(prefix="/equipe", tags=["equipe"])
GERENCIAR = requer("equipe.gerenciar")


# As rotas de permissões vêm antes de /{usuario_id} para não serem confundidas com um id.
@router.get("/permissoes")
def obter_permissoes(ctx: Contexto = Depends(GERENCIAR)):
    return servico.obter_permissoes(ctx)


@router.put("/permissoes")
def salvar_permissoes(dados: PermissoesIn, ctx: Contexto = Depends(GERENCIAR)):
    return servico.salvar_permissoes(ctx, dados)


@router.get("/pendentes")
def pendentes(ctx: Contexto = Depends(GERENCIAR)):
    """{total}: pedidos de acesso esperando aprovação (o número ao lado de Equipe no menu)."""
    return servico.pendentes(ctx)


@router.get("")
def listar(ctx: Contexto = Depends(GERENCIAR)):
    return servico.listar(ctx)


@router.post("", status_code=201)
def criar(dados: NovoUsuarioIn, ctx: Contexto = Depends(GERENCIAR)):
    return servico.criar(ctx, dados)


@router.patch("/{usuario_id}")
def alterar(usuario_id: int, dados: AlterarUsuarioIn, ctx: Contexto = Depends(GERENCIAR)):
    return servico.alterar(ctx, usuario_id, dados)


@router.delete("/{usuario_id}", status_code=204)
def excluir(usuario_id: int, ctx: Contexto = Depends(GERENCIAR)):
    servico.excluir(ctx, usuario_id)
    return Response(status_code=204)


@router.post("/{usuario_id}/reenviar-confirmacao")
def reenviar_confirmacao(usuario_id: int, ctx: Contexto = Depends(GERENCIAR)):
    return {"mensagem": servico.reenviar_confirmacao(ctx, usuario_id)}
