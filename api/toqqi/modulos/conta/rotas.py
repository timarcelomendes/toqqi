from fastapi import APIRouter, Depends, File, Response, UploadFile

from toqqi.core.deps import Contexto, requer
from toqqi.modulos.conta import dados as dados_empresa
from toqqi.modulos.conta import marca, servico
from toqqi.modulos.conta.esquemas import DadosEmpresaIn, IaIn, MarcaIn, SegurancaIn
from toqqi.modulos.ia import servico as ia
from toqqi.modulos.imagens.servico import ler_envio

router = APIRouter(prefix="/conta", tags=["conta"])
GERENCIAR = requer("configuracoes.gerenciar")


@router.get("/seguranca")
def obter(ctx: Contexto = Depends(GERENCIAR)):
    return servico.obter(ctx)


@router.put("/seguranca")
def salvar(dados: SegurancaIn, ctx: Contexto = Depends(GERENCIAR)):
    return servico.salvar(ctx, dados)


# ---- dados da empresa e logo ----------------------------------------------------

@router.get("/dados")
def obter_dados(ctx: Contexto = Depends(GERENCIAR)):
    return dados_empresa.obter(ctx)


@router.put("/dados")
def salvar_dados(dados: DadosEmpresaIn, ctx: Contexto = Depends(GERENCIAR)):
    return dados_empresa.salvar(ctx, dados)


@router.put("/logo")
def trocar_logo(arquivo: UploadFile = File(...), ctx: Contexto = Depends(GERENCIAR)):
    conteudo, tipo = ler_envio(arquivo)
    return dados_empresa.trocar_logo(ctx, conteudo, tipo)


@router.delete("/logo", status_code=204)
def remover_logo(ctx: Contexto = Depends(GERENCIAR)):
    dados_empresa.remover_logo(ctx)
    return Response(status_code=204)


# ---- sua marca nas pesquisas (etapa 5h): a cor e se há logo --------------------------

@router.get("/marca")
def obter_marca(ctx: Contexto = Depends(requer())):
    """Para quem vê o Início (qualquer perfil da conta): {cor, tem_logo}."""
    return marca.obter(ctx)


@router.put("/marca")
def salvar_marca(dados: MarcaIn, ctx: Contexto = Depends(GERENCIAR)):
    return marca.salvar(ctx, dados.cor)


# ---- IA (Configurações › IA) --------------------------------------------------------

@router.get("/ia")
def obter_ia(ctx: Contexto = Depends(GERENCIAR)):
    return ia.obter(ctx)


@router.put("/ia")
def salvar_ia(dados: IaIn, ctx: Contexto = Depends(GERENCIAR)):
    return ia.salvar(ctx, dados)


@router.post("/ia/analisar-recentes")
def analisar_recentes(ctx: Contexto = Depends(GERENCIAR)):
    return ia.analisar_recentes(ctx)
