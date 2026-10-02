"""Aceite dos Termos de uso e da Política de privacidade (LGPD).

O bloqueio de quem não aceitou é feito no site; a API registra o aceite (quem, quando, versão, IP, navegador, origem)
e informa a situação em `GET /eu` e na resposta de `POST /auth/entrar`. Nunca na leitura do contexto feita a cada
requisição.
"""
from sqlalchemy import select
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
VERSAO_DOCUMENTOS = 1

AGENTE_MAX = 400
ORIGENS = ("cadastro", "tela")


def aceite_json(s: Session, usuario_id: int) -> dict:
    """`{versao_atual, versao_aceita, aceito_em, pendente}`: `versao_aceita` é a maior versão aceita."""
    ultimo = s.execute(
        select(AceiteTermos.versao, AceiteTermos.aceito_em)
        .where(AceiteTermos.usuario_id == usuario_id)
        .order_by(AceiteTermos.versao.desc())
        .limit(1)
    ).one_or_none()
    versao, quando = ultimo if ultimo else (None, None)
    return {
        "versao_atual": VERSAO_DOCUMENTOS,
        "versao_aceita": versao,
        "aceito_em": quando,
        "pendente": versao is None or versao < VERSAO_DOCUMENTOS,
    }


def gravar(s: Session, usuario: Usuario, origem: str, ip: str | None, agente: str | None,
           conta_id: int | None = None) -> bool:
    """Grava o aceite da versão atual. Idempotente: se o usuário já aceitou esta versão, não cria linha nem auditoria.
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
        .on_conflict_do_nothing(index_elements=["usuario_id", "versao"])
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
