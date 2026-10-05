"""Etapa 5i: os sinais da saúde de várias empresas de uma vez (um número fixo de consultas agrupadas, sem N+1) e a
nota de cada uma (`regras.calcular`). Só empresas ativas; pausada ou perdida = sem saúde."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import String, and_, cast, func, select
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.modelos import Acao, Contato, Convite, Empresa, Envio, PerfilContato, Resposta
from toqqi.modulos.acoes.regras import aberta
from toqqi.modulos.saude.regras import JANELA, Sinais, calcular


def _inicio_do_dia(d: date) -> datetime:
    return datetime.combine(d, time(0), tzinfo=relogio.FUSO)


def _dia(momento: datetime) -> date:
    return momento.astimezone(relogio.FUSO).date()


def sinais(s: Session, empresa_ids: list[int], hoje: date) -> dict[int, Sinais]:
    from toqqi.modulos.painel.servico import SAIU_CONVITE  # aqui: o painel importa empresas, que importa este módulo

    if not empresa_ids:
        return {}
    ini_j = _inicio_do_dia(hoje - timedelta(days=JANELA - 1))
    ini_ant = _inicio_do_dia(hoje - timedelta(days=2 * JANELA - 1))
    sin = {e: Sinais() for e in empresa_ids}
    ids = empresa_ids

    # NPS por janela (atual e anterior)
    nps = Resposta.tipo_nota == "nps"
    validas = and_(Resposta.empresa_id.in_(ids), Resposta.arquivada.is_(False), Resposta.nota.is_not(None))
    atual = (Resposta.data_resposta >= ini_j).label("atual")
    for e, atual_, grupo, n in s.execute(
            select(Resposta.empresa_id, atual, Resposta.grupo, func.count())
            .where(validas, nps, Resposta.data_resposta >= ini_ant)
            .group_by(Resposta.empresa_id, atual, Resposta.grupo)):
        alvo = "nps_j" if atual_ else "nps_anterior"
        p, ne, d = getattr(sin[e], alvo)
        setattr(sin[e], alvo, (p + n * (grupo == "promotor"), ne + n * (grupo == "neutro"), d + n * (grupo == "detrator")))

    # última resposta (NPS ou CSAT) de cada empresa, em qualquer data
    ultima = dict(s.execute(select(Resposta.empresa_id, func.max(Resposta.data_resposta))
                            .where(Resposta.empresa_id.in_(ids), Resposta.arquivada.is_(False))
                            .group_by(Resposta.empresa_id)).all())
    for e in ultima:
        sin[e].respondeu_alguma_vez = True

    # convites que saíram (com o envio do convite em SAIU_CONVITE)
    saiu = (select(Envio.convite_id).where(Envio.tipo == "convite", Envio.situacao.in_(SAIU_CONVITE),
                                           Envio.convite_id == Convite.id).exists())
    convites = s.execute(select(Convite.empresa_id, Convite.contato_id, Convite.criado_em)
                         .where(Convite.empresa_id.in_(ids), Convite.canal.in_(("email", "whatsapp")), saiu)).all()
    ativos = set(s.scalars(select(Contato.id).where(Contato.empresa_id.in_(ids), Contato.ativo.is_(True))))
    convidados = defaultdict(set)
    for e, contato, criado in convites:
        sx = sin[e]
        dia = _dia(criado)
        sx.primeiro_convite = min(filter(None, (sx.primeiro_convite, dia)))
        if e not in ultima or criado > ultima[e]:
            sx.pendente_desde = min(filter(None, (sx.pendente_desde, dia)))
        if criado >= ini_j and contato in ativos:
            convidados[e].add(contato)
    responderam = defaultdict(set)
    for e, contato in s.execute(select(Resposta.empresa_id, Resposta.contato_id).distinct()
                                .where(validas, nps, Resposta.data_resposta >= ini_j, Resposta.contato_id.is_not(None))):
        responderam[e].add(contato)
    for e, cs in convidados.items():
        sin[e].convidados = len(cs)
        sin[e].convidados_responderam = len(cs & responderam[e])

    # decisores (contatos ativos com o perfil "Decisor")
    decisores = defaultdict(set)
    for e, c in s.execute(select(Contato.empresa_id, Contato.id).join(PerfilContato, PerfilContato.id == Contato.perfil_id)
                          .where(Contato.empresa_id.in_(ids), Contato.ativo.is_(True),
                                 cast(PerfilContato.nome, String).ilike("decisor"))):
        decisores[e].add(c)
    todos_decisores = set().union(*decisores.values()) if decisores else set()
    if todos_decisores:
        for e, c, quando, grupo, nota in s.execute(
                select(Resposta.empresa_id, Resposta.contato_id, Resposta.data_resposta, Resposta.grupo, Resposta.nota)
                .where(validas, nps, Resposta.contato_id.in_(todos_decisores))
                .order_by(Resposta.data_resposta)):
            sx = sin[e]
            sx.decisor_ultima = _dia(quando)
            if quando >= ini_j:
                sx.decisor_j = (grupo, nota, _dia(quando))
        for e, contato, _ in convites:
            if contato in decisores.get(e, ()):
                sin[e].decisor_convidado = True
    for e in decisores:
        sin[e].tem_decisor = True

    # planos de ação abertos
    for e, atrasados, de_detrator in s.execute(
            select(Acao.empresa_id, func.count().filter(Acao.prazo < hoje),
                   func.count().filter(Acao.grupo.in_(("detrator", "insatisfeito")),
                                       (Acao.prazo.is_(None)) | (Acao.prazo >= hoje)))
            .where(Acao.empresa_id.in_(ids), aberta()).group_by(Acao.empresa_id)):
        sin[e].atrasados, sin[e].abertos_detrator = atrasados, de_detrator
    return sin


def saude_das_empresas(s: Session, hoje: date | None = None, empresa_ids: list[int] | None = None) -> dict[int, dict]:
    """{empresa_id: saúde} das empresas ativas (todas da conta, ou só as pedidas)."""
    hoje = hoje or relogio.hoje()
    consulta = select(Empresa.id, Empresa.renovacao_em).where(Empresa.ativa.is_(True))
    if empresa_ids is not None:
        consulta = consulta.where(Empresa.id.in_(empresa_ids))
    empresas = dict(s.execute(consulta).all())
    todos = sinais(s, list(empresas), hoje)
    return {e: calcular(todos[e], hoje, empresas[e]) for e in empresas}
