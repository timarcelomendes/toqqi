"""Regras de acesso: cadastro, entrada, confirmação, senha, pedido de acesso, sessões.

Etapa 5g: a conta nova começa com `teste.dias` de teste no plano `teste.plano` (parâmetros da plataforma; padrões 14
dias e Profissional).
Entrar com o Google (08/10/2026, docs/api-login-google.md): `entrar_google` e `cadastrar_google`; a sessão sai de
`_abrir_sessao`, a mesma da entrada com senha."""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy import null as sql_null
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from toqqi.apresentacao import conta_json, usuario_json
from toqqi.core import acessos, parametros, planos, relogio
from toqqi.core.auditoria import registrar
from toqqi.core.avisos import avisar_admins
from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.permissoes import TODAS, ordenar, semear_padrao
from toqqi.core.security import (
    conferir_senha,
    criar_token_acesso,
    descrever_aparelho,
    gastar_tempo,
    gerar_hash,
    hash_token,
    novo_token_uso_unico,
    precisa_rehash,
)
from toqqi.core.validacao import DOMINIOS_GRATUITOS, dominio_do_email
from toqqi.modelos import Conta, DominioLiberado, PerfilPermissao, Sessao, TokenUsoUnico, Usuario
from toqqi.modulos.acesso import emails, google, termos
from toqqi.modulos.formularios.semear import semear_conta
from toqqi.modulos.imagens.servico import logo_da_conta

VALIDADE = {"confirmar_email": timedelta(hours=24), "redefinir_senha": timedelta(minutes=30)}
SESSAO_LEMBRAR = timedelta(days=30)

MSG_CADASTRO = (
    "Conta criada! Enviamos um e-mail para você confirmar o endereço. "
    "Abra o link da mensagem para liberar o acesso (confira também a caixa de spam)."
)
MSG_REENVIO = (
    "Se este e-mail estiver cadastrado e ainda não tiver sido confirmado, "
    "você vai receber um novo link em instantes."
)
MSG_ESQUECI = "Se este e-mail estiver cadastrado, você vai receber um link para criar uma nova senha em instantes."
MSG_PEDIDO = (
    "Pedido recebido. Se a sua empresa já usa o Toqqi e liberou o domínio do seu e-mail, "
    "você vai receber uma mensagem para confirmar o endereço. Depois, o administrador da conta aprova o seu acesso."
)
MSG_LINK_INVALIDO = "Este link não vale mais: ele expirou ou já foi usado. Peça um novo link."
MSG_OUTRA_CONTA_GOOGLE = ("Este e-mail já entra no Toqqi por outra conta do Google. Use aquela conta do Google ou entre "
                          "com e-mail e senha.")
MSG_JA_TEM_CONTA = "Este e-mail já tem conta no Toqqi: entre pelo botão do Google na tela de entrada."

def erro_credenciais() -> AppError:
    return AppError(401, "credenciais_invalidas", "E-mail ou senha incorretos.")


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def criar_token(s: Session, usuario_id: int, conta_id: int, finalidade: str) -> str:
    token, h = novo_token_uso_unico()
    s.add(TokenUsoUnico(
        conta_id=conta_id, usuario_id=usuario_id, finalidade=finalidade,
        token_hash=h, expira_em=_agora() + VALIDADE[finalidade],
    ))
    s.flush()
    return token


def permissoes_do_perfil(s: Session, perfil: str) -> list[str]:
    """Permissões efetivas de um perfil na conta da transação."""
    if perfil == "admin":
        return list(TODAS)
    perms = s.scalars(select(PerfilPermissao.permissao).where(PerfilPermissao.perfil == perfil)).all()
    return ordenar(perms)


# ---- cadastro ---------------------------------------------------------------

def _nova_conta(s: Session, empresa: str, origem, ip: str | None) -> Conta:
    """A conta de um cadastro (com senha ou pelo Google): teste de `teste.dias` no plano `teste.plano`."""
    conta = Conta(
        # o fim do teste segue o relógio das regras que o leem (assinatura.regras); tokens e sessões seguem no
        # relógio real
        nome=empresa,
        # sem origem: NULL de SQL (o JSONB gravaria 'null', que o CHECK da coluna recusa)
        origem=planos.limpar_origem(origem) or sql_null(),
        situacao="teste", teste_ate=relogio.agora() + timedelta(days=parametros.valor("teste.dias")),
        plano=parametros.valor("teste.plano"),
        termos_aceitos_em=_agora(), termos_ip=ip,
        # registro da versão aceita no cadastro da conta; a fonte da versão é termos.VERSAO_DOCUMENTOS e a prova de
        # cada pessoa fica em aceites_termos
        termos_versao=str(termos.VERSAO_DOCUMENTOS),
    )
    s.add(conta)
    s.flush()
    return conta


