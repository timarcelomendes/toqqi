"""Melhoria 5, prova social.

- Tela final da pesquisa (convite individual): o promotor (NPS 9–10 ou CSAT 5) que deixou comentário vê "Podemos
  publicar seu comentário como depoimento?" quando os depoimentos estão ligados; e, com o link de avaliação
  configurado, "Avaliar a {empresa}" (Google, Reclame Aqui...). Só na conta liberada, como a indicação.
- `POST /publico/convites/{token}/depoimento`: o cliente autoriza (uma vez; repetir responde igual). O depoimento entra
  `pendente`; a equipe aprova (pode publicar) ou oculta em Crescimento › Depoimentos.
- A assinatura do depoimento é o primeiro nome do contato e o nome da empresa dele ("Ana, Mercado Azul").
- O cliente mudou a resposta (docs/api-editar-resposta.md) e o comentário ou a categoria mudou: o depoimento autorizado
  volta a `pendente` (a equipe confere o texto novo antes de publicar).
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.paginacao import Pagina
from toqqi.modelos import Contato, Conta, Empresa, Resposta
from toqqi.modulos.assinatura.regras import liberada
from toqqi.modulos.crescimento.configuracao import obter
from toqqi.modulos.crescimento.indicacoes import da_direito
from toqqi.modulos.respostas.eventos import GANCHOS_EDICAO

SITUACOES = ("pendente", "aprovado", "oculto")
MSG_OBRIGADO = "Obrigado! Seu comentário pode ajudar outras empresas a nos conhecer."


def _primeiro_nome(nome: str | None) -> str:
    return (nome or "").strip().split(" ")[0] if nome and nome.strip() else ""


def assinatura(contato: str | None, empresa: str | None) -> str:
    """"Ana, Mercado Azul" (ou só um dos dois; vazio vira "Cliente")."""
    return ", ".join(p for p in (_primeiro_nome(contato), (empresa or "").strip()) if p) or "Cliente"


def _pode_pedir(r: Resposta, cfg) -> bool:
    return bool(cfg.depoimentos_ativos and (r.comentario_cliente or "").strip() and r.depoimento_em is None)


def tela_final(s: Session, r: Resposta | None, empresa: str) -> dict | None:
    """{pedir, avaliar_url, avaliar_rotulo} para a tela final, ou None (nota sem direito, nada ligado, conta parada)."""
    if r is None or r.arquivada or not da_direito(r):
        return None
    cfg = obter(s, criar=False)
    pedir = _pode_pedir(r, cfg)
    if not (pedir or cfg.link_avaliacao):
        return None
    conta = s.scalar(select(Conta))
    if conta is None or not liberada(conta):
        return None
    return {"pedir": pedir, "avaliar_url": cfg.link_avaliacao,
            "avaliar_rotulo": f"Avaliar a {empresa}" if empresa else "Deixar uma avaliação"}


def autorizar(s: Session, r: Resposta | None) -> dict:
    """O cliente autorizou (na transação da conta). Sem direito ou desligado: 409 `depoimento_indisponivel`."""
    if r is not None and r.depoimento_em is not None:
        return {"mensagem": MSG_OBRIGADO}  # repetido: responde igual
    if r is None or r.arquivada or not da_direito(r) or not _pode_pedir(r, obter(s, criar=False)):
        raise AppError(409, "depoimento_indisponivel", "Não é possível registrar este depoimento.")
    conta = s.scalar(select(Conta))
    if conta is None or not liberada(conta):
        raise AppError(409, "depoimento_indisponivel", "Não é possível registrar este depoimento.")
    r.depoimento_em, r.depoimento_situacao = relogio.agora(), "pendente"
    return {"mensagem": MSG_OBRIGADO}


def _json(r: Resposta, contato: str | None, empresa_id: int | None, empresa: str | None) -> dict:
    return {"resposta_id": r.id, "nota": r.nota, "tipo_nota": r.tipo_nota, "comentario": r.comentario_cliente,
            "autorizado_em": r.depoimento_em, "situacao": r.depoimento_situacao, "data_resposta": r.data_resposta,
            "contato": {"id": r.contato_id, "nome": contato} if r.contato_id else None,
            "empresa": {"id": empresa_id, "nome": empresa} if empresa_id else None,
            "assinatura": assinatura(contato, empresa)}


def _consulta():
    return (select(Resposta, Contato.nome, Empresa.id, Empresa.nome)
            .outerjoin(Contato, Contato.id == Resposta.contato_id)
            .outerjoin(Empresa, Empresa.id == Resposta.empresa_id)
            .where(Resposta.depoimento_em.is_not(None)))


def listar(ctx: Contexto, situacao: str | None, pg: Pagina) -> dict:
    """Os depoimentos autorizados, dos mais novos aos mais antigos, com `resumo` por situação."""
    with em_conta(ctx.conta_id) as s:
        resumo = dict.fromkeys(SITUACOES, 0) | dict(s.execute(
            select(Resposta.depoimento_situacao, func.count()).where(Resposta.depoimento_em.is_not(None))
            .group_by(Resposta.depoimento_situacao)).all())
        consulta = _consulta()
        if situacao:
            consulta = consulta.where(Resposta.depoimento_situacao == situacao)
        total = s.scalar(select(func.count()).select_from(consulta.subquery()))
        linhas = s.execute(consulta.order_by(Resposta.depoimento_em.desc(), Resposta.id.desc())
                           .limit(pg.por_pagina).offset(pg.offset)).all()
        return pg.resultado([_json(*x) for x in linhas], total) | {"resumo": resumo}


def alterar(ctx: Contexto, resposta_id: int, situacao: str) -> dict:
    with em_conta(ctx.conta_id) as s:
        linha = s.execute(_consulta().where(Resposta.id == resposta_id)).one_or_none()
        if linha is None:
            raise nao_encontrado("Depoimento não encontrado.")
        r = linha[0]
        if r.depoimento_situacao != situacao:
            r.depoimento_situacao = situacao
            s.flush()
            registrar(s, "depoimento_alterado", "info", {"resposta_id": r.id, "situacao": situacao},
                      usuario_id=ctx.usuario_id)
        return _json(*linha)


def _ao_editar_resposta(s: Session, r: Resposta, antes: dict) -> None:
    if r.depoimento_em is None or r.depoimento_situacao == "pendente":
        return
    if antes["comentario_cliente"] != r.comentario_cliente or antes["grupo"] != r.grupo:
        r.depoimento_situacao = "pendente"
        s.flush()


GANCHOS_EDICAO.append(_ao_editar_resposta)
