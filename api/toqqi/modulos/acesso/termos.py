"""Aceite dos Termos de uso e da Política de privacidade (LGPD).

O bloqueio de quem não aceitou é feito no site; a API registra o aceite (quem, quando, versão, IP, navegador, origem)
e informa a situação em `GET /eu` e na resposta de `POST /auth/entrar`. Nunca na leitura do contexto feita a cada
requisição.
"""
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.modelos import AceiteTermos, Usuario

# Versão dos dois documentos (Termos de uso e Política de privacidade). Precisa ser IGUAL ao número em
# web/src/modulos/geral/legal/versao.ts: mudou o texto de forma relevante, sobe os dois juntos no mesmo commit
# (todo mundo vê a tela de aceite de novo).
VERSAO_DOCUMENTOS = 3  # 2 (etapa 5d): os cinco recursos de IA; 3 (etapa 5e): o registro de e-mails enviados (90 dias)

AGENTE_MAX = 400
ORIGENS = ("cadastro", "tela")


def aceite_json(s: Session, usuario_id: int) -> dict:
    """`{versao_atual, versao_aceita, aceito_em, pendente, revogado_em}`.

    `versao_aceita`/`aceito_em`: a maior versão aceita entre as linhas em vigor (sem `revogado_em`).
    `revogado_em`: a retirada mais recente, quando ela é posterior ao último aceite em vigor (senão null)."""
    em_vigor = AceiteTermos.revogado_em.is_(None)
    ultimo = s.execute(
        select(AceiteTermos.versao, AceiteTermos.aceito_em)
        .where(AceiteTermos.usuario_id == usuario_id, em_vigor)
        .order_by(AceiteTermos.versao.desc())
        .limit(1)
    ).one_or_none()
    versao, quando = ultimo if ultimo else (None, None)
    revogado, aceito_mais_recente = s.execute(
        select(func.max(AceiteTermos.revogado_em),
               func.max(AceiteTermos.aceito_em).filter(em_vigor))
        .where(AceiteTermos.usuario_id == usuario_id)
    ).one()
    if revogado is not None and aceito_mais_recente is not None and revogado <= aceito_mais_recente:
        revogado = None
    return {
        "versao_atual": VERSAO_DOCUMENTOS,
        "versao_aceita": versao,
        "aceito_em": quando,
        "pendente": versao is None or versao < VERSAO_DOCUMENTOS,
        "revogado_em": revogado,
    }


def gravar(s: Session, usuario: Usuario, origem: str, ip: str | None, agente: str | None,
           conta_id: int | None = None) -> bool:
    """Grava o aceite da versão atual. Idempotente: se o usuário já tem esta versão aceita e em vigor, não cria linha
    nem auditoria; depois de retirar o aceite, cria uma linha nova (o índice único é parcial: só as linhas em vigor).
    Devolve True quando gravou agora. Sem `conta_id`, usa a conta da transação (app_conta()).
    Guarda uma cópia do e-mail e do nome: se o membro for removido em Equipe, `usuario_id` vira nulo e a prova fica."""
    assert origem in ORIGENS
    usuario_id = usuario.id
    valores = {
        "usuario_id": usuario_id,
        "usuario_email": usuario.email,
        "usuario_nome": usuario.nome,
        "versao": VERSAO_DOCUMENTOS,
        "ip": ip,
        "agente": (agente or "")[:AGENTE_MAX] or None,
        "origem": origem,
    }
    if conta_id is not None:
        valores["conta_id"] = conta_id
    novo = s.execute(
        insert(AceiteTermos).values(**valores)
        # o alvo do conflito precisa repetir o WHERE do índice único parcial (aceites_termos_vigente_uq)
        .on_conflict_do_nothing(index_elements=["usuario_id", "versao"],
                                index_where=AceiteTermos.revogado_em.is_(None))
        .returning(AceiteTermos.id)
    ).scalar_one_or_none()
    if novo is None:
        return False
    detalhe = {"versao": VERSAO_DOCUMENTOS}
    if origem == "cadastro":
        detalhe["origem"] = "cadastro"
    registrar(s, "termos_aceitos", "info", detalhe, usuario_id=usuario_id, conta_id=conta_id)
    return True


def aceitar(ctx: Contexto, versao: int, ip: str | None, agente: str | None) -> dict:
    """`POST /eu/aceite`: aceite pela tela "Antes de continuar"."""
    if versao != VERSAO_DOCUMENTOS:
        raise AppError(409, "versao_desatualizada",
                       "Os termos foram atualizados. Recarregue a página para ver a versão nova.")
    with em_conta(ctx.conta_id) as s:
        gravar(s, s.get(Usuario, ctx.usuario_id), "tela", ip, agente)
        return aceite_json(s, ctx.usuario_id)


MSG_REVOGADO = "Aceite retirado. Para voltar a usar o Toqqi, entre de novo e aceite os termos."


def revogar(ctx: Contexto, ip: str | None, agente: str | None) -> str:
    """`POST /eu/aceite/revogar`: marca a retirada em todas as linhas em vigor do usuário (a prova fica) e encerra
    todas as sessões dele, inclusive a atual. Sem aceite em vigor: 409 `sem_aceite`."""
    # import aqui: servico importa este módulo
    from toqqi.modulos.acesso.servico import revogar_sessoes

    with em_conta(ctx.conta_id) as s:
        versoes = s.scalars(
            update(AceiteTermos)
            .where(AceiteTermos.usuario_id == ctx.usuario_id, AceiteTermos.revogado_em.is_(None))
            .values(revogado_em=func.now(), revogado_ip=ip, revogado_agente=(agente or "")[:AGENTE_MAX] or None)
            .returning(AceiteTermos.versao)
        ).all()
        if not versoes:
            raise AppError(409, "sem_aceite", "Você não tem um aceite em vigor para retirar.")
        revogar_sessoes(s, ctx.usuario_id)
        registrar(s, "termos_revogados", "atencao", {"versao": max(versoes)}, usuario_id=ctx.usuario_id)
    return MSG_REVOGADO