def cadastrar(dados, ip: str | None, agente: str | None = None) -> str:
    senha_hash = gerar_hash(dados.senha)  # antes de qualquer consulta: tempo igual nos dois caminhos
    aviso_existente: tuple[str, str, int] | None = None
    confirmacao: tuple[str, str, str, int] | None = None
    try:
        # Modo sistema: ainda não existe conta, e o e-mail é único entre todas as contas.
        with modo_sistema() as s:
            existente = s.scalar(select(Usuario).where(Usuario.email == dados.email))
            if existente is not None:
                aviso_existente = (existente.nome, existente.email, existente.conta_id)
            else:
                conta = _nova_conta(s, dados.empresa, dados.origem, ip)
                u = Usuario(
                    conta_id=conta.id, nome=dados.nome, email=dados.email, senha_hash=senha_hash,
                    telefone=dados.telefone, perfil="admin", situacao="ativo", email_confirmado=False,
                )
                s.add(u)
                s.flush()
                semear_padrao(s, conta.id)
                semear_conta(s, conta.id)
                token = criar_token(s, u.id, conta.id, "confirmar_email")
                registrar(s, "cadastro_conta", "sucesso", {"empresa": conta.nome, "email": u.email},
                          usuario_id=u.id, conta_id=conta.id)
                # "Li e aceito" do cadastro (aceite_termos: true, obrigatório): vale como aceite da versão atual
                termos.gravar(s, u, "cadastro", ip, agente, conta_id=conta.id)
                acessos.registrar(s, "cadastro", conta_id=conta.id, usuario_id=u.id)
                confirmacao = (u.nome, u.email, token, conta.id)
    except IntegrityError:
        # Corrida com outro cadastro do mesmo e-mail: resposta igual, nada criado.
        return MSG_CADASTRO
    if confirmacao:
        emails.confirmar_email(*confirmacao)
    elif aviso_existente:
        emails.ja_tem_conta(*aviso_existente)
    return MSG_CADASTRO


# ---- entrar -----------------------------------------------------------------

def entrar(dados, ip: str | None, agente: str | None) -> dict:
    # Modo sistema: o login só conhece o e-mail, não a conta.
    with modo_sistema() as s:
        u = s.scalar(select(Usuario).where(Usuario.email == dados.email))
    if u is None:
        gastar_tempo(dados.senha)  # mesmo custo de uma verificação real
        acessos.registrar_avulso("login_falhou")  # sem conta nem usuário (e nunca o e-mail digitado)
        raise erro_credenciais()
    if not conferir_senha(u.senha_hash, dados.senha):
        with em_conta(u.conta_id) as s:
            registrar(s, "login_falhou", "atencao", {"email": u.email})
            acessos.registrar(s, "login_falhou", conta_id=u.conta_id, usuario_id=u.id)
        raise erro_credenciais()

    recusa = None
    if not u.email_confirmado:
        recusa = AppError(403, "email_nao_confirmado",
                          "Confirme seu e-mail antes de entrar. Procure a mensagem que enviamos "
                          "(veja também o spam) ou peça um novo link.")
    else:
        recusa = _recusa_situacao(u)
    if recusa is not None:
        with em_conta(u.conta_id) as s:
            acessos.registrar(s, "login_falhou", conta_id=u.conta_id, usuario_id=u.id)
        raise recusa

    novo_hash = gerar_hash(dados.senha) if precisa_rehash(u.senha_hash) else None
    return _abrir_sessao(u, dados.lembrar, ip, agente, {"senha_hash": novo_hash} if novo_hash else {})


def _recusa_situacao(u: Usuario) -> AppError | None:
    if u.situacao == "pendente":
        return AppError(403, "acesso_pendente",
                        "Seu acesso ainda não foi aprovado. O administrador da conta precisa liberar sua entrada.")
    if u.situacao == "bloqueado":
        return AppError(403, "acesso_bloqueado", "Seu acesso está bloqueado. Fale com o administrador da sua conta.")
    return None


