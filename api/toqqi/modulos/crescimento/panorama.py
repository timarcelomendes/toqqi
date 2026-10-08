"""Panorama do Crescimento (pedido do Marcelo em 08/10/2026: "faça a tela de crescimento ficar incrível"): o topo da
tela conta, num período, quanto os clientes felizes trouxeram e o que fazer a seguir (docs/api-crescimento-panorama.md).

- `receita`: a mesma conta da "Receita gerada pelo Toqqi" do Início (`resumo`): o valor mensal das indicações recebidas
  no período que viraram cliente + o valor das ofertas feitas no período que foram aceitas; e o mesmo no período
  anterior, de mesmo tamanho, para comparar.
- `indicacoes`: a trilha do promotor ao cliente. `promotores` = respostas de nota máxima no período (NPS 9–10 ou
  CSAT 5, como o convite de indicação), não arquivadas; `recebidas` = indicações recebidas no período, por situação;
  `abordadas` = as que já saíram de "nova" (em contato, cliente ou não avançou); `esperando_contato` = as que estão em
  "nova" agora, de qualquer data (o próximo passo não esquece a indicação que ficou para trás).
- `ofertas`: as feitas no período, por resultado (`aguardando` = sem resultado ainda); `prontas` = empresas nas listas
  de Oportunidades agora (Pode crescer ou Promotores recentes, a regra de ouro já aplicada); `sem_oferta` = as prontas
  sem oferta nos últimos 90 dias.
- `fas`: quem mais indicou no período (até 5 empresas): indicações, quantas viraram cliente e o valor mensal delas.
- `depoimentos`: aprovados e pendentes (de sempre) e o aprovado mais recente em destaque.
- `meses`: a receita nova de cada um dos 12 meses (de São Paulo) que terminam no mês de hoje, pela mesma conta da
  `receita` (o mês de hoje vai até hoje); não depende do período escolhido.
- `tem_historico`: a conta já teve um promotor, uma indicação ou uma oferta, em qualquer data (sem nada disso, a tela
  explica como o Crescimento funciona em vez de mostrar zeros).
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Date, cast, exists, func, or_, select

from toqqi.core import relogio
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto
from toqqi.core.filtros import entre_datas
from toqqi.core.relogio import FUSO_NOME
from toqqi.modelos import Contato, Empresa, Indicacao, Oferta, Resposta
from toqqi.modulos.crescimento import oportunidades
from toqqi.modulos.crescimento.depoimentos import assinatura
from toqqi.modulos.painel.servico import _validar_periodo

DIAS_PADRAO = 90
DIAS_SEM_OFERTA = 90
MAX_FAS = 5
MAX_DESTAQUE = 600  # caracteres do depoimento em destaque (a tela corta em linhas)
MESES = 12
NOTA_MAXIMA = or_((Resposta.tipo_nota == "nps") & (Resposta.nota >= 9), (Resposta.tipo_nota == "csat") & (Resposta.nota == 5))


def _periodos(de: date | None, ate: date | None) -> tuple[date | None, date | None, tuple[date, date] | None]:
    """(de, até, período anterior de mesmo tamanho). Sem nenhum dos dois: os últimos 90 dias. Só o começo: até hoje.
    Só o fim: sem começo, e então sem período anterior."""
    if de is None and ate is None:
        ate = relogio.hoje()
        de = oportunidades.desde(ate, DIAS_PADRAO)
    if de is None:
        return de, ate, None
    fim = ate or relogio.hoje()
    dias = (fim - de).days + 1
    return de, ate, (de - timedelta(days=dias), de - timedelta(days=1))


def _receita(s, conta_id: int, de: date | None, ate: date | None) -> tuple[Decimal, Decimal]:
    ind = s.scalar(select(func.coalesce(func.sum(Indicacao.valor_mensal), 0)).where(
        Indicacao.conta_id == conta_id, Indicacao.situacao == "cliente", *entre_datas(Indicacao.criada_em, de, ate)))
    ofe = s.scalar(select(func.coalesce(func.sum(Oferta.valor), 0)).where(
        Oferta.conta_id == conta_id, Oferta.resultado == "aceitou", *entre_datas(Oferta.criada_em, de, ate)))
    return Decimal(ind), Decimal(ofe)


def _mes_menos(d: date, n: int) -> date:
    """Primeiro dia do mês `n` meses antes do mês de `d`."""
    ano, mes = divmod(d.year * 12 + d.month - 1 - n, 12)
    return date(ano, mes + 1, 1)


def _meses(s, conta_id: int, hoje: date) -> list[dict]:
    inicio = _mes_menos(hoje, MESES - 1)

    def por_mes(coluna_data, valor, *filtros) -> dict:
        mes = cast(func.date_trunc("month", func.timezone(FUSO_NOME, coluna_data)), Date)
        return dict(s.execute(select(mes, func.coalesce(func.sum(valor), 0))
                              .where(*filtros, *entre_datas(coluna_data, inicio, hoje)).group_by(mes)).all())

    ind = por_mes(Indicacao.criada_em, Indicacao.valor_mensal, Indicacao.conta_id == conta_id, Indicacao.situacao == "cliente")
    ofe = por_mes(Oferta.criada_em, Oferta.valor, Oferta.conta_id == conta_id, Oferta.resultado == "aceitou")
    meses = []
    for n in range(MESES - 1, -1, -1):
        m = _mes_menos(hoje, n)
        i, o = Decimal(ind.get(m, 0)), Decimal(ofe.get(m, 0))
        meses.append({"mes": f"{m.year:04d}-{m.month:02d}", "indicacoes": i, "ofertas": o, "total": i + o})
    return meses


def _indicacoes(s, conta_id: int, de: date | None, ate: date | None) -> dict:
    promotores = s.scalar(select(func.count()).select_from(Resposta).where(
        Resposta.conta_id == conta_id, Resposta.arquivada.is_(False), NOTA_MAXIMA,
        *entre_datas(Resposta.data_resposta, de, ate)))
    r = s.execute(select(
        func.count(),
        func.count().filter(Indicacao.situacao == "nova"),
        func.count().filter(Indicacao.situacao == "em_contato"),
        func.count().filter(Indicacao.situacao == "cliente"),
        func.count().filter(Indicacao.situacao == "nao_avancou"),
    ).where(Indicacao.conta_id == conta_id, *entre_datas(Indicacao.criada_em, de, ate))).one()
    esperando = s.scalar(select(func.count()).select_from(Indicacao).where(
        Indicacao.conta_id == conta_id, Indicacao.situacao == "nova"))
    return {"promotores": promotores, "recebidas": r[0], "novas": r[1], "em_contato": r[2], "clientes": r[3],
            "nao_avancou": r[4], "abordadas": r[0] - r[1], "esperando_contato": esperando}


def _ofertas(s, ctx: Contexto, de: date | None, ate: date | None) -> dict:
    r = s.execute(select(
        func.count(),
        func.count().filter(Oferta.resultado == "aceitou"),
        func.count().filter(Oferta.resultado == "recusou"),
        func.count().filter(Oferta.resultado == "sem_resposta"),
        func.count().filter(Oferta.resultado.is_(None)),
    ).where(Oferta.conta_id == ctx.conta_id, *entre_datas(Oferta.criada_em, de, ate))).one()
    hoje = relogio.hoje()
    prontas = {c.id for c in oportunidades._pode_crescer(s, ctx, hoje)} | \
        {c.id for c in oportunidades._promotores(s, ctx, hoje)}
    com_oferta = set(s.scalars(select(Oferta.empresa_id).distinct().where(
        Oferta.conta_id == ctx.conta_id, Oferta.empresa_id.in_(prontas),
        *entre_datas(Oferta.criada_em, oportunidades.desde(hoje, DIAS_SEM_OFERTA), hoje)))) if prontas else set()
    return {"feitas": r[0], "aceitas": r[1], "recusadas": r[2], "sem_resposta": r[3], "aguardando": r[4],
            "prontas": len(prontas), "sem_oferta": len(prontas - com_oferta)}


def _fas(s, conta_id: int, de: date | None, ate: date | None) -> list[dict]:
    linhas = s.execute(
        select(Empresa.id, Empresa.nome, func.count(Indicacao.id),
               func.count().filter(Indicacao.situacao == "cliente"),
               func.coalesce(func.sum(Indicacao.valor_mensal), 0))
        .join(Empresa, Empresa.id == Indicacao.indicador_empresa_id)
        .where(Indicacao.conta_id == conta_id, *entre_datas(Indicacao.criada_em, de, ate))
        .group_by(Empresa.id, Empresa.nome)
        .order_by(func.count(Indicacao.id).desc(), func.count().filter(Indicacao.situacao == "cliente").desc(),
                  func.coalesce(func.sum(Indicacao.valor_mensal), 0).desc(), Empresa.nome, Empresa.id)
        .limit(MAX_FAS)).all()
    return [{"empresa": {"id": i, "nome": n}, "indicacoes": q, "clientes": c, "receita_mensal": v}
            for i, n, q, c, v in linhas]


def _depoimentos(s) -> dict:
    contagem = dict(s.execute(select(Resposta.depoimento_situacao, func.count())
                              .where(Resposta.depoimento_em.is_not(None))
                              .group_by(Resposta.depoimento_situacao)).all())
    destaque = s.execute(
        select(Resposta, Contato.nome, Empresa.nome)
        .outerjoin(Contato, Contato.id == Resposta.contato_id)
        .outerjoin(Empresa, Empresa.id == Resposta.empresa_id)
        .where(Resposta.depoimento_em.is_not(None), Resposta.depoimento_situacao == "aprovado",
               Resposta.arquivada.is_(False), func.length(func.trim(func.coalesce(Resposta.comentario_cliente, ""))) > 0)
        .order_by(Resposta.depoimento_em.desc(), Resposta.id.desc()).limit(1)).one_or_none()
    em_destaque = None
    if destaque is not None:
        r, contato, empresa = destaque
        texto = " ".join((r.comentario_cliente or "").split())
        em_destaque = {"resposta_id": r.id, "comentario": texto[:MAX_DESTAQUE], "assinatura": assinatura(contato, empresa),
                       "nota": r.nota, "tipo_nota": r.tipo_nota, "data_resposta": r.data_resposta}
    return {"aprovados": contagem.get("aprovado", 0), "pendentes": contagem.get("pendente", 0),
            "destaque": em_destaque}


def _tem_historico(s, conta_id: int) -> bool:
    return bool(s.scalar(select(or_(
        exists().where(Indicacao.conta_id == conta_id),
        exists().where(Oferta.conta_id == conta_id),
        exists().where(Resposta.conta_id == conta_id, Resposta.arquivada.is_(False), NOTA_MAXIMA),
    ))))


def panorama(ctx: Contexto, de: date | None, ate: date | None) -> dict:
    _validar_periodo(de, ate)
    de, ate, anterior = _periodos(de, ate)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        ind, ofe = _receita(s, ctx.conta_id, de, ate)
        antes = sum(_receita(s, ctx.conta_id, *anterior), Decimal(0)) if anterior else None
        dados = {
            "periodo": {"de": de, "ate": ate},
            "anterior": {"de": anterior[0], "ate": anterior[1]} if anterior else None,
            "receita": {"total": ind + ofe, "indicacoes": ind, "ofertas": ofe, "anterior": antes},
            "indicacoes": _indicacoes(s, ctx.conta_id, de, ate),
            "ofertas": _ofertas(s, ctx, de, ate),
            "fas": _fas(s, ctx.conta_id, de, ate),
            "depoimentos": _depoimentos(s),
            "meses": _meses(s, ctx.conta_id, relogio.hoje()),
            "tem_historico": _tem_historico(s, ctx.conta_id),
        }
    return dados
