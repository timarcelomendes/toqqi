"""Rotas do feedback (docs/api-feedback.md §3 e §4): /feedback (qualquer usuário logado, só os próprios) e
/plataforma/feedback (só superadmin). As imagens saem só por estas rotas, com o token no cabeçalho (nunca por URL
pública): o site busca como blob."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field

from toqqi.core.deps import Contexto, requer, requer_superadmin
from toqqi.core.rate_limit import LIMITE_FEEDBACK, LIMITE_FEEDBACK_MENSAGEM, limite_por_usuario, limiter
from toqqi.core.validacao import MAX_ID
from toqqi.modulos.feedback import plataforma, servico

router = APIRouter(prefix="/feedback", tags=["feedback"])
router_plataforma = APIRouter(prefix="/plataforma/feedback", tags=["plataforma"])

Id = Annotated[int, Path(ge=1, le=MAX_ID)]
FormTexto = Annotated[str | None, Form()]
Imagens = Annotated[list[UploadFile] | None, File()]
LOGADO = requer()


class AutorizacaoIn(BaseModel):
    autoriza_depoimento: bool


class RespostaEquipeIn(BaseModel):
    texto: str = Field(default="", max_length=20000)
    situacao: str | None = Field(default=None, max_length=40)


class AlteracaoEquipeIn(BaseModel):
    situacao: str | None = Field(default=None, max_length=40)
    nota_interna: str | None = Field(default=None, max_length=20000)


def _imagem(dados: bytes, tipo: str) -> Response:
    return Response(content=dados, media_type=tipo, headers={
        "Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'", "Content-Disposition": "inline"})


# ---- quem usa -----------------------------------------------------------------------------------------------------

@router.get("")
def listar(ctx: Contexto = Depends(LOGADO)):
    return servico.listar(ctx)


@router.get("/novidades")
def novidades(ctx: Contexto = Depends(LOGADO)):
    return servico.novidades(ctx)


@router.post("", status_code=201)
@limiter.limit(LIMITE_FEEDBACK, key_func=limite_por_usuario)
def criar(
    request: Request,
    tipo: FormTexto = None,
    texto: FormTexto = None,
    impacto: FormTexto = None,
    autoriza_depoimento: Annotated[bool, Form()] = False,
    detalhes: Annotated[bool, Form()] = True,
    pagina: FormTexto = None,
    pagina_titulo: FormTexto = None,
    tela: FormTexto = None,
    versao_site: FormTexto = None,
    diagnostico: FormTexto = None,
    imagens: Imagens = None,
    ctx: Contexto = Depends(LOGADO),
):
    """multipart/form-data: tipo, texto, impacto (só erro), autoriza_depoimento (só elogio), detalhes (padrão sim:
    navegador, tela, versão e diagnóstico), pagina, pagina_titulo, tela, versao_site, diagnostico (JSON) e até 3
    `imagens` (PNG ou JPG de até 1 MB)."""
    dados = {"tipo": tipo, "texto": texto, "impacto": impacto, "autoriza_depoimento": autoriza_depoimento,
             "detalhes": detalhes, "pagina": pagina, "pagina_titulo": pagina_titulo, "tela": tela,
             "versao_site": versao_site, "diagnostico": diagnostico}
    return servico.criar(ctx, dados, imagens, request.headers.get("user-agent"))


@router.get("/{feedback_id}")
def detalhe(feedback_id: Id, ctx: Contexto = Depends(LOGADO)):
    return servico.detalhe(ctx, feedback_id)


@router.patch("/{feedback_id}")
def alterar(feedback_id: Id, dados: AutorizacaoIn, ctx: Contexto = Depends(LOGADO)):
    return servico.alterar(ctx, feedback_id, dados.autoriza_depoimento)


@router.post("/{feedback_id}/mensagens", status_code=201)
@limiter.limit(LIMITE_FEEDBACK_MENSAGEM, key_func=limite_por_usuario)
def responder(request: Request, feedback_id: Id, texto: FormTexto = None, imagens: Imagens = None,
              ctx: Contexto = Depends(LOGADO)):
    """multipart/form-data: texto e/ou até 3 `imagens`. Devolve o feedback com a conversa."""
    return servico.responder(ctx, feedback_id, texto, imagens)


@router.get("/{feedback_id}/imagens/{imagem_id}")
def imagem(feedback_id: Id, imagem_id: Id, ctx: Contexto = Depends(LOGADO)):
    return _imagem(*servico.imagem(ctx, feedback_id, imagem_id))


# ---- equipe Toqqi (Plataforma › Feedback) ------------------------------------------------------------------------

@router_plataforma.get("")
def listar_plataforma(
    tipo: Annotated[Literal["", "erro", "sugestao", "melhoria", "elogio"] | None, Query()] = None,
    situacao: Annotated[Literal["abertos", "concluidos", "encerrados", "todos"], Query()] = "abertos",
    busca: Annotated[str | None, Query(max_length=200)] = None,
    ctx: Contexto = Depends(requer_superadmin),
):
    return plataforma.listar(tipo or None, situacao, busca)


@router_plataforma.get("/contagem")
def contagem(ctx: Contexto = Depends(requer_superadmin)):
    return plataforma.contagem()


@router_plataforma.get("/{feedback_id}")
def detalhe_plataforma(feedback_id: Id, ctx: Contexto = Depends(requer_superadmin)):
    return plataforma.detalhe(feedback_id)


@router_plataforma.post("/{feedback_id}/mensagens", status_code=201)
def responder_plataforma(feedback_id: Id, dados: RespostaEquipeIn, ctx: Contexto = Depends(requer_superadmin)):
    return plataforma.responder(ctx, feedback_id, dados.texto, dados.situacao)


@router_plataforma.patch("/{feedback_id}")
def alterar_plataforma(feedback_id: Id, dados: AlteracaoEquipeIn, ctx: Contexto = Depends(requer_superadmin)):
    return plataforma.alterar(ctx, feedback_id, dados.situacao, dados.nota_interna)


@router_plataforma.get("/{feedback_id}/imagens/{imagem_id}")
def imagem_plataforma(feedback_id: Id, imagem_id: Id, ctx: Contexto = Depends(requer_superadmin)):
    return _imagem(*plataforma.imagem(feedback_id, imagem_id))