def _abrir_sessao(u: Usuario, lembrar: bool, ip: str | None, agente: str | None, valores: dict,
                  metodo: str | None = None, ligou_google: bool = False) -> dict:
    """A sessão de quem passou na entrada (senha ou Google): grava a sessão, o último acesso (e `valores` no usuário),
    a auditoria e o registro de acesso, e devolve o que o site guarda."""
    with em_conta(u.conta_id) as s:
        conta = s.get(Conta, u.conta_id)
        duracao = SESSAO_LEMBRAR if lembrar else timedelta(minutes=conta.sessao_minutos)
        sessao = Sessao(
            conta_id=u.conta_id, usuario_id=u.id, expira_em=_agora() + duracao,
            ip=ip, agente=(agente or "")[:500] or None,
        )
        s.add(sessao)
        s.execute(update(Usuario).where(Usuario.id == u.id).values(ultimo_acesso=func.now(), **valores))
        s.flush()
        if ligou_google:
            registrar(s, "login_google_ligado", "info", {"email": u.email}, usuario_id=u.id)
        registrar(s, "login_ok", "sucesso",
                  {"aparelho": descrever_aparelho(agente), **({"metodo": metodo} if metodo else {})}, usuario_id=u.id)
        acessos.registrar(s, "login", conta_id=u.conta_id, usuario_id=u.id)
        usuario = s.get(Usuario, u.id, populate_existing=True)
        permissoes = permissoes_do_perfil(s, usuario.perfil)
        return {
            "token": criar_token_acesso(u.id, u.conta_id, sessao.id, sessao.expira_em),
            "expira_em": sessao.expira_em,
            "usuario": {**usuario_json(usuario, preferencias=True), "aceite": termos.aceite_json(s, u.id)},
            "conta": {**conta_json(conta), "logo_url": logo_da_conta(s, u.conta_id)},
            "permissoes": permissoes,
        }


# ---- entrar com o Google ----------------------------------------------------

def entrar_google(dados, ip: str | None, agente: str | None) -> dict:
    """Com o token do Google: entra quem já tem usuário (pela conta do Google já ligada a ele ou, na primeira vez, pelo
    e-mail, que fica ligado); quem não tem recebe {novo, cadastro, email, nome} para terminar o cadastro."""
    g = google.verificar(dados.credencial)
    with modo_sistema() as s:  # como na entrada com senha: ainda não se sabe a conta
        u = s.scalar(select(Usuario).where(Usuario.google_sub == g["sub"]))
        if u is None:
            u = s.scalar(select(Usuario).where(Usuario.email == g["email"]))
    if u is None:
        return {"novo": True, "cadastro": google.token_cadastro(g), "email": g["email"], "nome": g["nome"]}
    if u.google_sub and u.google_sub != g["sub"]:
        with em_conta(u.conta_id) as s:
            registrar(s, "login_google_recusado", "atencao", {"email": u.email}, usuario_id=u.id)
            acessos.registrar(s, "login_falhou", conta_id=u.conta_id, usuario_id=u.id)
        raise AppError(409, "google_outra_conta", MSG_OUTRA_CONTA_GOOGLE)
    recusa = _recusa_situacao(u)
    if recusa is not None:
        with em_conta(u.conta_id) as s:
            if not u.email_confirmado:
                # o Google confirmou o e-mail: vale como a confirmação (e o pedido de acesso avisa os administradores)
                x = s.get(Usuario, u.id)
                x.email_confirmado = True
                if x.situacao == "pendente":
                    _avisar_pedido_de_acesso(s, x)
            acessos.registrar(s, "login_falhou", conta_id=u.conta_id, usuario_id=u.id)
        raise recusa
    valores: dict = {}
    if not u.email_confirmado:
        valores["email_confirmado"] = True
    if not u.google_sub:
        valores["google_sub"] = g["sub"]
    try:
        return _abrir_sessao(u, dados.lembrar, ip, agente, valores, "google", ligou_google=not u.google_sub)
    except IntegrityError:  # a mesma conta do Google ligada a outro usuário ao mesmo tempo
        raise AppError(409, "google_outra_conta", MSG_OUTRA_CONTA_GOOGLE)


