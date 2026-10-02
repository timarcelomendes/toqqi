from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from toqqi.core.deps import Contexto, requer
from toqqi.core.filtros import DataFiltro
from toqqi.core.paginacao import Pagina, pagina
from toqqi.modulos.ia import pareceres
from toqqi.modulos.relatorios import servico
from toqqi.modulos.relatorios.parecer_ia import TIPO as PARECER_IA
from toqqi.modulos.relatorios.regras import FAIXAS_TEMPO, FAIXAS_VALOR, QUADRANTES, ROTULOS_DIMENSAO
from toqqi.modulos.respostas.esquemas import Busca, Id, Opcional
from toqqi.modulos.respostas.rotas import csv_resposta

router = APIRouter(prefix="/relatorios", tags=["relatorios"])
VER = requer("relatorios.ver")
EXPORTAR = requer("relatorios.ver", "painel.exportar")

FaixaValor = Literal[tuple(k for k, _ in FAIXAS_VALOR)]  # type: ignore[valid-type]
TempoCliente = Literal[tuple(k for k, _ in FAIXAS_TEMPO)]  # type: ignore[valid-type]
Quadrante = Literal[tuple(QUADRANTES)]  # type: ignore[valid-type]
Dimensao = Literal[tuple(ROTULOS_DIMENSAO)]  # type: ignore[valid-type]


class FiltrosComuns(BaseModel):
    de: DataFiltro = None
    ate: DataFiltro = None
    grupo_id: Id = None
    so_ativos: Annotated[bool | None, Opcional] = None  # vazio = true


class FiltrosEmpresa(FiltrosComuns):
    segmento_id: Id = None  # 0 = sem segmento
    responsavel_id: Id = None  # 0 = sem responsável
    faixa_valor: Annotated[FaixaValor | None, Opcional] = None
    tempo_cliente: Annotated[TempoCliente | None, Opcional] = None


class FiltrosEmpresas(FiltrosEmpresa):
    busca: Busca = None
    respostas: Annotated[Literal["com", "sem"] | None, Opcional] = None
    quadrante: Annotated[Quadrante | None, Opcional] = None
    ordem: Annotated[Literal["prioridade", "nps", "valor", "cobertura", "respostas", "nome"] | None, Opcional] = None


class FiltrosGrupos(FiltrosComuns):
    segmento_id: Id = None
    faixa_valor: Annotated[FaixaValor | None, Opcional] = None
    tempo_cliente: Annotated[TempoCliente | None, Opcional] = None


class FiltrosEntregas(FiltrosComuns):
    dimensao: Annotated[Dimensao | None, Opcional] = None  # vazio = motorista
    busca: Busca = None
    ordem: Annotated[Literal["respostas", "nps", "csat", "reclamacoes", "valor"] | None, Opcional] = None

    def model_post_init(self, _contexto) -> None:
        self.dimensao = self.dimensao or "motorista"


class Periodo(BaseModel):
    de: DataFiltro = None
    ate: DataFiltro = None


@router.get("/empresas")
def empresas(filtros: Annotated[FiltrosEmpresas, Query()], pg: Pagina = Depends(pagina), ctx: Contexto = Depends(VER)):
    return servico.empresas(ctx, filtros, pg)


@router.get("/empresas.csv")
def empresas_csv(filtros: Annotated[FiltrosEmpresas, Query()], ctx: Contexto = Depends(EXPORTAR)):
    return csv_resposta(servico.empresas_csv(ctx, filtros), servico.nome_csv("relatorio-empresas"))


@router.get("/grupos")
def grupos(filtros: Annotated[FiltrosGrupos, Query()], ctx: Contexto = Depends(VER)):
    return servico.grupos(ctx, filtros)


@router.get("/temas")
def temas(filtros: Annotated[FiltrosComuns, Query()], ctx: Contexto = Depends(VER)):
    return servico.temas(ctx, filtros)


@router.get("/entregas")
def entregas(filtros: Annotated[FiltrosEntregas, Query()], pg: Pagina = Depends(pagina), ctx: Contexto = Depends(VER)):
    return servico.entregas(ctx, filtros, pg)


@router.get("/entregas.csv")
def entregas_csv(filtros: Annotated[FiltrosEntregas, Query()], ctx: Contexto = Depends(EXPORTAR)):
    return csv_resposta(servico.entregas_csv(ctx, filtros), servico.nome_csv(f"relatorio-{filtros.dimensao}"))


@router.get("/responsaveis")
def responsaveis(filtros: Annotated[FiltrosComuns, Query()], ctx: Contexto = Depends(VER)):
    return servico.responsaveis(ctx, filtros)


@router.get("/responsaveis.csv")
def responsaveis_csv(filtros: Annotated[FiltrosComuns, Query()], ctx: Contexto = Depends(EXPORTAR)):
    return csv_resposta(servico.responsaveis_csv(ctx, filtros), servico.nome_csv("relatorio-responsaveis"))


@router.get("/responsaveis/{responsavel_id}/empresas")
def empresas_do_responsavel(responsavel_id: int, filtros: Annotated[FiltrosComuns, Query()],
                            ctx: Contexto = Depends(VER)):
    return servico.empresas_do_responsavel(ctx, responsavel_id, filtros)


@router.get("/operacao")
def operacao(filtros: Annotated[FiltrosComuns, Query()], ctx: Contexto = Depends(VER)):
    return servico.operacao(ctx, filtros)


# ---- parecer da IA (etapa 5d) ---------------------------------------------------------

@router.get("/parecer-ia")
def parecer_ia(filtros: Annotated[FiltrosComuns, Query()], ctx: Contexto = Depends(VER)):
    return pareceres.estado(ctx, PARECER_IA, pareceres.Recorte.dos_filtros(filtros))


@router.post("/parecer-ia")
def gerar_parecer_ia(dados: FiltrosComuns | None = None, ctx: Contexto = Depends(VER)):
    # síncrona: segura uma thread da API por até 45 s; as vagas do assistente limitam quantas ao mesmo tempo
    return pareceres.gerar(ctx, PARECER_IA, pareceres.Recorte.dos_filtros(dados or FiltrosComuns()))


@router.get("/operacao/sem-resposta.csv")
def sem_resposta_csv(filtros: Annotated[FiltrosComuns, Query()], ctx: Contexto = Depends(EXPORTAR)):
    return csv_resposta(servico.sem_resposta_csv(ctx, filtros), servico.nome_csv("contatos-sem-resposta"))


# o .csv vem antes: "/historico/12.csv" também casaria com "/historico/{empresa_id}"
@router.get("/historico/{empresa_id}.csv")
def historico_csv(empresa_id: int, filtros: Annotated[Periodo, Query()], ctx: Contexto = Depends(EXPORTAR)):
    return csv_resposta(servico.historico_csv(ctx, empresa_id, filtros.de, filtros.ate),
                        servico.nome_csv(f"historico-empresa-{empresa_id}"))


@router.get("/historico/{empresa_id}")
def historico(empresa_id: int, filtros: Annotated[Periodo, Query()], ctx: Contexto = Depends(VER)):
    return servico.historico(ctx, empresa_id, filtros.de, filtros.ate)
