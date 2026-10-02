"""Passos de subida em produção (Render e afins), todos idempotentes.

1. garantir_papel_app: cria/atualiza o papel restrito da aplicação (sem superusuário e sem BYPASSRLS),
   para o isolamento entre contas depender do banco e não só do código.
2. garantir_admin_inicial: cria a conta da plataforma e o primeiro admin (e-mail já confirmado),
   para existir um jeito de entrar antes de o envio de e-mails estar configurado. Só com o banco vazio:
   trocar ADMIN_INICIAL_EMAIL depois não cria outra conta.
"""
import logging
import re

from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError

from toqqi.core.config import config
from toqqi.core.db import modo_sistema, usar_url_app

log = logging.getLogger("toqqi")


def garantir_papel_app() -> None:
    cfg = config()
    if not cfg.APP_DB_PASSWORD:
        return
    papel = cfg.APP_DB_ROLE  # já validado no config (só [a-z0-9_])
    dono = create_engine(cfg.url_migracao, future=True, hide_parameters=True)
    try:
        with dono.begin() as c:
            existe = c.scalar(text("select 1 from pg_roles where rolname = :p"), {"p": papel})
            senha = c.scalar(text("select quote_literal(:s)"), {"s": cfg.APP_DB_PASSWORD})
            if existe:
                # (mudar SUPERUSER/BYPASSRLS, mesmo para "não", exige superusuário: só confere abaixo)
                c.execute(text(f"ALTER ROLE {papel} WITH LOGIN PASSWORD {senha}"))
            else:
                c.execute(text(f"CREATE ROLE {papel} WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE "
                               f"PASSWORD {senha}"))
            poderes = c.execute(text("select rolsuper or rolbypassrls from pg_roles where rolname = :p"),
                                {"p": papel}).scalar()
            if poderes:
                raise RuntimeError(f"o papel {papel} tem SUPERUSER ou BYPASSRLS e anularia o isolamento")
            banco = c.scalar(text("select current_database()"))
            c.execute(text(f'GRANT CONNECT ON DATABASE "{banco}" TO {papel}'))
        log.info("Papel restrito %s pronto; a aplicação vai se conectar com ele.", papel)
    except (SQLAlchemyError, RuntimeError) as e:
        motivo = str(getattr(e, "orig", e)).splitlines()[0][:200]
        log.warning("Não foi possível criar o papel restrito %s (%s). A aplicação vai usar a conexão do dono "
                    "do banco; o RLS com FORCE continua valendo, mas o ideal é criar o papel à mão.",
                    papel, motivo)
        usar_url_app(cfg.url_migracao)
    finally:
        dono.dispose()


def _mascarar(email: str) -> str:
    """Não escreve o e-mail inteiro no log: fu***@dominio.com."""
    nome, _, dominio = email.partition("@")
    return f"{nome[:2]}***@{dominio}"


def garantir_admin_inicial() -> None:
    cfg = config()
    email = cfg.ADMIN_INICIAL_EMAIL.strip().lower()
    if not email or not cfg.ADMIN_INICIAL_SENHA:
        log.warning("Admin inicial: ADMIN_INICIAL_EMAIL ou ADMIN_INICIAL_SENHA vazio; nenhuma conta criada.")
        return
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        log.error("Admin inicial: ADMIN_INICIAL_EMAIL não é um e-mail válido; nenhuma conta criada.")
        return
    from toqqi.core.auditoria import registrar
    from toqqi.core.permissoes import semear_padrao
    from toqqi.core.security import gerar_hash, mensagem_senha_fraca, problemas_senha
    from toqqi.modelos import Conta, Usuario
    from toqqi.modulos.formularios.semear import semear_conta

    with modo_sistema() as s:
        if s.scalar(select(Usuario.id).where(Usuario.email == email)):
            log.info("Admin inicial: %s já existe; nada a fazer.", _mascarar(email))
            return
        # Só com o banco vazio: trocar ADMIN_INICIAL_EMAIL depois não cria outra conta (as outras saem da Plataforma).
        if s.scalar(select(Conta.id).limit(1)) is not None:
            log.warning("Admin inicial: o banco já tem contas; %s não foi criado. A conta inicial só é criada com o "
                        "banco vazio; para outra conta, use a Plataforma.", _mascarar(email))
            return
        faltas = problemas_senha(cfg.ADMIN_INICIAL_SENHA)
        if faltas:
            log.error("ADMIN_INICIAL_SENHA fraca: %s Conta inicial NÃO criada.", mensagem_senha_fraca(faltas))
            return
        conta = Conta(nome=cfg.ADMIN_INICIAL_EMPRESA, situacao="cortesia")
        s.add(conta)
        s.flush()
        s.add(Usuario(conta_id=conta.id, nome=cfg.ADMIN_INICIAL_NOME, email=email,
                      senha_hash=gerar_hash(cfg.ADMIN_INICIAL_SENHA), perfil="admin", situacao="ativo",
                      email_confirmado=True))
        s.flush()
        semear_padrao(s, conta.id)
        semear_conta(s, conta.id)
        registrar(s, "conta_criada_plataforma", "info", {"por": "implantacao", "admin_email": email},
                  conta_id=conta.id)
    log.info("Conta inicial criada para %s.", _mascarar(email))