def cadastrar_google(dados, ip: str | None, agente: str | None) -> dict:
    """Termina o cadastro de quem veio do Google (o token de `entrar_google`): conta nova em teste, o usuário
    administrador com o e-mail já confirmado e a conta do Google ligada, o aceite dos termos e a sessão aberta. Senha:
    uma aleatória que ninguém sabe (para usar senha, "Esqueci a senha")."""
    g = google.ler_cadastro(dados.cadastro)
    senha_hash = gerar_hash(secrets.token_urlsafe(32))
    try:
        with modo_sistema() as s:
            if s.scalar(select(Usuario.id).where(or_(Usuario.email == g["email"], Usuario.google_sub == g["sub"]))):
                raise AppError(409, "email_em_uso", MSG_JA_TEM_CONTA)
            conta = _nova_conta(s, dados.empresa, dados.origem, ip)
            u = Usuario(conta_id=conta.id, nome=dados.nome, email=g["email"], senha_hash=senha_hash,
                        telefone=dados.telefone, perfil="admin", situacao="ativo", email_confirmado=True,
                        google_sub=g["sub"])
            s.add(u)
            s.flush()
            semear_padrao(s, conta.id)
            semear_conta(s, conta.id)
            registrar(s, "cadastro_conta", "sucesso", {"empresa": conta.nome, "email": u.email, "metodo": "google"},
                      usuario_id=u.id, conta_id=conta.id)
            termos.gravar(s, u, "cadastro", ip, agente, conta_id=conta.id)
            acessos.registrar(s, "cadastro", conta_id=conta.id, usuario_id=u.id)
    except IntegrityError:  # corrida com outro cadastro do mesmo e-mail ou da mesma conta do Google
        raise AppError(409, "email_em_uso", MSG_JA_TEM_CONTA)
    return _abrir_sessao(u, False, ip, agente, {}, "google")


# ---- tokens de uso único ----------------------------------------------------

def _buscar_token(token: str, finalidade: str) -> TokenUsoUnico | None:
    """Localiza o token pelo hash. O consumo (uso único) é feito depois, com UPDATE condicional
    dentro da conta do token, de modo que só uma requisição consegue usá-lo."""
    with modo_sistema() as s:  # busca pelo hash: a conta ainda é desconhecida
        return s.scalar(select(TokenUsoUnico).where(
            TokenUsoUnico.token_hash == hash_token(token), TokenUsoUnico.finalidade == finalidade))


def confirmar_email(token: str) -> str:
    t = _buscar_token(token, "confirmar_email")
    if t is None:
        raise AppError(400, "link_invalido", MSG_LINK_INVALIDO)
    with em_conta(t.conta_id) as s:
        consumido = s.execute(
            update(TokenUsoUnico)
            .where(TokenUsoUnico.id == t.id, TokenUsoUnico.usado_em.is_(None), TokenUsoUnico.expira_em > func.now())
            .values(usado_em=func.now())
            .returning(TokenUsoUnico.id)
        ).scalar_one_or_none()
        u = s.get(Usuario, t.usuario_id)
        if consumido is None:
            if u is not None and u.email_confirmado and t.usado_em is not None:
                return "Seu e-mail já estava confirmado. É só entrar."
            raise AppError(400, "link_invalido", MSG_LINK_INVALIDO)
        ja_confirmado = u.email_confirmado
        u.email_confirmado = True  # nunca altera a situação do usuário
        if u.situacao == "pendente" and not ja_confirmado:
            _avisar_pedido_de_acesso(s, u)
    if u.situacao == "pendente":
        return "E-mail confirmado! Agora é só aguardar o administrador da conta aprovar o seu acesso."
    return "E-mail confirmado! Você já pode entrar."


def reenviar_confirmacao(email: str) -> str:
    with modo_sistema() as s:
        u = s.scalar(select(Usuario).where(Usuario.email == email))
    if u is not None and not u.email_confirmado:
        with em_conta(u.conta_id) as s:
            token = criar_token(s, u.id, u.conta_id, "confirmar_email")
        emails.confirmar_email(u.nome, u.email, token, u.conta_id)
    return MSG_REENVIO


def esqueci_senha(email: str) -> str:
    with modo_sistema() as s:
        u = s.scalar(select(Usuario).where(Usuario.email == email))
    if u is not None:
        with em_conta(u.conta_id) as s:
            token = criar_token(s, u.id, u.conta_id, "redefinir_senha")
        emails.redefinir_senha(u.nome, u.email, token, u.conta_id)
    return MSG_ESQUECI


