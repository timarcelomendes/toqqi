"""Operações da equipe Toqqi (superadmin) sobre as contas.

Usa modo sistema de propósito: aqui a pessoa age sobre contas que não são a dela.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from toqqi.core.auditoria import registrar
from toqqi.core.db import modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.permissoes import semear_padrao
from toqqi.core.security import gerar_hash
from toqqi.modelos import (
    Acao,
    Auditoria,
    Cargo,
    ConfigAcoes,
    ConfigEnvios,
    Conta,
    Contato,
    Convite,
    Descadastro,
    DominioLiberado,
    Empresa,
    Envio,
    Formulario,
    Grupo,
    Imagem,
    Importacao,
    PerfilContato,
    PerfilPermissao,
    Responsavel,
    Resposta,
    Segmento,
    Sessao,
    TokenUsoUnico,
    Usuario,
)
from toqqi.modulos.acesso.servico import DIAS_TESTE
from toqqi.modulos.formularios.semear import semear_conta


def _conta_json(c: Conta, usuarios: int) -> dict:
    return {
        "id": c.id, "nome": c.nome, "plano": c.plano, "situacao": c.situacao,
        "teste_ate": c.teste_ate, "usuarios": usuarios, "criada_em": c.criada_em,
    }


def _contar_usuarios(s, conta_id: int) -> int:
    return s.scalar(select(func.count()).select_from(Usuario).where(Usuario.conta_id == conta_id))


def listar() -> list[dict]:
    contagem = (
        select(Usuario.conta_id, func.count().label("n")).group_by(Usuario.conta_id).subquery()
    )
    with modo_sistema() as s:
        linhas = s.execute(
            select(Conta, func.coalesce(contagem.c.n, 0))
            .outerjoin(contagem, contagem.c.conta_id == Conta.id)
            .order_by(Conta.criada_em.desc(), Conta.id.desc())
        ).all()
    return [_conta_json(c, n) for c, n in linhas]


def criar_conta(ctx: Contexto, dados) -> dict:
    senha_hash = gerar_hash(dados.admin_senha)
    try:
        with modo_sistema() as s:
            teste_ate = datetime.now(timezone.utc) + timedelta(days=DIAS_TESTE) if dados.situacao == "teste" else None
            conta = Conta(nome=dados.empresa, situacao=dados.situacao, teste_ate=teste_ate)
            s.add(conta)
            s.flush()
            u = Usuario(conta_id=conta.id, nome=dados.admin_nome, email=dados.admin_email, senha_hash=senha_hash,
                        perfil="admin", situacao="ativo", email_confirmado=True)
            s.add(u)
            s.flush()
            semear_padrao(s, conta.id)
            semear_conta(s, conta.id)
            registrar(s, "conta_criada_plataforma", "info",
                      {"por": ctx.email, "situacao": dados.situacao, "admin_email": u.email}, conta_id=conta.id)
            s.refresh(conta)
            return _conta_json(conta, 1)
    except IntegrityError:
        msg = "Este e-mail já está em uso no Toqqi."
        raise AppError(409, "email_em_uso", msg, {"admin_email": msg})


def _conta_travada(s, conta_id: int) -> Conta:
    c = s.get(Conta, conta_id, with_for_update=True)
    if c is None:
        raise nao_encontrado("Conta não encontrada.")
    return c


def estender_teste(ctx: Contexto, conta_id: int, dias: int) -> dict:
    with modo_sistema() as s:
        c = _conta_travada(s, conta_id)
        agora = s.scalar(select(func.now()))
        anterior = c.teste_ate
        base = max(agora, anterior) if anterior else agora
        c.teste_ate = base + timedelta(days=dias)
        c.situacao = "teste"
        registrar(s, "teste_estendido", "info",
                  {"por": ctx.email, "dias": dias, "teste_ate_anterior": anterior.isoformat() if anterior else None,
                   "teste_ate_novo": c.teste_ate.isoformat()}, conta_id=c.id)
        s.flush()
        return _conta_json(c, _contar_usuarios(s, c.id))


def cortesia(ctx: Contexto, conta_id: int) -> dict:
    with modo_sistema() as s:
        c = _conta_travada(s, conta_id)
        anterior = c.situacao
        c.situacao = "cortesia"
        registrar(s, "cortesia", "info", {"por": ctx.email, "situacao_anterior": anterior}, conta_id=c.id)
        s.flush()
        return _conta_json(c, _contar_usuarios(s, c.id))


# Ordem de exclusão: quem aponta para outras tabelas da conta sai antes.
_ORDEM_EXCLUSAO = (Acao, ConfigAcoes, Envio, Descadastro, ConfigEnvios, Resposta, Convite, Importacao, Contato,
                   Empresa, Responsavel, Grupo, Segmento, PerfilContato, Cargo, Imagem, Formulario, Auditoria,
                   DominioLiberado, PerfilPermissao, TokenUsoUnico, Sessao, Usuario)


def excluir_conta(ctx: Contexto, conta_id: int, confirmar_nome: str) -> None:
    """Apaga a conta e todos os dados dela. Auditoria global (sem conta), visível só na plataforma."""
    with modo_sistema() as s:
        c = _conta_travada(s, conta_id)
        if c.id == ctx.conta_id:
            raise AppError(409, "propria_conta", "Você não pode excluir a conta que está usando.")
        if " ".join(confirmar_nome.split()).casefold() != " ".join(c.nome.split()).casefold():
            msg = "O nome digitado não confere com o nome da conta."
            raise AppError(409, "nome_nao_confere", msg, {"confirmar_nome": msg})
        conta = {"id": c.id, "nome": c.nome}
        usuarios = _contar_usuarios(s, c.id)
        for modelo in _ORDEM_EXCLUSAO:
            s.execute(delete(modelo).where(modelo.conta_id == conta["id"]))
        s.execute(delete(Conta).where(Conta.id == conta["id"]))
        registrar(s, "conta_excluida", "atencao", {"conta": conta, "usuarios": usuarios, "por": ctx.email})
