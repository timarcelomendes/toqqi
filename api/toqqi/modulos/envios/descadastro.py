"""Descadastro (conta + e-mail ou telefone): token assinado, página pública e tela interna.

O token leva conta_id e e-mail, assinados com HMAC(JWT_SECRET); não expira. A página pública só confia
na conta que vem de um token com assinatura válida e trabalha dentro de em_conta(conta).
O descadastro por telefone vem do WhatsApp ("SAIR"). Um contato com o e-mail ou o telefone descadastrado
sai da lista: não recebe nada da conta, em nenhum canal. Voltar (o botão da página /sair/{token} ou VOLTAR no
WhatsApp) também vale em todos: tira o e-mail ou o telefone e os dos contatos com ele (`desfazer`).

Página /sair sem token (pedido do Marcelo, 07/10/2026; docs/api-voltar-a-receber.md): a pessoa digita o e-mail e a
Toqqi manda a ele um link por empresa que já lhe mandou pesquisas (ou de cuja lista ela saiu), para sair ou voltar
a receber. A resposta é sempre a mesma (não revela de quem a pessoa é cliente); limite por IP na rota e por e-mail
aqui.
"""
import base64
import binascii
import hashlib
import hmac
from urllib.parse import urlparse

from limits import parse_many
from sqlalchemy import String, and_, cast, delete, exists, false, func, or_, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from toqqi.core import email as emails
from toqqi.core.auditoria import registrar
from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.email import Link
from toqqi.core.errors import AppError
from toqqi.core.paginacao import Pagina
from toqqi.core.rate_limit import limiter
from toqqi.core.texto import RE_CELULAR_SEM_NOVE, telefone_canonico
from toqqi.modelos import Conta, Contato, Descadastro
from toqqi.modulos.integracoes.webhooks import enfileirar

_MAX_TOKEN = 600
MSG_LINK = ("Se este e-mail já recebeu pesquisas pelo Toqqi, o link chega em alguns minutos. Não achou? Olhe também "
            "no spam.")
LIMITE_LINK_POR_EMAIL = "3/hour;6/day"  # e-mails com o link para o mesmo endereço (o pedido sempre responde igual)
MAX_EMPRESAS_LINK = 20


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _assinatura(dados: str) -> str:
    mac = hmac.new(config().JWT_SECRET.encode(), f"descadastro|{dados}".encode(), hashlib.sha256).digest()
    return _b64(mac[:18])


def token_descadastro(conta_id: int, email: str) -> str:
    dados = _b64(f"{int(conta_id)}:{email.strip().lower()}".encode())
    return f"{dados}.{_assinatura(dados)}"


def ler_token(token: str) -> tuple[int, str] | None:
    if not token or len(token) > _MAX_TOKEN or token.count(".") != 1:
        return None
    dados, assinatura = token.split(".")
    if not hmac.compare_digest(assinatura.encode(), _assinatura(dados).encode()):
        return None
    try:
        conta, _, email = base64.urlsafe_b64decode(dados + "=" * (-len(dados) % 4)).decode().partition(":")
        return int(conta), email
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def link_descadastro(conta_id: int, email: str) -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}/sair/{token_descadastro(conta_id, email)}"


def link_um_clique(conta_id: int, email: str) -> str:
    return f"{config().API_PUBLIC_URL.rstrip('/')}/api/v1/publico/descadastro/{token_descadastro(conta_id, email)}"


def mascarar(email: str) -> str:
    """ "maria@empresa.com.br" → "ma***@empresa.com.br"."""
    nome, _, dominio = email.partition("@")
    return f"{nome[:2]}***@{dominio}"


def mascarar_telefone(telefone: str) -> str:
    """ "5511987654321" → "***4321"."""
    return f"***{telefone[-4:]}"


def telefone_sql(coluna):
    """Telefone canônico (ver core.texto.telefone_canonico) de uma coluna."""
    return func.regexp_replace(coluna, RE_CELULAR_SEM_NOVE, "\\19\\2")


def descadastrado(email_coluna, telefone_coluna):
    """Expressão: o e-mail ou o telefone (colunas) está descadastrado."""
    return exists().where(or_(Descadastro.email == email_coluna,
                              Descadastro.telefone == telefone_sql(telefone_coluna)))


def esta_descadastrado(s: Session, email: str | None, telefone: str | None = None) -> bool:
    conds = []
    if email:
        conds.append(Descadastro.email == email)
    if telefone:
        conds.append(Descadastro.telefone == telefone_canonico(telefone))
    return bool(conds) and bool(s.scalar(select(exists().where(or_(*conds)))))


def _do_mesmo_contato(s: Session, email: str | None, telefone: str | None) -> tuple[set[str], set[str]]:
    """O e-mail (ou o telefone canônico) e os e-mails e telefones dos contatos com ele."""
    emails_ = {email.lower()} if email else set()
    telefones = {telefone} if telefone else set()
    cond = Contato.email == email if email else telefone_sql(Contato.telefone) == telefone
    for e, t in s.execute(select(Contato.email, telefone_sql(Contato.telefone)).where(cond)):
        if e:
            emails_.add(e.lower())
        if t:
            telefones.add(t)
    return emails_, telefones