def redefinir_senha(token: str, senha: str) -> str:
    t = _buscar_token(token, "redefinir_senha")
    if t is None:
        raise AppError(400, "link_invalido", MSG_LINK_INVALIDO)
    novo_hash = gerar_hash(senha)
    with em_conta(t.conta_id) as s:
        mais_novo = aliased(TokenUsoUnico)
        consumido = s.execute(
            update(TokenUsoUnico)
            .where(
                TokenUsoUnico.id == t.id,
                TokenUsoUnico.usado_em.is_(None),
                TokenUsoUnico.expira_em > func.now(),
                ~exists().where(and_(
                    mais_novo.usuario_id == t.usuario_id,
                    mais_novo.finalidade == "redefinir_senha",
                    mais_novo.id > t.id,
                )),
            )
            .values(usado_em=func.now())
            .returning(TokenUsoUnico.id)
        ).scalar_one_or_none()
        if consumido is None:
            raise AppError(400, "link_invalido", MSG_LINK_INVALIDO)
        # Quem abriu o link provou ser dono do e-mail.
        s.execute(update(Usuario).where(Usuario.id == t.usuario_id)
                  .values(senha_hash=novo_hash, email_confirmado=True))
        revogadas = revogar_sessoes(s, t.usuario_id)
        registrar(s, "senha_redefinida", "atencao", {"sessoes_encerradas": revogadas}, usuario_id=t.usuario_id)
        acessos.registrar(s, "senha_redefinida", conta_id=t.conta_id, usuario_id=t.usuario_id)
    return "Senha alterada! Entre com a nova senha."


# ---- pedido de acesso -------------------------------------------------------

def _avisar_pedido_de_acesso(s: Session, u: Usuario) -> None:
    """Pedido de acesso com o e-mail confirmado (a pessoa provou ser dona do endereço): e-mail aos administradores
    ativos da conta, depois do commit, com o atalho para os pedidos em Equipe. Uma vez por pedido (na primeira
    confirmação); entra no registro de e-mails enviados como `aviso`."""
    nome = " ".join((u.nome or "").split())[:80] or u.email
    empresa = " ".join((s.get(Conta, u.conta_id).nome or "").split())
    conta = f"à conta {empresa} no Toqqi" if empresa else "à sua conta no Toqqi"
    avisar_admins(s, u.conta_id, f"{nome} pediu acesso ao Toqqi", [
        f"{nome} ({u.email}) pediu acesso {conta} e já confirmou o e-mail.",
        "Confira quem é e aprove ou bloqueie o pedido em Equipe. Quem é aprovado entra com o perfil Consulta, que você "
        "pode trocar depois.",
    ], ("Ver pedidos", f"{config().FRONTEND_URL.rstrip('/')}/equipe?pedidos=1"))


def pedir_acesso(dados) -> str:
    senha_hash = gerar_hash(dados.senha)
    dominio = dominio_do_email(dados.email)
    if dominio in DOMINIOS_GRATUITOS:
        return MSG_PEDIDO
    # Modo sistema: descobrir qual conta liberou o domínio (e se o e-mail já existe em alguma).
    with modo_sistema() as s:
        conta_id = s.scalar(select(DominioLiberado.conta_id).where(DominioLiberado.dominio == dominio))
        ja_existe = s.scalar(select(exists().where(Usuario.email == dados.email)))
    if conta_id is None or ja_existe:
        return MSG_PEDIDO
    try:
        with em_conta(conta_id) as s:
            u = Usuario(nome=dados.nome, email=dados.email, senha_hash=senha_hash,
                        perfil="consulta", situacao="pendente", email_confirmado=False)
            s.add(u)
            s.flush()
            token = criar_token(s, u.id, conta_id, "confirmar_email")
            registrar(s, "usuario_criado", "info",
                      {"origem": "pedido_de_acesso", "nome": u.nome, "email": u.email, "perfil": "consulta"})
            acessos.registrar(s, "pedido_acesso", conta_id=conta_id, usuario_id=u.id)
    except IntegrityError:
        return MSG_PEDIDO
    emails.confirmar_email(dados.nome, dados.email, token, conta_id)
    return MSG_PEDIDO


# ---- usuário logado ---------------------------------------------------------

def revogar_sessoes(s: Session, usuario_id: int, exceto: uuid.UUID | None = None) -> int:
    q = update(Sessao).where(Sessao.usuario_id == usuario_id, Sessao.revogada_em.is_(None))
    if exceto is not None:
        q = q.where(Sessao.id != exceto)
    return s.execute(q.values(revogada_em=func.now())).rowcount



