from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response

from toqqi.core.deps import Contexto, requer
from toqqi.core.paginacao import Pagina, pagina
from toqqi.modulos.acoes import servico
from toqqi.modulos.acoes.esquemas import AcaoAlterarIn, AcaoIn, ConfigAcoesIn, FiltrosAcoes, FiltrosListaAcoes
from toqqi.modulos.acoes.passos import coletar_passos, sugerir_passos

router = APIRouter(prefix="/acoes", tags=["acoes"])
VER = requer("acoes.ver")
TRATAR = requer("acoes.tratar")


@router.get("/quadro")
def quadro(filtros: Annotated[FiltrosAcoes, Query()], ctx: Contexto = Depends(VER)):
    return servico.quadro(ctx, filtros)


@router.get("/configuracao")
def ver_config(ctx: Contexto = Depends(VER)):
    return servico.ver_config(ctx)


@router.put("/configuracao")
def salvar_config(dados: ConfigAcoesIn, ctx: Contexto = Depends(requer("configuracoes.gerenciar"))):
    return servico.salvar_config(ctx, dados)


@router.get("")
def listar(filtros: Annotated[FiltrosListaAcoes, Query()], pg: Pagina = Depends(pagina),
           ctx: Contexto = Depends(VER)):
    return servico.listar(ctx, filtros, pg)


@router.post("", status_code=201)
def criar(dados: AcaoIn, tarefas: BackgroundTasks, ctx: Contexto = Depends(TRATAR)):
    with coletar_passos() as passos:
        resultado = servico.criar(ctx, dados)
    tarefas.add_task(sugerir_passos, passos)  # passos sugeridos pela IA (ação de uma resposta), depois do commit
    return resultado


@router.get("/{acao_id}")
def obter(acao_id: int, ctx: Contexto = Depends(VER)):
    return servico.obter_acao(ctx, acao_id)


@router.patch("/{acao_id}")
def alterar(acao_id: int, dados: AcaoAlterarIn, ctx: Contexto = Depends(TRATAR)):
    return servico.alterar(ctx, acao_id, dados)


@router.delete("/{acao_id}", status_code=204)
def excluir(acao_id: int, ctx: Contexto = Depends(requer("acoes.excluir"))):
    servico.excluir(ctx, acao_id)
    return Response(status_code=204)