def _fora(emails_: set[str], telefones: set[str]):
    conds = []
    if emails_:
        conds.append(Descadastro.email.in_(sorted(emails_)))
    if telefones:
        conds.append(Descadastro.telefone.in_(sorted(telefones)))
    return or_(*conds) if conds else false()


def fora_da_lista(s: Session, email: str | None = None, telefone: str | None = None) -> bool:
    """A pessoa não recebe nada da conta: o e-mail (ou o telefone) dela, ou um dos contatos com ele, saiu da lista."""
    return bool(s.scalar(select(exists().where(_fora(*_do_mesmo_contato(s, email, telefone))))))


def desfazer(s: Session, origem: str, email: str | None = None, telefone: str | None = None) -> bool:
    """Volta a receber: tira da lista o e-mail (ou o telefone canônico) e os dos contatos com ele (quem sai por um
    canal sai de todos; quem volta por um, volta em todos). Audita sem o dado completo; False se não estava fora."""
    apagados = s.execute(delete(Descadastro).where(_fora(*_do_mesmo_contato(s, email, telefone)))).rowcount
    if apagados:
        dado = {"email": mascarar(email)} if email else {"telefone": mascarar_telefone(telefone or "")}
        registrar(s, "descadastro_desfeito", "info", {**dado, "origem": origem})
    return bool(apagados)


def _contato_de(s: Session, email: str | None, telefone: str | None) -> Contato | None:
    cond = Contato.email == email if email else telefone_sql(Contato.telefone) == telefone
    return s.scalar(select(Contato).where(cond).order_by(Contato.ativo.desc(), Contato.id).limit(1))


def gravar(s: Session, email: str | None, origem: str, motivo: str | None, usuario_id: int | None = None,
           telefone: str | None = None) -> None:
    """Registra (ou mantém) o descadastro por e-mail ou por telefone, audita sem o dado completo e avisa os
    webhooks (`contato.descadastrado`)."""
    telefone = telefone_canonico(telefone) if telefone and not email else None
    alvo = ({"index_elements": ["conta_id", "email"]} if email else
            {"index_elements": ["conta_id", "telefone"], "index_where": Descadastro.telefone.is_not(None)})
    novo = s.scalar(insert(Descadastro).values(email=email, telefone=telefone, origem=origem, motivo=motivo,
                                               usuario_id=usuario_id)
                    .on_conflict_do_nothing(**alvo).returning(Descadastro.id))
    dado = {"email": mascarar(email)} if email else {"telefone": mascarar_telefone(telefone)}
    registrar(s, "descadastro", "atencao", {**dado, "origem": origem, "motivo": motivo}, usuario_id=usuario_id)
    if novo is not None:
        contato = _contato_de(s, email, telefone)
        email_contato = email or (contato.email if contato else None)
        enfileirar(s, "contato.descadastrado", {
            "email_mascarado": mascarar(email_contato) if email_contato else None,
            "contato_id": contato.id if contato else None, "origem": origem})


# ---- página pública ---------------------------------------------------------

def link_invalido() -> AppError:
    return AppError(404, "link_invalido", "Este link não é válido ou não está mais disponível.")


def _abrir_token(token: str) -> tuple[int, str]:
    lido = ler_token(token)
    if lido is None:
        raise link_invalido()
    return lido


def _nome_conta(s: Session) -> str:
    nome = s.scalar(select(Conta.nome))
    if nome is None:  # conta excluída
        raise link_invalido()
    return nome


def abrir(token: str) -> dict:
    """`descadastrado`: a pessoa não recebe nada da conta (o e-mail saiu da lista, ou o telefone de um contato com
    ele saiu pelo WhatsApp)."""
    conta_id, email = _abrir_token(token)
    with em_conta(conta_id) as s:
        return {"email_mascarado": mascarar(email), "empresa": _nome_conta(s),
                "descadastrado": fora_da_lista(s, email)}


def descadastrar(token: str, motivo: str | None, origem: str) -> dict:
    conta_id, email = _abrir_token(token)
    with em_conta(conta_id) as s:
        _nome_conta(s)
        if not esta_descadastrado(s, email):
            gravar(s, email, origem, motivo)
    return {"descadastrado": True}


def voltar(token: str) -> dict:
    conta_id, email = _abrir_token(token)
    with em_conta(conta_id) as s:
        _nome_conta(s)
        desfazer(s, "link", email=email)
    return {"descadastrado": False}


# ---- pedir o link (página /sair, sem token) ---------------------------------

def _chave_email(email: str) -> str:
    return hashlib.sha256(f"link-sair|{email}".encode()).hexdigest()[:32]


def contar_pedido(email: str) -> bool:
    """Conta o pedido no limite por e-mail (`LIMITE_LINK_POR_EMAIL`, por processo, como os da rota); False se passou
    (o pedido responde igual, sem mandar nada). Desligado com os limites (RATE_LIMIT_ENABLED=0)."""
    if not limiter.enabled:
        return True
    return all(limiter.limiter.hit(item, "link-sair", _chave_email(email)) for item in parse_many(LIMITE_LINK_POR_EMAIL))