def sair(ctx: Contexto) -> None:
    with em_conta(ctx.conta_id) as s:
        s.execute(update(Sessao).where(Sessao.id == ctx.sessao_id).values(revogada_em=func.now()))
        registrar(s, "sessao_encerrada", "info", {"motivo": "saiu"}, usuario_id=ctx.usuario_id)


def eu(ctx: Contexto) -> dict:
    # o logo (em `imagens`) e o aceite dos termos não vêm na leitura do contexto feita a cada requisição
    with em_conta(ctx.conta_id) as s:
        logo = logo_da_conta(s, ctx.conta_id)
        aceite = termos.aceite_json(s, ctx.usuario_id)
    return {"usuario": {**ctx.usuario, "aceite": aceite}, "conta": {**ctx.conta, "logo_url": logo},
            "permissoes": ctx.permissoes}


def alterar_eu(ctx: Contexto, dados) -> dict:
    with em_conta(ctx.conta_id) as s:
        u = s.get(Usuario, ctx.usuario_id)
        if "nome" in dados.model_fields_set and dados.nome is not None:
            u.nome = dados.nome
        if "cargo" in dados.model_fields_set:
            u.cargo = dados.cargo or None
        for campo in ("recebe_resumo_semanal", "recebe_alertas"):  # e-mails do Toqqi (Minha conta)
            if campo in dados.model_fields_set and getattr(dados, campo) is not None:
                setattr(u, campo, getattr(dados, campo))
        s.flush()
        # o aceite também vem aqui: o site troca o usuário da sessão pela resposta
        return {**usuario_json(u, preferencias=True), "aceite": termos.aceite_json(s, u.id)}


def trocar_senha(ctx: Contexto, dados) -> str:
    with em_conta(ctx.conta_id) as s:
        atual = s.scalar(select(Usuario.senha_hash).where(Usuario.id == ctx.usuario_id))
    if not conferir_senha(atual, dados.senha_atual):
        raise AppError(422, "senha_atual_incorreta", "A senha atual não confere.",
                       {"senha_atual": "A senha atual não confere."})
    novo_hash = gerar_hash(dados.senha_nova)
    with em_conta(ctx.conta_id) as s:
        s.execute(update(Usuario).where(Usuario.id == ctx.usuario_id).values(senha_hash=novo_hash))
        revogadas = revogar_sessoes(s, ctx.usuario_id, exceto=ctx.sessao_id)
        registrar(s, "senha_alterada", "sucesso", {"outras_sessoes_encerradas": revogadas}, usuario_id=ctx.usuario_id)
    return "Senha alterada. As outras sessões abertas foram encerradas."


def listar_sessoes(ctx: Contexto) -> list[dict]:
    with em_conta(ctx.conta_id) as s:
        sessoes = s.scalars(
            select(Sessao)
            .where(Sessao.usuario_id == ctx.usuario_id, Sessao.revogada_em.is_(None), Sessao.expira_em > func.now())
            .order_by(Sessao.ultimo_uso.desc())
        ).all()
    return [
        {
            "id": str(x.id),
            "aparelho": descrever_aparelho(x.agente),
            "ip": x.ip,
            "criada_em": x.criada_em,
            "ultimo_uso": x.ultimo_uso,
            "atual": x.id == ctx.sessao_id,
        }
        for x in sessoes
    ]


def encerrar_sessao(ctx: Contexto, sessao_id: uuid.UUID) -> None:
    with em_conta(ctx.conta_id) as s:
        agente = s.execute(
            update(Sessao)
            .where(Sessao.id == sessao_id, Sessao.usuario_id == ctx.usuario_id, Sessao.revogada_em.is_(None))
            .values(revogada_em=func.now())
            .returning(Sessao.agente)
        ).one_or_none()
        if agente is None:
            raise nao_encontrado("Sessão não encontrada ou já encerrada.")
        registrar(s, "sessao_encerrada", "info",
                  {"motivo": "encerrada_pelo_usuario", "aparelho": descrever_aparelho(agente[0])},
                  usuario_id=ctx.usuario_id)


def encerrar_outras(ctx: Contexto) -> None:
    with em_conta(ctx.conta_id) as s:
        n = revogar_sessoes(s, ctx.usuario_id, exceto=ctx.sessao_id)
        if n:
            registrar(s, "sessao_encerrada", "info", {"motivo": "outras_sessoes", "quantidade": n},
                      usuario_id=ctx.usuario_id)
