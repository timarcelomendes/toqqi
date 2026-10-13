"""Plataforma › Feedback › Denúncias (Plano Grátis, docs/api-plano-gratis.md): o que chegou pelo "Denunciar esta
pesquisa" das contas Grátis, para a equipe conferir. Só o modo sistema lê e grava a tabela (a conta denunciada nunca
vê). Uma denúncia aberta nos últimos 30 dias pesa na nota de risco (`risco.calcular`, sinal `denuncias`); marcar
`descartada` tira o peso.
"""
from sqlalchemy import func, select

from toqqi.core import relogio
from toqqi.core.db import modo_sistema
from toqqi.core.errors import nao_encontrado
from toqqi.modelos import Conta, Denuncia

LIMITE_LISTA = 300
SITUACOES = ("aberta", "procedente", "descartada")


def _json(d: Denuncia, conta_nome: str | None, conta_situacao: str | None) -> dict:
    return {"id": d.id, "conta": {"id": d.conta_id, "nome": conta_nome, "situacao": conta_situacao},
            "formulario": {"id": d.formulario_id, "nome": d.formulario_nome}, "origem": d.origem, "motivo": d.motivo,
            "detalhe": d.detalhe, "situacao": d.situacao, "criada_em": d.criada_em, "resolvida_em": d.resolvida_em,
            "nota_interna": d.nota_interna}


def contagem(s) -> int:
    return s.scalar(select(func.count()).select_from(Denuncia).where(Denuncia.situacao == "aberta"))


def listar(situacao: str = "abertas") -> dict:
    """{itens, abertas}: as denúncias (abertas, ou todas), das mais novas às mais antigas, até 300."""
    with modo_sistema() as s:
        consulta = (select(Denuncia, Conta.nome, Conta.situacao).outerjoin(Conta, Conta.id == Denuncia.conta_id)
                    .order_by(Denuncia.criada_em.desc(), Denuncia.id.desc()).limit(LIMITE_LISTA))
        if situacao == "abertas":
            consulta = consulta.where(Denuncia.situacao == "aberta")
        itens = [_json(d, nome, sit) for d, nome, sit in s.execute(consulta)]
        return {"itens": itens, "abertas": contagem(s)}


def alterar(denuncia_id: int, situacao: str | None, nota_interna: str | None, mudar_nota: bool) -> dict:
    """Muda a situação (procedente ou descartada fecha; aberta reabre) e/ou a nota interna."""
    with modo_sistema() as s:
        d = s.get(Denuncia, denuncia_id, with_for_update=True)
        if d is None:
            raise nao_encontrado("Denúncia não encontrada.")
        if situacao is not None and situacao != d.situacao:
            d.situacao = situacao
            d.resolvida_em = None if situacao == "aberta" else relogio.agora()
        if mudar_nota:
            d.nota_interna = nota_interna or None
        s.flush()
        conta = s.execute(select(Conta.nome, Conta.situacao).where(Conta.id == d.conta_id)).one_or_none()
        return _json(d, conta.nome if conta else None, conta.situacao if conta else None)
