"""Regras da equipe: usuários da conta e matriz de permissões por perfil."""
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from toqqi.apresentacao import eh_superadmin, usuario_json
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.permissoes import CHAVES, SOMENTE_ADMIN, catalogo_json, ordenar
from toqqi.core.security import gerar_hash
from toqqi.modelos import PerfilPermissao, Usuario
from toqqi.modulos.acesso import emails
from toqqi.modulos.acesso.servico import criar_token, revogar_sessoes


def erro_email_em_uso() -> AppError:
    msg = "Este e-mail já está em uso no Toqqi."
    return AppError(409, "email_em_uso", msg, {"email": msg})


def erro_ultimo_admin() -> AppError:
    return AppError(409, "ultimo_admin",
                    "A conta precisa de pelo menos um administrador ativo. "
                    "Promova outra pessoa a administrador antes de fazer isso.")


def erro_si_mesmo() -> AppError:
    return AppError(409, "nao_pode_si_mesmo",
                    "Você não pode mudar o próprio perfil, a própria situação nem excluir a si mesmo. "
                    "Peça a outro administrador.")


def _usuario_ou_404(s: Session, usuario_id: int) -> Usuario:
    # RLS: usuário de outra conta simplesmente não existe aqui.
    u = s.get(Usuario, usuario_id, with_for_update=True)
    if u is None:
        raise nao_encontrado("Usuário não encontrado.")
    return u


def _sobraria_admin(s: Session, alvo: Usuario) -> bool:
    """Há outro admin ativo além do alvo? Trava as linhas para evitar corrida entre dois pedidos."""
    outros = s.scalars(
        select(Usuario.id)
        .where(Usuario.perfil == "admin", Usuario.situacao == "ativo", Usuario.id != alvo.id)
        .with_for_update()
    ).all()
    return len(outros) > 0


def listar(ctx: Contexto) -> list[dict]:
    with em_conta(ctx.conta_id) as s:
        return [usuario_json(u) for u in s.scalars(select(Usuario).order_by(Usuario.nome, Usuario.id))]


def criar(ctx: Contexto, dados) -> dict:
    # E-mails de superadmin da plataforma só podem ser criados pela própria plataforma:
    # um admin de conta qualquer não pode "reservar" esse e-mail já confirmado.
    if eh_superadmin(dados.email) and not ctx.superadmin:
        raise erro_email_em_uso()
    senha_hash = gerar_hash(dados.senha)
    with em_conta(ctx.conta_id) as s:
        u = Usuario(conta_id=ctx.conta_id, nome=dados.nome, email=dados.email, cargo=dados.cargo,
                    perfil=dados.perfil, senha_hash=senha_hash, situacao="ativo", email_confirmado=True)
        s.add(u)
        try:
            with s.begin_nested():
                s.flush()
        except IntegrityError:
            raise erro_email_em_uso()
        registrar(s, "usuario_criado", "sucesso",
                  {"nome": u.nome, "email": u.email, "perfil": u.perfil}, usuario_id=ctx.usuario_id)
        return usuario_json(u)


def alterar(ctx: Contexto, usuario_id: int, dados) -> dict:
    campos = dados.model_fields_set
    with em_conta(ctx.conta_id) as s:
        u = _usuario_ou_404(s, usuario_id)
        novo_perfil = dados.perfil if "perfil" in campos and dados.perfil else u.perfil
        nova_situacao = dados.situacao if "situacao" in campos and dados.situacao else u.situacao
        muda_acesso = novo_perfil != u.perfil or nova_situacao != u.situacao

        if muda_acesso:
            era_admin_ativo = u.perfil == "admin" and u.situacao == "ativo"
            continua_admin_ativo = novo_perfil == "admin" and nova_situacao == "ativo"
            if era_admin_ativo and not continua_admin_ativo and not _sobraria_admin(s, u):
                raise erro_ultimo_admin()
            if u.id == ctx.usuario_id:
                raise erro_si_mesmo()

        mudancas: dict[str, list] = {}
        novos = {
            "nome": dados.nome if "nome" in campos and dados.nome else u.nome,
            "cargo": (dados.cargo or None) if "cargo" in campos else u.cargo,
            "perfil": novo_perfil,
            "situacao": nova_situacao,
        }
        for campo, valor in novos.items():
            antes = getattr(u, campo)
            if antes != valor:
                mudancas[campo] = [antes, valor]
                setattr(u, campo, valor)
        if not mudancas:
            return usuario_json(u)

        bloqueou = mudancas.get("situacao", [None, None])[1] == "bloqueado"
        detalhe = {"usuario": {"id": u.id, "nome": u.nome, "email": u.email}, "mudancas": mudancas}
        if bloqueou:
            detalhe["sessoes_encerradas"] = revogar_sessoes(s, u.id)
            registrar(s, "usuario_bloqueado", "atencao", detalhe, usuario_id=ctx.usuario_id)
        else:
            registrar(s, "usuario_alterado", "info", detalhe, usuario_id=ctx.usuario_id)
        s.flush()
        return usuario_json(u)