def empresas_do_email(email: str) -> list[tuple[int, str, bool]]:
    """(conta_id, nome, fora da lista) das contas que já mandaram pesquisa a um contato com este e-mail, ou de cuja
    lista ele saiu (pelo e-mail, ou um contato com ele pelo WhatsApp), em ordem de nome (até `MAX_EMPRESAS_LINK`).
    Modo sistema: o e-mail pode estar em várias contas."""
    tel = aliased(Contato)
    fora = or_(
        exists().where(Descadastro.conta_id == Conta.id, Descadastro.email == email),
        exists().where(Descadastro.conta_id == Conta.id, tel.conta_id == Conta.id, tel.email == email,
                       Descadastro.telefone == telefone_sql(tel.telefone)),
    )
    recebeu = exists().where(Contato.conta_id == Conta.id, Contato.email == email, Contato.ultimo_envio.is_not(None))
    with modo_sistema() as s:
        linhas = s.execute(select(Conta.id, Conta.nome, fora).where(or_(recebeu, fora))
                           .order_by(Conta.nome, Conta.id).limit(MAX_EMPRESAS_LINK)).all()
    return [(conta_id, " ".join((nome or "").split()) or "Empresa", bool(f)) for conta_id, nome, f in linhas]


def enviar_link(email: str) -> None:
    """E-mail da Toqqi com a página /sair/{token} de cada empresa (`empresas_do_email`); nenhuma: não manda nada."""
    empresas = empresas_do_email(email)
    if not empresas:
        return
    pagina = f"{urlparse(config().FRONTEND_URL).netloc or 'toqqi.com'}/sair"
    paragrafos: list[emails.Paragrafo] = [f"Você pediu, em {pagina}, para escolher as pesquisas que recebe."]
    botao = None
    if len(empresas) == 1:
        conta_id, nome, fora = empresas[0]
        if fora:
            paragrafos.append(f"Você saiu da lista de pesquisas de {nome}. Se quiser voltar a receber, é só abrir o "
                              "link abaixo.")
            botao = ("Voltar a receber as pesquisas", link_descadastro(conta_id, email))
        else:
            paragrafos.append(f"{nome} manda pesquisas de satisfação para este e-mail pelo Toqqi. Se não quiser "
                              "mais receber, é só abrir o link abaixo.")
            botao = ("Não quero mais receber", link_descadastro(conta_id, email))
    else:
        paragrafos.append("Estas empresas mandam pesquisas de satisfação para este e-mail pelo Toqqi. Abra o link de "
                          "cada uma para sair da lista ou voltar a receber:")
        paragrafos += [Link(f"{nome} (você saiu da lista)" if fora else nome, link_descadastro(conta_id, email))
                       for conta_id, nome, fora in empresas]
    paragrafos.append("Não foi você que pediu? É só ignorar este e-mail: nada muda.")
    emails.enviar(email, "Escolha as pesquisas que você recebe", paragrafos, botao,
                  assunto_no_log="Link para escolher as pesquisas (página /sair)")


# ---- tela interna -----------------------------------------------------------

def _json(d: Descadastro, contato_id: int | None, contato_nome: str | None) -> dict:
    return {"email": d.email, "telefone": d.telefone,
            "contato": {"id": contato_id, "nome": contato_nome} if contato_id else None,
            "motivo": d.motivo, "origem": d.origem, "criado_em": d.criado_em}


# contato do descadastro: pelo e-mail ou, no descadastro por telefone, pelo telefone
_CONTATO = (select(Contato.id, Contato.nome)
            .where(or_(Contato.email == Descadastro.email,
                       and_(Descadastro.email.is_(None), telefone_sql(Contato.telefone) == Descadastro.telefone)))
            .order_by(Contato.ativo.desc(), Contato.id).limit(1).correlate(Descadastro).lateral("contato"))


def _consulta():
    return select(Descadastro, _CONTATO.c.id, _CONTATO.c.nome).outerjoin(_CONTATO, true())


def listar(ctx: Contexto, pg: Pagina, busca: str | None) -> dict:
    filtros = []
    if busca:
        termo = f"%{busca}%"
        filtros.append(or_(cast(Descadastro.email, String).ilike(termo), Descadastro.telefone.contains(busca),
                           _CONTATO.c.nome.ilike(termo)))
    with em_conta(ctx.conta_id) as s:
        total = s.scalar(select(func.count()).select_from(_consulta().where(*filtros).subquery()))
        linhas = s.execute(_consulta().where(*filtros).order_by(Descadastro.criado_em.desc(), Descadastro.id.desc())
                           .limit(pg.por_pagina).offset(pg.offset)).all()
    return pg.resultado([_json(*x) for x in linhas], total)


def adicionar(ctx: Contexto, dados) -> dict:
    with em_conta(ctx.conta_id) as s:
        if not esta_descadastrado(s, dados.email):
            gravar(s, dados.email, "manual", dados.motivo, usuario_id=ctx.usuario_id)
        return _json(*s.execute(_consulta().where(Descadastro.email == dados.email)).one())
