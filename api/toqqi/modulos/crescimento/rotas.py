"""Crescimento (etapa 5c): indicações, oportunidades, ofertas, resumo e Configurações › Crescimento.

Ver pede `crescimento.ver`; alterar (indicações e ofertas) pede `crescimento.ver` e `crescimento.tratar`: as rotas que
alteram devolvem o registro inteiro, então "tratar" sem "ver" leria tudo percorrendo os ids."""
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query, Response

from toqqi.core.deps import Contexto, contexto_atual, requer
from toqqi.core.errors import AppError
from toqqi.core.paginacao import Pagina, pagina
from toqqi.core.validacao import MAX_ID
from toqqi.modulos.crescimento import configuracao, indicacoes, oportunidades
from toqqi.modulos.crescimento.esquemas import (
    ConfigCrescimentoIn,
    FiltrosIndicacoes,
    FiltrosOportunidades,
    IndicacaoAlterarIn,
    IndicacaoIn,
    OfertaAlterarIn,
    OfertaIn,
    PeriodoIn,
)
from toqqi.modulos.integracoes.webhooks import coletar_entregas, entregar_lista
from toqqi.modulos.respostas.rotas import csv_resposta

router = APIRouter(prefix="/crescimento", tags=["crescimento"])
VER = requer("crescimento.ver")
TRATAR = requer("crescimento.ver", "crescimento.tratar")  # `requer` exige todas
EXPORTAR = requer("crescimento.ver", "painel.exportar")
GERENCIAR = requer("configuracoes.gerenciar")
IdCaminho = Annotated[int, Path(ge=1, le=MAX_ID)]  # fora do bigint: 422 (e não erro do banco)


def ver_configuracao(ctx: Contexto = Depends(contexto_atual)) -> Contexto:
    """A configuração é lida pela tela do Crescimento (`crescimento.ver`) e por quem a altera
    (`configuracoes.gerenciar`)."""
    if not {"crescimento.ver", "configuracoes.gerenciar"} & set(ctx.permissoes):
        raise AppError(403, "sem_permissao", "Seu perfil não tem permissão para fazer isso.")
    return ctx


# ---- indicações -------------------------------------------------------------------------

@router.get("/indicacoes")
def listar_indicacoes(filtros: Annotated[FiltrosIndicacoes, Query()], pg: Pagina = Depends(pagina),
                      ctx: Contexto = Depends(VER)):
    return indicacoes.listar(ctx, filtros, pg)


@router.get("/indicacoes.csv")
def indicacoes_csv(filtros: Annotated[FiltrosIndicacoes, Query()], ctx: Contexto = Depends(EXPORTAR)):
    return csv_resposta(indicacoes.exportar_csv(ctx, filtros), indicacoes.nome_csv())


@router.post("/indicacoes", status_code=201)
def criar_indicacao(dados: IndicacaoIn, tarefas: BackgroundTasks, ctx: Contexto = Depends(TRATAR)):
    with coletar_entregas() as entregas:
        item = indicacoes.criar(ctx, dados)
    tarefas.add_task(entregar_lista, entregas)  # webhook indicacao.criada, depois do commit
    return item


@router.patch("/indicacoes/{indicacao_id}")
def alterar_indicacao(indicacao_id: IdCaminho, dados: IndicacaoAlterarIn, tarefas: BackgroundTasks,
                      ctx: Contexto = Depends(TRATAR)):
    with coletar_entregas() as entregas:
        item = indicacoes.alterar(ctx, indicacao_id, dados)
    tarefas.add_task(entregar_lista, entregas)  # webhook indicacao.atualizada, depois do commit
    return item


@router.delete("/indicacoes/{indicacao_id}", status_code=204)
def excluir_indicacao(indicacao_id: IdCaminho, ctx: Contexto = Depends(TRATAR)):
    indicacoes.excluir(ctx, indicacao_id)
    return Response(status_code=204)


# ---- oportunidades e ofertas ------------------------------------------------------------

@router.get("/oportunidades")
def listar_oportunidades(filtros: Annotated[FiltrosOportunidades, Query()], pg: Pagina = Depends(pagina),
                         ctx: Contexto = Depends(VER)):
    return oportunidades.listar(ctx, filtros, pg)


@router.get("/oportunidades.csv")
def oportunidades_csv(filtros: Annotated[FiltrosOportunidades, Query()], ctx: Contexto = Depends(EXPORTAR)):
    return csv_resposta(oportunidades.exportar_csv(ctx, filtros), oportunidades.nome_csv(filtros.lista))


@router.post("/ofertas", status_code=201)
def criar_oferta(dados: OfertaIn, ctx: Contexto = Depends(TRATAR)):
    return oportunidades.criar_oferta(ctx, dados)


@router.patch("/ofertas/{oferta_id}")
def alterar_oferta(oferta_id: IdCaminho, dados: OfertaAlterarIn, ctx: Contexto = Depends(TRATAR)):
    return oportunidades.alterar_oferta(ctx, oferta_id, dados)


@router.get("/resumo")
def resumo(filtros: Annotated[PeriodoIn, Query()], ctx: Contexto = Depends(VER)):
    return oportunidades.resumo(ctx, filtros.de, filtros.ate)


# ---- configuração -----------------------------------------------------------------------

@router.get("/configuracao")
def ver_config(ctx: Contexto = Depends(ver_configuracao)):
    return configuracao.ver(ctx)


@router.put("/configuracao")
def salvar_config(dados: ConfigCrescimentoIn, ctx: Contexto = Depends(GERENCIAR)):
    return configuracao.salvar(ctx, dados)
