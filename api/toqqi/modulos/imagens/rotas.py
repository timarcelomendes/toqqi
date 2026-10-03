"""Banco de imagens da conta (etapa 5e): GET/POST /imagens e DELETE /imagens/{id}, com `configuracoes.gerenciar`.
As imagens saem sem login por GET /publico/imagens/{chave} (`publico.rotas`)."""
from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, Response, UploadFile

from toqqi.core.deps import Contexto, requer
from toqqi.core.validacao import MAX_ID
from toqqi.modulos.imagens import banco
from toqqi.modulos.imagens.servico import LIMITE_BANCO, MSG_BANCO, ler_envio, nome_do_arquivo

router = APIRouter(prefix="/imagens", tags=["imagens"])
GERENCIAR = requer("configuracoes.gerenciar")
IdCaminho = Annotated[int, Path(ge=1, le=MAX_ID)]  # fora do bigint: 422 (e não erro do banco)


@router.get("")
def listar(ctx: Contexto = Depends(GERENCIAR)):
    return banco.listar(ctx)


@router.post("", status_code=201)
def enviar(arquivo: UploadFile = File(...), ctx: Contexto = Depends(GERENCIAR)):
    """PNG ou JPG de até 1 MB (conferido pelos bytes); 422 no campo `arquivo` se não for."""
    dados, tipo = ler_envio(arquivo, LIMITE_BANCO, MSG_BANCO)
    return banco.enviar(ctx, dados, tipo, nome_do_arquivo(arquivo.filename))


@router.delete("/{imagem_id}", status_code=204)
def excluir(imagem_id: IdCaminho, ctx: Contexto = Depends(GERENCIAR)):
    banco.excluir(ctx, imagem_id)
    return Response(status_code=204)
