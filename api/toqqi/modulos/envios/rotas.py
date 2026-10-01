import hmac
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query

from toqqi.core.config import config
from toqqi.core.deps import Contexto, requer
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.paginacao import Pagina, pagina
from toqqi.modulos.envios import descadastro, servico
from toqqi.modulos.envios.esquemas import ConfigIn, DescadastroManualIn, DispararIn, FiltrosFila, FiltrosHistorico
from toqqi.modulos.envios.processamento import processar_lista
from toqqi.tarefas import executar

router = APIRouter(prefix="/envios", tags=["envios"])
router_interno = APIRouter(prefix="/interno", tags=["infra"])


def _agendar(tarefas: BackgroundTasks, resultado: tuple[dict, list]) -> dict:
    corpo, envios = resultado
    if envios:
        tarefas.add_task(processar_lista, envios)
    return corpo


@router.get("/pre-condicoes")
def pre_condicoes(ctx: Contexto = Depends(requer("envios.ver"))):
    return servico.ver_pre_condicoes(ctx)


@router.get("/configuracao")
def ver_config(ctx: Contexto = Depends(requer("envios.ver"))):
    return servico.ver_config(ctx)


@router.put("/configuracao")
def salvar_config(dados: ConfigIn, ctx: Contexto = Depends(requer("configuracoes.gerenciar"))):
    return servico.salvar_config(ctx, dados)


@router.post("/configuracao/teste")
def teste(ctx: Contexto = Depends(requer("configuracoes.gerenciar"))):
    return servico.enviar_teste(ctx)


@router.get("/resumo")
def resumo(ctx: Contexto = Depends(requer("envios.ver"))):
    return servico.resumo(ctx)


@router.get("/contatos")
def contatos(filtros: Annotated[FiltrosFila, Query()], pg: Pagina = Depends(pagina),
             ctx: Contexto = Depends(requer("envios.ver"))):
    return servico.listar_contatos(ctx, filtros, pg)


@router.post("/disparar", status_code=202)
def disparar(dados: DispararIn, tarefas: BackgroundTasks, ctx: Contexto = Depends(requer("envios.disparar"))):
    return _agendar(tarefas, servico.disparar(ctx, dados))


@router.post("/{envio_id}/tentar-de-novo", status_code=202)
def tentar_de_novo(envio_id: int, tarefas: BackgroundTasks, ctx: Contexto = Depends(requer("envios.disparar"))):
    return _agendar(tarefas, servico.tentar_de_novo(ctx, envio_id))


@router.get("/historico")
def historico(filtros: Annotated[FiltrosHistorico, Query()], pg: Pagina = Depends(pagina),
              ctx: Contexto = Depends(requer("envios.ver"))):
    return servico.historico(ctx, filtros, pg)


@router.get("/lembretes/previa")
def previa_lembretes(ctx: Contexto = Depends(requer("envios.ver"))):
    return servico.previa_lembretes(ctx)


@router.post("/lembretes/executar")
def executar_lembretes(tarefas: BackgroundTasks, ctx: Contexto = Depends(requer("envios.disparar"))):
    return _agendar(tarefas, servico.executar_lembretes(ctx))


@router.post("/robo/executar")
def executar_robo(tarefas: BackgroundTasks, ctx: Contexto = Depends(requer("envios.disparar"))):
    return _agendar(tarefas, servico.executar_robo(ctx))


@router.get("/descadastros")
def descadastros(busca: Annotated[str | None, Query(max_length=100)] = None, pg: Pagina = Depends(pagina),
                 ctx: Contexto = Depends(requer("envios.ver"))):
    return descadastro.listar(ctx, pg, (busca or "").strip() or None)


@router.post("/descadastros", status_code=201)
def adicionar_descadastro(dados: DescadastroManualIn, ctx: Contexto = Depends(requer("contatos.editar"))):
    return descadastro.adicionar(ctx, dados)


@router_interno.post("/tarefas")
def tarefas(x_tarefas_token: Annotated[str | None, Header()] = None):
    """Chamada pelo agendador externo (a cada hora). Comparação do token em tempo constante."""
    esperado = config().TAREFAS_TOKEN
    if not esperado:
        raise nao_encontrado()
    if not x_tarefas_token or not hmac.compare_digest(x_tarefas_token.encode(), esperado.encode()):
        raise AppError(401, "token_invalido", "Token de tarefas inválido.")
    return executar("tudo")
