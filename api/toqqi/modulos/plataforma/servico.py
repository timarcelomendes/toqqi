"""Operações da equipe Toqqi (superadmin) sobre as contas.

Usa modo sistema de propósito: aqui a pessoa age sobre contas que não são a dela.
Etapa 5a: "+14 dias" não vale para conta com assinatura ativa nem cortesia; marcar cortesia (e excluir a conta)
remove antes a assinatura no Asaas (se falhar, 503 e nada muda).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError

from toqqi.core.auditoria import registrar
from toqqi.core.db import modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.permissoes import semear_padrao
from toqqi.core.security import gerar_hash
from toqqi.modelos import (
    Acao,
    AceiteTermos,
    AlertaPico,
    Assinatura,
    Auditoria,
    Cargo,
    Cobranca,
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
    IaUsoMensal,
    Imagem,
    Importacao,
    PerfilContato,
    PerfilPermissao,
    Responsavel,
    Resposta,
    ResumoSemanal,
    Segmento,
    Sessao,
    TokenUsoUnico,
    Usuario,
)
from toqqi.modulos.acesso.servico import DIAS_TESTE
from toqqi.modulos.assinatura import servico as assinaturas
from toqqi.modulos.formularios.semear import semear_conta


def _conta_json(c: Conta, usuarios: int, a: Assinatura | None = None, admins: list[dict] | None = None) -> dict:
    """`assinatura` = a assinatura ativa ({plano, valor, situacao}) ou null; `admins` = administradores da conta, o
    mais antigo primeiro ([{nome, email, email_confirmado}])."""
    return {
        "id": c.id, "nome": c.nome, "plano": c.plano, "situacao": c.situacao,
        "teste_ate": c.teste_ate, "usuarios": usuarios, "criada_em": c.criada_em,
        "pago_ate": c.pago_ate, "atrasada_desde": c.atrasada_desde,
        "assinatura": {"plano": a.plano, "valor": a.valor, "situacao": a.situacao} if a is not None else None,
        "admins": admins or [],
    }


def _contar_usuarios(s, conta_id: int) -> int:
    return s.scalar(select(func.count()).select_from(Usuario).where(Usuario.conta_id == conta_id))


def _admins(s, conta_id: int | None = None) -> dict[int, list[dict]]:
    """Administradores por conta (de todas, ou só de `conta_id`), o mais antigo primeiro."""
    consulta = (select(Usuario.conta_id, Usuario.nome, Usuario.email, Usuario.email_confirmado)
                .where(Usuario.perfil == "admin").order_by(Usuario.conta_id, Usuario.id))
    if conta_id is not None:
        consulta = consulta.where(Usuario.conta_id == conta_id)
    por_conta: dict[int, list[dict]] = {}
    for dona, nome, email, confirmado in s.execute(consulta):
        por_conta.setdefault(dona, []).append({"nome": nome, "email": email, "email_confirmado": bool(confirmado)})
    return por_conta


def listar() -> list[dict]:
    contagem = (
        select(Usuario.conta_id, func.count().label("n")).group_by(Usuario.conta_id).subquery()
    )
    with modo_sistema() as s:
        linhas = s.execute(
            select(Conta, func.coalesce(contagem.c.n, 0), Assinatura)
            .outerjoin(contagem, contagem.c.conta_id == Conta.id)
            .outerjoin(Assinatura, and_(Assinatura.conta_id == Conta.id, Assinatura.situacao == "ativa",
                                        assinaturas.filtro_ambiente()))
            .order_by(Conta.criada_em.desc(), Conta.id.desc())
        ).all()
        admins = _admins(s)
    return [_conta_json(c, n, a, admins.get(c.id)) for c, n, a in linhas]


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
            return _conta_json(conta, 1, None, _admins(s, conta.id).get(conta.id))
    except IntegrityError:
        msg = "Este e-mail já está em uso no Toqqi."
        raise AppError(409, "email_em_uso", msg, {"admin_email": msg})


def _conta_travada(s, conta_id: int) -> Conta:
    c = s.get(Conta, conta_id, with_for_update=True)
    if c is None:
        raise nao_encontrado("Conta não encontrada.")
    return c


def estender_teste(ctx: Contexto, conta_id: int, dias: int) -> dict:
    """Soma a partir do fim do teste atual (ou de agora, se já acabou) e recalcula a situação (`teste`; `cancelada`
    enquanto o período pago for mais longo). 409 `assinatura_ativa` para conta com assinatura ativa ou cortesia."""
    with modo_sistema() as s:
        c = _conta_travada(s, conta_id)
        if c.situacao == "cortesia":
            raise AppError(409, "assinatura_ativa", "Conta cortesia não tem teste para estender.")
        if assinaturas.assinatura_ativa(s, c.id) is not None:
            raise AppError(409, "assinatura_ativa", "Esta conta tem assinatura ativa: o teste não pode ser estendido.")
        agora = s.scalar(select(func.now()))
        anterior = c.teste_ate
        base = max(agora, anterior) if anterior else agora
        c.teste_ate = base + timedelta(days=dias)
        assinaturas.recalcular(s, c)
        registrar(s, "teste_estendido", "info",
                  {"por": ctx.email, "dias": dias, "teste_ate_anterior": anterior.isoformat() if anterior else None,
                   "teste_ate_novo": c.teste_ate.isoformat()}, conta_id=c.id)
        s.flush()
        return _conta_json(c, _contar_usuarios(s, c.id), None, _admins(s, c.id).get(c.id))


def cortesia(ctx: Contexto, conta_id: int) -> dict:
    """Com assinatura ativa, remove antes no Asaas (falhou → 503 e nada muda) e a marca cancelada aqui."""
    with modo_sistema() as s:
        c = _conta_travada(s, conta_id)
        a = assinaturas.assinatura_ativa(s, c.id)
        if a is not None:
            assinaturas.remover_no_asaas(a.asaas_id)
            assinaturas.encerrar(s, a, None)
            registrar(s, "assinatura_cancelada", "atencao", {"plano": a.plano, "motivo": "cortesia", "por": ctx.email},
                      conta_id=c.id)
        anterior = c.situacao
        c.situacao = "cortesia"
        assinaturas.recalcular(s, c)  # cortesia não muda por cobrança; refaz atraso e primeiro vencimento
        registrar(s, "cortesia", "info", {"por": ctx.email, "situacao_anterior": anterior}, conta_id=c.id)
        s.flush()
        return _conta_json(c, _contar_usuarios(s, c.id), None, _admins(s, c.id).get(c.id))


# Ordem de exclusão: quem aponta para outras tabelas da conta sai antes.
_ORDEM_EXCLUSAO = (Cobranca, Assinatura, AlertaPico, ResumoSemanal, IaUsoMensal, Acao, ConfigAcoes, Envio,
                   Descadastro, ConfigEnvios, Resposta, Convite, Importacao, Contato, Empresa, Responsavel, Grupo, Segmento, PerfilContato, Cargo,
                   Imagem, Formulario, Auditoria, DominioLiberado, PerfilPermissao, TokenUsoUnico, Sessao, AceiteTermos, Usuario)


def excluir_conta(ctx: Contexto, conta_id: int, confirmar_nome: str) -> None:
    """Apaga a conta e todos os dados dela. Auditoria global (sem conta), visível só na plataforma. Remove antes no
    Asaas a assinatura ativa e qualquer outra viva com a referência da conta (senão ele seguiria cobrando; falhou → 503
    e nada é apagado)."""
    with modo_sistema() as s:
        c = _conta_travada(s, conta_id)
        if c.id == ctx.conta_id:
            raise AppError(409, "propria_conta", "Você não pode excluir a conta que está usando.")
        if " ".join(confirmar_nome.split()).casefold() != " ".join(c.nome.split()).casefold():
            msg = "O nome digitado não confere com o nome da conta."
            raise AppError(409, "nome_nao_confere", msg, {"confirmar_nome": msg})
        conta = {"id": c.id, "nome": c.nome}
        usuarios = _contar_usuarios(s, c.id)
        assinaturas.remover_vivas_no_asaas(c)  # todas as vivas com a referência da conta (falhou → 503)
        ativa = assinaturas.assinatura_ativa(s, c.id)
        if ativa is not None:
            assinaturas.remover_no_asaas(ativa.asaas_id)  # já removida acima (404) conta como removida
        for modelo in _ORDEM_EXCLUSAO:
            s.execute(delete(modelo).where(modelo.conta_id == conta["id"]))
        s.execute(delete(Conta).where(Conta.id == conta["id"]))
        registrar(s, "conta_excluida", "atencao", {"conta": conta, "usuarios": usuarios, "por": ctx.email})
