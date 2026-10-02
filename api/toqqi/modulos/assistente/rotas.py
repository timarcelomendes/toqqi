from fastapi import APIRouter, Depends

from toqqi.core.deps import Contexto, requer
from toqqi.modulos.assistente import servico
from toqqi.modulos.assistente.esquemas import PerguntaIn

router = APIRouter(prefix="/assistente", tags=["assistente"])
LOGADO = requer()  # todos os perfis; cada consulta de dados confere as permissões de quem pergunta


@router.get("")
def estado(ctx: Contexto = Depends(LOGADO)):
    return servico.estado(ctx)


@router.post("/perguntar")
def perguntar(dados: PerguntaIn, ctx: Contexto = Depends(LOGADO)):
    # síncrona: segura uma thread da API por até 60 s; `servico.perguntar` limita as perguntas em andamento
    return servico.perguntar(ctx, dados.pergunta, dados.historico)