def excluir(ctx: Contexto, usuario_id: int) -> None:
    with em_conta(ctx.conta_id) as s:
        u = _usuario_ou_404(s, usuario_id)
        if u.perfil == "admin" and u.situacao == "ativo" and not _sobraria_admin(s, u):
            raise erro_ultimo_admin()
        if u.id == ctx.usuario_id:
            raise erro_si_mesmo()
        detalhe = {"usuario": {"id": u.id, "nome": u.nome, "email": u.email, "perfil": u.perfil}}
        s.delete(u)
        s.flush()
        registrar(s, "usuario_excluido", "atencao", detalhe, usuario_id=ctx.usuario_id)


def reenviar_confirmacao(ctx: Contexto, usuario_id: int) -> str:
    with em_conta(ctx.conta_id) as s:
        u = _usuario_ou_404(s, usuario_id)
        if u.email_confirmado:
            return "O e-mail deste usuário já está confirmado."
        token = criar_token(s, u.id, ctx.conta_id, "confirmar_email")
        nome, email = u.nome, u.email
    emails.confirmar_email(nome, email, token, ctx.conta_id)
    return f"Enviamos um novo link de confirmação para {email}."


# ---- permissões -------------------------------------------------------------

def _matriz(s: Session) -> dict:
    linhas = s.execute(select(PerfilPermissao.perfil, PerfilPermissao.permissao)).all()
    return {
        "catalogo": catalogo_json(),
        "gestor": ordenar(p for perfil, p in linhas if perfil == "gestor"),
        "consulta": ordenar(p for perfil, p in linhas if perfil == "consulta"),
    }


def obter_permissoes(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return _matriz(s)


def salvar_permissoes(ctx: Contexto, dados) -> dict:
    novos = {"gestor": dados.gestor, "consulta": dados.consulta}
    campos = {}
    for perfil, perms in novos.items():
        desconhecidas = sorted({p for p in perms if p not in CHAVES})
        exclusivas = sorted({p for p in perms if p in SOMENTE_ADMIN})
        if desconhecidas:
            campos[perfil] = "Permissão desconhecida: " + ", ".join(desconhecidas) + "."
        elif exclusivas:
            campos[perfil] = "Estas permissões são exclusivas do administrador: " + ", ".join(exclusivas) + "."
    if campos:
        raise AppError(422, "dados_invalidos", "Confira as permissões escolhidas.", campos)

    with em_conta(ctx.conta_id) as s:
        antes = _matriz(s)
        s.execute(delete(PerfilPermissao))
        linhas = [
            {"conta_id": ctx.conta_id, "perfil": perfil, "permissao": p}
            for perfil, perms in novos.items()
            for p in sorted(set(perms))
        ]
        if linhas:
            s.execute(insert(PerfilPermissao), linhas)
        depois = _matriz(s)
        diferencas = {}
        for perfil in ("gestor", "consulta"):
            add = [p for p in depois[perfil] if p not in antes[perfil]]
            rem = [p for p in antes[perfil] if p not in depois[perfil]]
            if add or rem:
                diferencas[perfil] = {"adicionadas": add, "removidas": rem}
        if diferencas:
            registrar(s, "permissoes_alteradas", "atencao", diferencas, usuario_id=ctx.usuario_id)
        return depois
