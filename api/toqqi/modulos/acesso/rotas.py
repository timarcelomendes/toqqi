import uuid

from fastapi import APIRouter, Depends, Request, Response

from toqqi.core.deps import Contexto, requer
from toqqi.core.rate_limit import LIMITE_ENTRAR, LIMITE_SENSIVEL, limiter
from toqqi.core.security import SENHA_MAX, SENHA_MIN
from toqqi.modulos.acesso import servico
from toqqi.modulos.acesso.esquemas import (
    CadastroIn,
    EmailIn,
    EntrarIn,
    EuAlterarIn,
    PedirAcessoIn,
    RedefinirIn,
    TokenIn,
    TrocarSenhaIn,
)

router = APIRouter(tags=["acesso"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/auth/cadastro", status_code=201)
@limiter.limit(LIMITE_SENSIVEL)
def cadastro(request: Request, dados: CadastroIn):
    return {"mensagem": servico.cadastrar(dados, _ip(request))}


@router.post("/auth/entrar")
@limiter.limit(LIMITE_ENTRAR)
def entrar(request: Request, dados: EntrarIn):
    return servico.entrar(dados, _ip(request), request.headers.get("user-agent"))


@router.post("/auth/confirmar-email")
def confirmar_email(dados: TokenIn):
    return {"mensagem": servico.confirmar_email(dados.token)}


@router.post("/auth/reenviar-confirmacao")
@limiter.limit(LIMITE_SENSIVEL)
def reenviar_confirmacao(request: Request, dados: EmailIn):
    return {"mensagem": servico.reenviar_confirmacao(dados.email)}


@router.post("/auth/esqueci-senha")
@limiter.limit(LIMITE_SENSIVEL)
def esqueci_senha(request: Request, dados: EmailIn):
    return {"mensagem": servico.esqueci_senha(dados.email)}


@router.post("/auth/redefinir-senha")
@limiter.limit(LIMITE_SENSIVEL)
def redefinir_senha(request: Request, dados: RedefinirIn):
    return {"mensagem": servico.redefinir_senha(dados.token, dados.senha)}


@router.post("/auth/pedir-acesso")
@limiter.limit(LIMITE_SENSIVEL)
def pedir_acesso(request: Request, dados: PedirAcessoIn):
    return {"mensagem": servico.pedir_acesso(dados)}


@router.get("/auth/regras-senha")
def regras_senha():
    return {"minimo": SENHA_MIN, "maximo": SENHA_MAX, "exige": ["maiuscula", "numero", "simbolo"]}


@router.post("/auth/sair", status_code=204)
def sair(ctx: Contexto = Depends(requer())):
    servico.sair(ctx)
    return Response(status_code=204)


@router.get("/eu")
def eu(ctx: Contexto = Depends(requer())):
    return servico.eu(ctx)


@router.patch("/eu")
def alterar_eu(dados: EuAlterarIn, ctx: Contexto = Depends(requer())):
    return servico.alterar_eu(ctx, dados)


@router.post("/eu/senha")
def trocar_senha(dados: TrocarSenhaIn, ctx: Contexto = Depends(requer())):
    return {"mensagem": servico.trocar_senha(ctx, dados)}


@router.get("/eu/sessoes")
def listar_sessoes(ctx: Contexto = Depends(requer())):
    return servico.listar_sessoes(ctx)


@router.post("/eu/sessoes/encerrar-outras", status_code=204)
def encerrar_outras(ctx: Contexto = Depends(requer())):
    servico.encerrar_outras(ctx)
    return Response(status_code=204)


@router.delete("/eu/sessoes/{sessao_id}", status_code=204)
def encerrar_sessao(sessao_id: uuid.UUID, ctx: Contexto = Depends(requer())):
    servico.encerrar_sessao(ctx, sessao_id)
    return Response(status_code=204)
