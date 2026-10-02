"""Relatórios (etapa 4b, `relatorios.ver`): empresas (com a matriz NPS × valor), grupos de clientes, temas, entregas,
responsáveis, operação e histórico de uma empresa.

Regras comuns (as do painel): só respostas não arquivadas; a data é `data_resposta`; período inclusivo em dias de
São Paulo (sem `de`/`ate` = todo o histórico); `grupo_id` = grupo de empresas; `so_ativos` (padrão true) tira as
empresas inativas (e as respostas delas). NPS por empresa = respostas NPS com aquela empresa no período.

Desempenho: as respostas são agregadas no banco (poucas consultas agrupadas por empresa, tema, semana ou valor do
contexto, com `conta_id` explícito e sem JIT); o que é por empresa (até alguns milhares de linhas) é montado em
Python a partir desses agregados.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Date, DateTime, Text, and_, any_, cast, func, literal, not_, select, true
from sqlalchemy.orm import Session, aliased

from toqqi.core import relogio
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto
from toqqi.core.errors import nao_encontrado
from toqqi.core.filtros import entre_datas, inicio_do_dia
from toqqi.core.paginacao import Pagina
from toqqi.core.relogio import FUSO_NOME
from toqqi.modelos import (
    Acao,
    Cargo,
    Conta,
    Contato,
    Empresa,
    Grupo,
    PerfilContato,
    Responsavel,
    Resposta,
    Segmento,
)
from toqqi.modulos.acoes.regras import aberta
from toqqi.modulos.envios.configuracao import obter as config_envios
from toqqi.modulos.ia.regras import ia_ativa
from toqqi.modulos.painel.servico import Filtro, _com_empresa, _taxa_resposta, _validar_periodo
from toqqi.modulos.relatorios import picos as picos_mod
from toqqi.modulos.relatorios.regras import (
    FAIXAS_TEMPO,
    FAIXAS_VALOR,
    QUADRANTES,
    ROTULOS_DIMENSAO,
    ROTULOS_FAIXA_NPS,
    EmpresaRel,
    FiltroEmpresas,
    carregar_empresas,
    chave_nome,
    data_br,
    gerar_csv,
    mediana,
    num,
    quadrante,
    sim_nao,
)
from toqqi.modulos.respostas import indicadores as ind
from toqqi.modulos.respostas import temas as temas_mod
from toqqi.modulos.respostas.servico import ROTULOS_CANAL, ROTULOS_SENTIMENTO, bloco_csat, valor_contexto

NPS = Resposta.tipo_nota == "nps"
CSAT = Resposta.tipo_nota == "csat"
COM_NOTA = Resposta.tipo_nota.in_(("nps", "csat"))
MAX_PONTOS = 1000
MAX_SEM_RESPOSTA = 1000
MAX_LINHA_DO_TEMPO = 500
MAX_MESES = 24
MAX_SEMANAS = 26
SEMANAS_SEM_PERIODO = 12
AMOSTRA_PEQUENA = 5
MIN_MENCOES_PRIORIDADE = 2


@dataclass
class Periodo:
    conta_id: int
    de: date | None
    ate: date | None

    def respostas(self, *extra) -> list:
        return [Resposta.conta_id == self.conta_id, Resposta.arquivada.is_(False),
                *entre_datas(Resposta.data_resposta, self.de, self.ate), *extra]


def _ultima_json(u) -> dict | None:
    return {"data": u[0], "nota": u[1], "tipo_nota": u[2]} if u else None


# ---- agregados por empresa -------------------------------------------------------

def _nps_empresas(s: Session, p: Periodo) -> dict[int, tuple[int, int, int, int]]:
    """{empresa: (promotores, neutros, detratores, soma das notas)} das respostas NPS do período."""
    linhas = s.execute(
        select(Resposta.empresa_id, func.count().filter(Resposta.grupo == "promotor"),
               func.count().filter(Resposta.grupo == "neutro"), func.count().filter(Resposta.grupo == "detrator"),
               func.coalesce(func.sum(Resposta.nota), 0))
        .where(*p.respostas(NPS, Resposta.empresa_id.is_not(None))).group_by(Resposta.empresa_id)).all()
    return {e: (pr, ne, de, soma) for e, pr, ne, de, soma in linhas}


def _cobertura_empresas(s: Session, p: Periodo) -> dict[int, tuple[int, int]]:
    """{empresa: (contatos ativos, contatos ativos com resposta NPS no período)}."""
    respondeu = (select(Resposta.contato_id).where(*p.respostas(NPS, Resposta.contato_id.is_not(None)))
                 .distinct().subquery())
    linhas = s.execute(
        select(Contato.empresa_id, func.count(), func.count(respondeu.c.contato_id))
        .select_from(Contato).outerjoin(respondeu, respondeu.c.contato_id == Contato.id)
        .where(Contato.conta_id == p.conta_id, Contato.ativo.is_(True), Contato.empresa_id.is_not(None))
        .group_by(Contato.empresa_id)).all()
    return {e: (total, responderam) for e, total, responderam in linhas}


def _ultimas_respostas(s: Session, conta_id: int) -> dict[int, tuple]:
    """{empresa: (data, nota, tipo_nota)} da resposta mais recente de qualquer data."""
    linhas = s.execute(
        select(Resposta.empresa_id, Resposta.data_resposta, Resposta.nota, Resposta.tipo_nota)
        .distinct(Resposta.empresa_id)
        .where(Resposta.conta_id == conta_id, Resposta.arquivada.is_(False), Resposta.empresa_id.is_not(None))
        .order_by(Resposta.empresa_id, Resposta.data_resposta.desc(), Resposta.id.desc())).all()
    return {e: (d, n, t) for e, d, n, t in linhas}


def _acoes_empresas(s: Session, conta_id: int, hoje: date) -> dict[int, tuple[int, int]]:
    """{empresa: (ações abertas, vencidas)} agora."""
    linhas = s.execute(
        select(Acao.empresa_id, func.count(), func.count().filter(Acao.prazo < hoje))
        .where(Acao.conta_id == conta_id, aberta(), Acao.empresa_id.is_not(None)).group_by(Acao.empresa_id)).all()
    return {e: (abertas, vencidas) for e, abertas, vencidas in linhas}


def _cobertura_json(total: int, responderam: int) -> dict:
    return {"contatos_ativos": total, "responderam": responderam, "percentual": ind.percentual(responderam, total)}


def _filtro_empresas(f) -> FiltroEmpresas:
    return FiltroEmpresas(grupo_id=f.grupo_id, so_ativos=f.so_ativos is not False,
                          segmento_id=getattr(f, "segmento_id", None),
                          responsavel_id=getattr(f, "responsavel_id", None),
                          faixa_valor=getattr(f, "faixa_valor", None), tempo_cliente=getattr(f, "tempo_cliente", None))


# ---- empresas ---------------------------------------------------------------------

def _dados_empresas(s: Session, ctx: Contexto, f) -> tuple[list[dict], dict, dict]:
    hoje = relogio.hoje()
    p = Periodo(ctx.conta_id, f.de, f.ate)
    empresas = carregar_empresas(s, ctx.conta_id, _filtro_empresas(f), hoje)
    nps, cobertura = _nps_empresas(s, p), _cobertura_empresas(s, p)
    ultimas, acoes = _ultimas_respostas(s, ctx.conta_id), _acoes_empresas(s, ctx.conta_id, hoje)
    itens = []
    for e in empresas:
        pr, ne, de, _ = nps.get(e.id, (0, 0, 0, 0))
        bloco = ind.bloco_nps(pr, ne, de)
        total, responderam = cobertura.get(e.id, (0, 0))
        itens.append({
            "empresa": {"id": e.id, "nome": e.nome, "ativa": e.ativa}, "grupo": e.grupo, "segmento": e.segmento,
            "responsavel": e.responsavel, "valor_mensal": e.valor_mensal, "cliente_desde": e.cliente_desde,
            "nps": bloco, "cobertura": _cobertura_json(total, responderam),
            "ultima_resposta": _ultima_json(ultimas.get(e.id)), "em_risco": de > 0, "quadrante": None,
            "acoes_abertas": acoes.get(e.id, (0, 0))[0],
        })
    # matriz NPS × valor: empresas com NPS no período e valor cadastrado
    com_valor = [x for x in itens if x["nps"]["total"] and x["valor_mensal"] is not None]
    meio = mediana([x["valor_mensal"] for x in com_valor])
    quadrantes = dict.fromkeys(QUADRANTES, 0)
    for x in com_valor:
        x["quadrante"] = quadrante(x["valor_mensal"], x["nps"]["valor"], meio)
        quadrantes[x["quadrante"]] += 1
    pontos = sorted(com_valor, key=lambda x: (-x["valor_mensal"], chave_nome(x["empresa"]["nome"])))[:MAX_PONTOS]
    matriz = {
        "mediana_valor": meio, "quadrantes": quadrantes,
        "pontos": [{"empresa": {"id": x["empresa"]["id"], "nome": x["empresa"]["nome"]}, "nps": x["nps"]["valor"],
                    "valor_mensal": x["valor_mensal"], "respostas": x["nps"]["total"], "quadrante": x["quadrante"]}
                   for x in pontos],
        "sem_valor": sum(1 for x in itens if x["nps"]["total"] and x["valor_mensal"] is None),
    }
    receita_total = sum((x["valor_mensal"] for x in itens if x["valor_mensal"] is not None), Decimal(0))
    em_risco = [x for x in itens if x["em_risco"]]
    receita_risco = sum((x["valor_mensal"] for x in em_risco if x["valor_mensal"] is not None), Decimal(0))
    por_faixa = {"excelente": 0, "muito_bom": 0, "pode_melhorar": 0, "critico": 0, "sem_respostas": 0}
    for x in itens:
        por_faixa[x["nps"]["faixa"] or "sem_respostas"] += 1
    ativos = sum(x["cobertura"]["contatos_ativos"] for x in itens)
    responderam = sum(x["cobertura"]["responderam"] for x in itens)
    resumo = {
        "empresas": len(itens), "com_respostas": sum(1 for x in itens if x["nps"]["total"]),
        "cobertura": _cobertura_json(ativos, responderam),
        "receita": {"total": receita_total, "em_risco": receita_risco, "empresas_em_risco": len(em_risco),
                    "sem_valor": sum(1 for x in em_risco if x["valor_mensal"] is None),
                    "percentual": ind.percentual(receita_risco, receita_total)},
        "por_faixa": por_faixa,
    }
    return itens, resumo, matriz


def _ordenar_empresas(itens: list[dict], ordem: str | None) -> list[dict]:
    def nome(x):
        return chave_nome(x["empresa"]["nome"]), x["empresa"]["id"]

    def valor(x):
        return (0, -x["valor_mensal"]) if x["valor_mensal"] is not None else (1, 0)

    def nps(x):
        return (0, x["nps"]["valor"]) if x["nps"]["valor"] is not None else (1, 0)

    chaves = {
        "prioridade": lambda x: (not x["em_risco"], valor(x), nps(x), nome(x)),
        "nps": lambda x: (nps(x), nome(x)),
        "valor": lambda x: (valor(x), nome(x)),
        "cobertura": lambda x: ((0, x["cobertura"]["percentual"]) if x["cobertura"]["percentual"] is not None
                                else (1, 0), nome(x)),
        "respostas": lambda x: (-x["nps"]["total"], nome(x)),
        "nome": nome,
    }
    return sorted(itens, key=chaves[ordem or "prioridade"])


def _filtrar_tabela(itens: list[dict], f) -> list[dict]:
    """Filtros só da tabela: busca no nome, com/sem respostas no período e quadrante da matriz."""
    if f.busca and f.busca.strip():
        termo = chave_nome(f.busca.strip())
        itens = [x for x in itens if termo in chave_nome(x["empresa"]["nome"])]
    if f.respostas:
        itens = [x for x in itens if bool(x["nps"]["total"]) == (f.respostas == "com")]
    if f.quadrante:
        itens = [x for x in itens if x["quadrante"] == f.quadrante]
    return _ordenar_empresas(itens, f.ordem)


def empresas(ctx: Contexto, f, pg: Pagina) -> dict:
    _validar_periodo(f.de, f.ate)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        itens, resumo, matriz = _dados_empresas(s, ctx, f)
    tabela = _filtrar_tabela(itens, f)
    return {"resumo": resumo, "matriz": matriz,
            **pg.resultado(tabela[pg.offset:pg.offset + pg.por_pagina], len(tabela))}


CABECALHO_EMPRESAS = ["Empresa", "Ativa", "Grupo", "Segmento", "Responsável", "Valor mensal", "Cliente desde", "NPS",
                      "Faixa", "Respostas", "Promotores", "Neutros", "Detratores", "Contatos ativos", "Responderam",
                      "Cobertura (%)", "Última resposta", "Em risco", "Quadrante", "Ações abertas"]


def empresas_csv(ctx: Contexto, f) -> str:
    _validar_periodo(f.de, f.ate)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        itens, _, _ = _dados_empresas(s, ctx, f)
    linhas = []
    for x in _filtrar_tabela(itens, f):
        b, c = x["nps"], x["cobertura"]
        linhas.append([
            x["empresa"]["nome"], sim_nao(x["empresa"]["ativa"]), (x["grupo"] or {}).get("nome", ""),
            (x["segmento"] or {}).get("nome", ""), (x["responsavel"] or {}).get("nome", ""), num(x["valor_mensal"]),
            data_br(x["cliente_desde"]), num(b["valor"]), ROTULOS_FAIXA_NPS.get(b["faixa"], ""), num(b["total"]),
            num(b["promotores"]), num(b["neutros"]), num(b["detratores"]), num(c["contatos_ativos"]),
            num(c["responderam"]), num(c["percentual"]),
            data_br(x["ultima_resposta"]["data"]) if x["ultima_resposta"] else "", sim_nao(x["em_risco"]),
            QUADRANTES.get(x["quadrante"], ""), num(x["acoes_abertas"]),
        ])
    return gerar_csv(CABECALHO_EMPRESAS, linhas)


# ---- grupos de clientes ---------------------------------------------------------

def _somar(blocos: list[tuple[int, int, int]]) -> dict:
    return ind.bloco_nps(sum(b[0] for b in blocos), sum(b[1] for b in blocos), sum(b[2] for b in blocos))


def _ordem_nps(item: dict, nulo: bool) -> tuple:
    v = item["nps"]["valor"]
    return (nulo, v is None, v if v is not None else 0)


def grupos(ctx: Contexto, f) -> dict:
    """Só respostas NPS ligadas a uma empresa do filtro. `empresas` = empresas com respostas no período."""
    _validar_periodo(f.de, f.ate)
    hoje = relogio.hoje()
    p = Periodo(ctx.conta_id, f.de, f.ate)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        lista = carregar_empresas(s, ctx.conta_id, _filtro_empresas(f), hoje)
        nps = _nps_empresas(s, p)
        por_tema = s.execute(_temas_por_empresa(p)).all()
    com_respostas = [(e, nps[e.id][:3]) for e in lista if e.id in nps and sum(nps[e.id][:3])]

    def agrupar(chave) -> dict:
        grupos_: dict = defaultdict(list)
        for e, bloco in com_respostas:
            grupos_[chave(e)].append(bloco)
        return grupos_

    def lista_ref(campo: str, rotulo: str) -> list[dict]:
        refs = {}
        for e, _ in com_respostas:
            r = getattr(e, campo)
            refs[r["id"] if r else None] = r
        itens = [{rotulo: refs[k], "empresas": len(blocos), "nps": _somar(blocos)}
                 for k, blocos in agrupar(lambda e: (getattr(e, campo) or {}).get("id")).items()]
        return sorted(itens, key=lambda x: (*_ordem_nps(x, x[rotulo] is None),
                                            chave_nome((x[rotulo] or {}).get("nome"))))

    def faixas(campo: str, tabela) -> list[dict]:
        grupos_ = agrupar(lambda e: getattr(e, campo))
        return [{"faixa": k, "rotulo": r, "empresas": len(grupos_.get(k, [])), "nps": _somar(grupos_.get(k, []))}
                for k, r in tabela]

    ids = {e.id for e, _ in com_respostas}
    temas: dict = defaultdict(lambda: [0, 0, 0])  # menções, soma das notas, reclamações
    for empresa_id, tema, mencoes, soma, reclamacoes in por_tema:
        if empresa_id in ids and tema in temas_mod.ROTULOS:
            temas[tema][0] += mencoes
            temas[tema][1] += soma
            temas[tema][2] += reclamacoes
    prioridades = []
    for tema, (mencoes, soma, reclamacoes) in temas.items():
        if mencoes >= MIN_MENCOES_PRIORIDADE:
            media = Decimal(soma) / mencoes
            prioridades.append(({"tema": tema, "rotulo": temas_mod.ROTULOS[tema], "mencoes": mencoes,
                                 "nota_media": ind.media(soma, mencoes, 1), "reclamacoes": reclamacoes},
                                mencoes * (10 - media)))
    prioridades.sort(key=lambda x: (-x[1], -x[0]["mencoes"], temas_mod.CHAVES.index(x[0]["tema"])))
    return {"segmentos": lista_ref("segmento", "segmento"), "grupos": lista_ref("grupo", "grupo"),
            "tempo_cliente": faixas("faixa_tempo", FAIXAS_TEMPO), "valor": faixas("faixa_valor", FAIXAS_VALOR),
            "prioridades": [x for x, _ in prioridades]}


def _temas_por_empresa(p: Periodo):
    """(empresa, tema, menções, soma das notas, reclamações) das respostas NPS do período."""
    sq = (select(Resposta.empresa_id, func.unnest(Resposta.temas).label("tema"), Resposta.nota,
                 Resposta.temas_reclamacao.label("reclamacao"))
          .where(*p.respostas(NPS, Resposta.empresa_id.is_not(None))).subquery())
    return (select(sq.c.empresa_id, sq.c.tema, func.count(), func.coalesce(func.sum(sq.c.nota), 0),
                   func.count().filter(sq.c.tema == any_(sq.c.reclamacao)))
            .group_by(sq.c.empresa_id, sq.c.tema))


# ---- temas ------------------------------------------------------------------------

def _filtro_respostas(ctx: Contexto, f) -> Filtro:
    return Filtro(ctx.conta_id, f.de, f.ate, f.grupo_id, f.so_ativos is not False)


def _contagem_temas(s: Session, conds: list) -> dict[str, list]:
    """Por tema: menções, reclamações, elogios, NPS (quantas e soma), sentimento da IA (positivo, neutro,
    negativo, sem análise)."""
    sq = (_com_empresa(select(func.unnest(Resposta.temas).label("tema"), Resposta.nota, Resposta.tipo_nota,
                              Resposta.temas_reclamacao.label("rec"), Resposta.temas_elogio.label("elo"),
                              Resposta.ia_situacao, Resposta.ia_temas).select_from(Resposta))
          .where(*conds, COM_NOTA).subquery())
    analisada = sq.c.ia_situacao == "analisada"

    def texto(v):
        return cast(literal(v), Text) if isinstance(v, str) else v

    def cita(**campos):
        """A IA citou o tema (com o sentimento dado, se houver)? Pela contenção `ia_temas @> [{...}]`."""
        par = func.jsonb_build_object(*[texto(x) for k, v in {"tema": sq.c.tema, **campos}.items() for x in (k, v)])
        return and_(analisada, sq.c.ia_temas.op("@>")(func.jsonb_build_array(par)))

    nps = sq.c.tipo_nota == "nps"
    linhas = s.execute(select(
        sq.c.tema, func.count(), func.count().filter(sq.c.tema == any_(sq.c.rec)),
        func.count().filter(sq.c.tema == any_(sq.c.elo)), func.count().filter(nps),
        func.coalesce(func.sum(sq.c.nota).filter(nps), 0),
        func.count().filter(cita(sentimento="positivo")), func.count().filter(cita(sentimento="neutro")),
        func.count().filter(cita(sentimento="negativo")), func.count().filter(cita()),
    ).group_by(sq.c.tema)).all()
    # sem análise = menções que a IA não classificou (resposta não analisada, ou o tema veio das palavras-chave)
    return {tema: [m, *resto[:-1], m - resto[-1]] for tema, m, *resto in linhas}


def _segunda(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _semanas(de: date | None, ate: date | None, hoje: date) -> list[date]:
    """Segundas-feiras das semanas mostradas (nunca vazio): as que tocam o período, até as 26 mais recentes. Sem
    `de` nem `ate`, as 12 últimas até a atual. Só `de`: daquela semana até a atual (ou só a semana de `de`, se ela é
    futura). Só `ate`: as 26 que terminam na semana de `ate`."""
    if de is None and ate is None:
        fim = _segunda(hoje)
        inicio = fim - timedelta(weeks=SEMANAS_SEM_PERIODO - 1)
    else:
        fim = _segunda(ate) if ate is not None else max(_segunda(hoje), _segunda(de))
        inicio = _segunda(de) if de is not None else fim - timedelta(weeks=MAX_SEMANAS - 1)
    inicio = max(inicio, fim - timedelta(weeks=MAX_SEMANAS - 1))
    return [inicio + timedelta(weeks=i) for i in range((fim - inicio).days // 7 + 1)]


def temas(ctx: Contexto, f) -> dict:
    _validar_periodo(f.de, f.ate)
    hoje = relogio.hoje()
    filtro = _filtro_respostas(ctx, f)
    conds = filtro.respostas()
    semanas = _semanas(f.de, f.ate, hoje)
    semana = cast(func.date_trunc("week", func.timezone(FUSO_NOME, Resposta.data_resposta)), Date)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        conta = s.get(Conta, ctx.conta_id)
        texto = Resposta.comentario_cliente != ""
        analisada = Resposta.ia_situacao == "analisada"
        geral = s.execute(_com_empresa(select(
            func.count().filter(texto), func.count().filter(texto, analisada),
            *[func.count().filter(texto, analisada, Resposta.ia_sentimento == x)
              for x in ("positivo", "neutro", "negativo", "misto")],
        ).select_from(Resposta)).where(*conds, COM_NOTA)).one()
        contagem = _contagem_temas(s, conds)
        anterior = None
        if f.de and f.ate:
            dias = (f.ate - f.de).days + 1
            anterior = _contagem_temas(s, filtro.respostas(f.de - timedelta(days=dias), f.de - timedelta(days=1)))
        janela = [Resposta.data_resposta >= inicio_do_dia(semanas[0]),
                  Resposta.data_resposta < inicio_do_dia(semanas[-1] + timedelta(days=7))]
        por_semana = dict(s.execute(_com_empresa(select(semana, func.count()).select_from(Resposta))
                                    .where(*conds, COM_NOTA, *janela).group_by(semana)).all())
        sq = (_com_empresa(select(semana.label("semana"), func.unnest(Resposta.temas).label("tema"),
                                  Resposta.temas_reclamacao.label("rec")).select_from(Resposta))
              .where(*conds, COM_NOTA, *janela).subquery())
        temas_semana = s.execute(select(sq.c.semana, sq.c.tema, func.count(),
                                        func.count().filter(sq.c.tema == any_(sq.c.rec)))
                                 .group_by(sq.c.semana, sq.c.tema)).all()
        picos = picos_mod.calcular(s, ctx.conta_id, hoje)
        ativa = ia_ativa(conta)
    com_comentario, analisadas, *sentimentos = geral
    itens = []
    for t in temas_mod.CHAVES:
        m, rec, elo, n_nps, soma, pos, neu, neg, sem = contagem.get(t, [0] * 9)
        itens.append({
            "tema": t, "rotulo": temas_mod.ROTULOS[t], "mencoes": m, "reclamacoes": rec, "elogios": elo,
            "nota_media": ind.media(soma, n_nps, 1),
            "variacao": None if anterior is None else m - anterior.get(t, [0])[0],
            "sentimento": {"positivo": pos, "neutro": neu, "negativo": neg, "sem_analise": sem},
        })
    mapa = defaultdict(dict)
    for sem_, tema, m, rec in temas_semana:
        mapa[sem_][tema] = {"mencoes": m, "reclamacoes": rec}
    return {
        "ia": {"ativa": ativa, "analisadas": analisadas, "com_comentario": com_comentario},
        "sentimento": {**dict(zip(("positivo", "neutro", "negativo", "misto"), sentimentos, strict=True)),
                       "sem_analise": com_comentario - analisadas},
        "temas": itens,
        "semanas": [{"inicio": x, "fim": x + timedelta(days=6), "respostas": por_semana.get(x, 0),
                     "temas": {t: mapa[x].get(t, {"mencoes": 0, "reclamacoes": 0}) for t in temas_mod.CHAVES}}
                    for x in semanas],
        "picos": picos,
    }


# ---- entregas (motorista, rota, filial, transportadora) ---------------------------

def _dados_entregas(s: Session, ctx: Contexto, f) -> tuple[list[dict], int]:
    conds = [*_filtro_respostas(ctx, f).respostas(), COM_NOTA]
    chave = valor_contexto(f.dimensao)
    bruto = func.btrim(Resposta.contexto[f.dimensao].astext)
    sem_valor = s.scalar(_com_empresa(select(func.count()).select_from(Resposta))
                         .where(*conds, func.coalesce(chave, "") == ""))
    com_valor = [*conds, func.coalesce(chave, "") != ""]
    if f.busca and f.busca.strip():
        com_valor.append(func.strpos(chave, f.busca.strip().lower()) > 0)
    linhas = s.execute(_com_empresa(select(
        chave.label("chave"), func.mode().within_group(bruto), func.count(),
        func.count().filter(NPS, Resposta.grupo == "promotor"), func.count().filter(NPS, Resposta.grupo == "neutro"),
        func.count().filter(NPS, Resposta.grupo == "detrator"), func.count().filter(CSAT),
        func.count().filter(CSAT, Resposta.grupo == "satisfeito"),
        func.coalesce(func.sum(Resposta.nota).filter(CSAT), 0),
        func.count().filter(func.cardinality(Resposta.temas_reclamacao) > 0), func.max(Resposta.data_resposta),
    ).select_from(Resposta)).where(*com_valor).group_by(chave)).all()
    sq = (_com_empresa(select(chave.label("chave"), func.unnest(Resposta.temas).label("tema")).select_from(Resposta))
          .where(*com_valor).subquery())
    temas: dict = defaultdict(list)
    for k, tema, n in s.execute(select(sq.c.chave, sq.c.tema, func.count()).group_by(sq.c.chave, sq.c.tema)):
        if tema in temas_mod.ROTULOS:
            temas[k].append((tema, n))
    itens = []
    for k, valor, total, pr, ne, de, csat_total, satisfeitos, soma, reclamacoes, ultima in linhas:
        principais = sorted(temas[k], key=lambda x: (-x[1], temas_mod.CHAVES.index(x[0])))[:2]
        itens.append({"valor": valor, "respostas": total, "nps": ind.bloco_nps(pr, ne, de),
                      "csat": bloco_csat(satisfeitos, csat_total, soma), "reclamacoes": reclamacoes,
                      "temas": [{"tema": t, "rotulo": temas_mod.ROTULOS[t], "mencoes": n} for t, n in principais],
                      "ultima_resposta": ultima, "amostra_pequena": total < AMOSTRA_PEQUENA})
    return itens, sem_valor


def _ordenar_entregas(itens: list[dict], ordem: str | None) -> list[dict]:
    def nome(x):
        return chave_nome(x["valor"])

    chaves = {
        "respostas": lambda x: (-x["respostas"], nome(x)),
        "nps": lambda x: (x["nps"]["valor"] is None, x["nps"]["valor"] or 0, nome(x)),
        "csat": lambda x: (x["csat"]["percentual"] is None, x["csat"]["percentual"] or 0, nome(x)),
        "reclamacoes": lambda x: (-x["reclamacoes"], nome(x)),
        "valor": nome,
    }
    return sorted(itens, key=chaves[ordem or "respostas"])


def entregas(ctx: Contexto, f, pg: Pagina) -> dict:
    _validar_periodo(f.de, f.ate)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        itens, sem_valor = _dados_entregas(s, ctx, f)
    itens = _ordenar_entregas(itens, f.ordem)
    return {"dimensao": f.dimensao, "sem_valor": sem_valor,
            **pg.resultado(itens[pg.offset:pg.offset + pg.por_pagina], len(itens))}


def entregas_csv(ctx: Contexto, f) -> str:
    _validar_periodo(f.de, f.ate)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        itens, _ = _dados_entregas(s, ctx, f)
    cabecalho = [ROTULOS_DIMENSAO[f.dimensao], "Respostas", "NPS", "Promotores", "Neutros", "Detratores", "CSAT (%)",
                 "CSAT média", "Reclamações", "Última resposta"]
    linhas = [[x["valor"], num(x["respostas"]), num(x["nps"]["valor"]), num(x["nps"]["promotores"]),
               num(x["nps"]["neutros"]), num(x["nps"]["detratores"]), num(x["csat"]["percentual"]),
               num(x["csat"]["media"]), num(x["reclamacoes"]), data_br(x["ultima_resposta"])]
              for x in _ordenar_entregas(itens, f.ordem)]
    return gerar_csv(cabecalho, linhas)


# ---- responsáveis (carteira das empresas) -----------------------------------------

def _carteiras(s: Session, ctx: Contexto, f) -> list[dict]:
    hoje = relogio.hoje()
    p = Periodo(ctx.conta_id, f.de, f.ate)
    lista = carregar_empresas(s, ctx.conta_id, _filtro_empresas(f), hoje)
    nps, acoes = _nps_empresas(s, p), _acoes_empresas(s, ctx.conta_id, hoje)
    por_resp: dict = {}
    for e in lista:
        r = por_resp.setdefault(e.responsavel_id, {
            "responsavel": ({**e.responsavel, "foto_url": e.foto_url} if e.responsavel else None), "empresas": 0,
            "empresas_com_respostas": 0, "blocos": [], "receita": Decimal(0), "receita_em_risco": Decimal(0),
            "acoes_abertas": 0, "acoes_vencidas": 0})
        pr, ne, de, _ = nps.get(e.id, (0, 0, 0, 0))
        r["empresas"] += 1
        r["empresas_com_respostas"] += 1 if pr + ne + de else 0
        r["blocos"].append((pr, ne, de))
        r["receita"] += e.valor_mensal or 0
        r["receita_em_risco"] += (e.valor_mensal or 0) if de else 0
        abertas, vencidas = acoes.get(e.id, (0, 0))
        r["acoes_abertas"] += abertas
        r["acoes_vencidas"] += vencidas
    itens = []
    for r in por_resp.values():
        r["nps"] = _somar(r.pop("blocos"))
        itens.append(r)
    return sorted(itens, key=lambda x: (*_ordem_nps(x, x["responsavel"] is None),
                                        chave_nome((x["responsavel"] or {}).get("nome"))))


def responsaveis(ctx: Contexto, f) -> dict:
    _validar_periodo(f.de, f.ate)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        itens = _carteiras(s, ctx, f)
    return {"itens": [{"responsavel": x["responsavel"], "empresas": x["empresas"],
                       "empresas_com_respostas": x["empresas_com_respostas"], "nps": x["nps"], "receita": x["receita"],
                       "receita_em_risco": x["receita_em_risco"], "acoes_abertas": x["acoes_abertas"],
                       "acoes_vencidas": x["acoes_vencidas"]} for x in itens]}


def responsaveis_csv(ctx: Contexto, f) -> str:
    _validar_periodo(f.de, f.ate)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        itens = _carteiras(s, ctx, f)
    cabecalho = ["Responsável", "Empresas", "Com respostas", "NPS", "Promotores", "Neutros", "Detratores", "Respostas",
                 "Receita", "Receita em risco", "Ações abertas", "Ações vencidas"]
    linhas = [[(x["responsavel"] or {}).get("nome") or "Sem responsável", num(x["empresas"]),
               num(x["empresas_com_respostas"]), num(x["nps"]["valor"]), num(x["nps"]["promotores"]),
               num(x["nps"]["neutros"]), num(x["nps"]["detratores"]), num(x["nps"]["total"]), num(x["receita"]),
               num(x["receita_em_risco"]), num(x["acoes_abertas"]), num(x["acoes_vencidas"])] for x in itens]
    return gerar_csv(cabecalho, linhas)


def empresas_do_responsavel(ctx: Contexto, responsavel_id: int, f) -> list[dict]:
    """Empresas da carteira (0 = sem responsável) com o NPS do período, a nota média e as ações abertas."""
    _validar_periodo(f.de, f.ate)
    hoje = relogio.hoje()
    p = Periodo(ctx.conta_id, f.de, f.ate)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        if responsavel_id and s.get(Responsavel, responsavel_id) is None:
            raise nao_encontrado("Responsável não encontrado.")
        filtro = _filtro_empresas(f)
        filtro.responsavel_id = responsavel_id
        lista: list[EmpresaRel] = carregar_empresas(s, ctx.conta_id, filtro, hoje)
        nps, ultimas = _nps_empresas(s, p), _ultimas_respostas(s, ctx.conta_id)
        acoes = _acoes_empresas(s, ctx.conta_id, hoje)
    itens = []
    for e in lista:
        pr, ne, de, soma = nps.get(e.id, (0, 0, 0, 0))
        itens.append({"empresa": {"id": e.id, "nome": e.nome}, "nps": ind.bloco_nps(pr, ne, de),
                      "nota_media": ind.media(soma, pr + ne + de, 1), "valor_mensal": e.valor_mensal,
                      "ultima_resposta": _ultima_json(ultimas.get(e.id)), "acoes_abertas": acoes.get(e.id, (0, 0))[0]})
    return sorted(itens, key=lambda x: (*_ordem_nps(x, False), chave_nome(x["empresa"]["nome"])))


# ---- operação ---------------------------------------------------------------------

def _sem_resposta(ctx: Contexto, filtro: Filtro) -> list:
    """Contatos ativos cujo último convite que saiu (`contatos.ultimo_envio`) não teve resposta depois dele.
    Condições sobre Contato (com a empresa juntada)."""
    respondeu = (select(Resposta.id).where(Resposta.conta_id == ctx.conta_id, Resposta.contato_id == Contato.id,
                                           Resposta.arquivada.is_(False),
                                           Resposta.data_resposta >= Contato.ultimo_envio).exists())
    return [Contato.conta_id == ctx.conta_id, Contato.ativo.is_(True), Contato.ultimo_envio.is_not(None),
            not_(respondeu), *filtro.empresa(Contato.empresa_id)]


def _dias(ultimo_envio, hoje: date) -> int:
    return (hoje - ultimo_envio.astimezone(relogio.FUSO).date()).days


def numeros_operacao(s: Session, ctx: Contexto, f, hoje: date) -> dict:
    """Os números da aba Operação (sem a lista de contatos sem resposta). Também usado pelo parecer da IA."""
    filtro = _filtro_respostas(ctx, f)
    taxa = _taxa_resposta(s, filtro)
    canais = []
    for canal in ("email", "whatsapp"):
        t = _taxa_resposta(s, filtro, canal)
        canais.append({"canal": canal, "convidados": t["convidados"], "responderam": t["responderam"],
                       "percentual": t["percentual"]})
    com_empresa = [Acao.conta_id == ctx.conta_id, *filtro.empresa(Acao.empresa_id)]
    fim_do_prazo = func.timezone(FUSO_NOME, cast(Acao.prazo + 1, DateTime))
    concluidas, tempo, com_prazo, no_prazo = s.execute(
        select(func.count(), func.avg(func.extract("epoch", Acao.concluida_em - Acao.criada_em)),
               func.count().filter(Acao.prazo.is_not(None)),
               func.count().filter(Acao.prazo.is_not(None), Acao.concluida_em < fim_do_prazo))
        .select_from(Acao).outerjoin(Empresa, Empresa.id == Acao.empresa_id)
        .where(*com_empresa, Acao.situacao == "concluida", Acao.concluida_em.is_not(None),
               *entre_datas(Acao.concluida_em, f.de, f.ate))).one()
    abertas, vencidas = s.execute(
        select(func.count(), func.count().filter(Acao.prazo < hoje)).select_from(Acao)
        .outerjoin(Empresa, Empresa.id == Acao.empresa_id).where(*com_empresa, aberta())).one()
    intervalo = config_envios(s, criar=False).intervalo_dias
    data_envio = cast(func.timezone(FUSO_NOME, Contato.ultimo_envio), Date)
    limite = hoje - timedelta(days=intervalo)
    total, atrasados = s.execute(select(func.count(), func.count().filter(data_envio < limite))
                                 .select_from(Contato).outerjoin(Empresa, Empresa.id == Contato.empresa_id)
                                 .where(*_sem_resposta(ctx, filtro))).one()
    return {
        "taxa_resposta": taxa,
        "canais": canais,
        "acoes": {"concluidas": concluidas,
                  "tempo_medio_dias": None if tempo is None else float(ind.arredondar(Decimal(tempo) / 86400, 1)),
                  "no_prazo_percentual": ind.percentual(no_prazo, com_prazo), "abertas": abertas,
                  "vencidas": vencidas},
        "sem_resposta": {"total": total, "atrasados": atrasados, "intervalo_dias": intervalo},
    }


def operacao(ctx: Contexto, f) -> dict:
    _validar_periodo(f.de, f.ate)
    hoje = relogio.hoje()
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        numeros = numeros_operacao(s, ctx, f, hoje)
        linhas = s.execute(select(Contato.id, Contato.nome, Contato.email, Contato.empresa_id,
                                  Empresa.nome.label("empresa_nome"), Contato.ultimo_envio)
                           .select_from(Contato).outerjoin(Empresa, Empresa.id == Contato.empresa_id)
                           .where(*_sem_resposta(ctx, _filtro_respostas(ctx, f)))
                           .order_by(Contato.ultimo_envio, Contato.id).limit(MAX_SEM_RESPOSTA)).all()
    intervalo = numeros["sem_resposta"]["intervalo_dias"]
    numeros["sem_resposta"]["itens"] = [
        {"contato": {"id": x.id, "nome": x.nome, "email": x.email},
         "empresa": {"id": x.empresa_id, "nome": x.empresa_nome} if x.empresa_id else None,
         "ultimo_envio": x.ultimo_envio, "dias": _dias(x.ultimo_envio, hoje),
         "atrasado": _dias(x.ultimo_envio, hoje) > intervalo} for x in linhas]
    return numeros


def sem_resposta_csv(ctx: Contexto, f) -> str:
    _validar_periodo(f.de, f.ate)
    hoje = relogio.hoje()
    filtro = _filtro_respostas(ctx, f)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        intervalo = config_envios(s, criar=False).intervalo_dias
        conds = _sem_resposta(ctx, filtro)
        linhas = s.execute(select(Contato.nome, Contato.email, Empresa.nome.label("empresa_nome"), Contato.ultimo_envio)
                           .select_from(Contato).outerjoin(Empresa, Empresa.id == Contato.empresa_id).where(*conds)
                           .order_by(Contato.ultimo_envio, Contato.id)).all()
    return gerar_csv(["Contato", "E-mail", "Empresa", "Último envio", "Dias", "Atrasado"],
                     [[x.nome, x.email or "", x.empresa_nome or "", data_br(x.ultimo_envio),
                       num(_dias(x.ultimo_envio, hoje)), sim_nao(_dias(x.ultimo_envio, hoje) > intervalo)]
                      for x in linhas])


# ---- histórico de uma empresa -------------------------------------------------------

def _empresa_ou_404(s: Session, empresa_id: int):
    g, sg, rp = aliased(Grupo), aliased(Segmento), aliased(Responsavel)
    x = s.execute(select(Empresa, g.nome.label("grupo_nome"), sg.nome.label("segmento_nome"),
                         rp.nome.label("responsavel_nome"))
                  .outerjoin(g, g.id == Empresa.grupo_id).outerjoin(sg, sg.id == Empresa.segmento_id)
                  .outerjoin(rp, rp.id == Empresa.responsavel_id).where(Empresa.id == empresa_id)).one_or_none()
    if x is None:
        raise nao_encontrado("Empresa não encontrada.")
    return x


def _linha_do_tempo(conta_id: int, empresa_id: int, de: date | None, ate: date | None):
    acao = (select(Acao.id, Acao.situacao).where(Acao.conta_id == Resposta.conta_id, Acao.resposta_id == Resposta.id)
            .order_by((Acao.origem != "automatica"), Acao.criada_em.desc(), Acao.id.desc())
            .limit(1).correlate(Resposta).lateral("acao"))
    return (select(Resposta, Contato.nome.label("contato_nome"), Cargo.nome.label("cargo"),
                   PerfilContato.nome.label("perfil"), acao.c.id.label("acao_id"),
                   acao.c.situacao.label("acao_situacao"))
            .select_from(Resposta)
            .outerjoin(Contato, Contato.id == Resposta.contato_id)
            .outerjoin(Cargo, Cargo.id == Contato.cargo_id)
            .outerjoin(PerfilContato, PerfilContato.id == Contato.perfil_id)
            .outerjoin(acao, true())
            .where(Resposta.conta_id == conta_id, Resposta.empresa_id == empresa_id, Resposta.arquivada.is_(False),
                   *entre_datas(Resposta.data_resposta, de, ate))
            .order_by(Resposta.data_resposta.desc(), Resposta.id.desc()))


def historico(ctx: Contexto, empresa_id: int, de: date | None, ate: date | None) -> dict:
    _validar_periodo(de, ate)
    hoje = relogio.hoje()
    p = Periodo(ctx.conta_id, de, ate)
    mes = func.to_char(func.timezone(FUSO_NOME, Resposta.data_resposta), "YYYY-MM")
    da_empresa = Resposta.empresa_id == empresa_id
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        x = _empresa_ou_404(s, empresa_id)
        e: Empresa = x.Empresa
        pr, ne, de_, csat_total, satisfeitos, soma, total = s.execute(select(
            func.count().filter(NPS, Resposta.grupo == "promotor"),
            func.count().filter(NPS, Resposta.grupo == "neutro"),
            func.count().filter(NPS, Resposta.grupo == "detrator"), func.count().filter(CSAT),
            func.count().filter(CSAT, Resposta.grupo == "satisfeito"),
            func.coalesce(func.sum(Resposta.nota).filter(CSAT), 0), func.count(),
        ).where(*p.respostas(da_empresa))).one()
        respondeu = (select(Resposta.contato_id).where(*p.respostas(NPS, Resposta.contato_id.is_not(None)))
                     .distinct().subquery())
        ativos, responderam = s.execute(
            select(func.count(), func.count(respondeu.c.contato_id)).select_from(Contato)
            .outerjoin(respondeu, respondeu.c.contato_id == Contato.id)
            .where(Contato.conta_id == ctx.conta_id, Contato.empresa_id == empresa_id, Contato.ativo.is_(True))).one()
        abertas, vencidas, concluidas = s.execute(select(
            func.count().filter(aberta()), func.count().filter(aberta(), Acao.prazo < hoje),
            func.count().filter(Acao.situacao == "concluida", *entre_datas(Acao.concluida_em, de, ate)),
        ).where(Acao.conta_id == ctx.conta_id, Acao.empresa_id == empresa_id)).one()
        meses = s.execute(select(mes, func.count().filter(Resposta.grupo == "promotor"),
                                 func.count().filter(Resposta.grupo == "neutro"),
                                 func.count().filter(Resposta.grupo == "detrator"))
                          .where(*p.respostas(NPS, da_empresa)).group_by(mes).order_by(mes.desc())
                          .limit(MAX_MESES)).all()
        linhas = s.execute(_linha_do_tempo(ctx.conta_id, empresa_id, de, ate).limit(MAX_LINHA_DO_TEMPO)).all()
    return {
        "empresa": {"id": e.id, "nome": e.nome, "ativa": e.ativa,
                    "grupo": {"id": e.grupo_id, "nome": x.grupo_nome} if e.grupo_id else None,
                    "segmento": {"id": e.segmento_id, "nome": x.segmento_nome} if e.segmento_id else None,
                    "responsavel": {"id": e.responsavel_id, "nome": x.responsavel_nome} if e.responsavel_id else None,
                    "valor_mensal": e.valor_mensal, "cliente_desde": e.cliente_desde},
        "nps": ind.bloco_nps(pr, ne, de_),
        "csat": bloco_csat(satisfeitos, csat_total, soma) if csat_total else None,
        "cobertura": _cobertura_json(ativos, responderam),
        "acoes": {"abertas": abertas, "vencidas": vencidas, "concluidas": concluidas},
        "evolucao": [{"mes": m, "nps": ind.nps(a, c, a + b + c), "total": a + b + c} for m, a, b, c in reversed(meses)],
        "linha_do_tempo": [_item_linha(y) for y in linhas],
        "total": total,
    }


def _item_linha(y) -> dict:
    r: Resposta = y.Resposta
    return {
        "resposta_id": r.id, "data": r.data_resposta, "nota": r.nota, "tipo_nota": r.tipo_nota, "grupo": r.grupo,
        "contato": ({"id": r.contato_id, "nome": y.contato_nome, "cargo": y.cargo, "perfil": y.perfil}
                    if r.contato_id else None),
        "canal": r.canal, "origem": r.origem, "comentario": r.comentario, "temas": list(r.temas or []),
        "ia": ({"sentimento": r.ia_sentimento, "resumo": r.ia_resumo} if r.ia_situacao == "analisada" else None),
        "acao": {"id": y.acao_id, "situacao": y.acao_situacao} if y.acao_id else None,
    }


def historico_csv(ctx: Contexto, empresa_id: int, de: date | None, ate: date | None) -> str:
    _validar_periodo(de, ate)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        _empresa_ou_404(s, empresa_id)
        linhas = s.execute(_linha_do_tempo(ctx.conta_id, empresa_id, de, ate)).all()
    cabecalho = ["Data", "Nota", "Tipo", "Categoria", "Contato", "Cargo", "Canal", "Comentário", "Temas", "Sentimento",
                 "Resumo da IA"]
    saida = []
    for y in linhas:
        r: Resposta = y.Resposta
        analisada = r.ia_situacao == "analisada"
        saida.append([
            r.data_resposta.astimezone(relogio.FUSO).strftime("%d/%m/%Y %H:%M"), num(r.nota),
            ind.ROTULOS_TIPO.get(r.tipo_nota, ""), ind.ROTULOS_GRUPO.get(r.grupo, ""), y.contato_nome or "",
            y.cargo or "", ROTULOS_CANAL.get(r.canal, r.canal), r.comentario or "",
            ", ".join(temas_mod.ROTULOS[t] for t in temas_mod.ordenar(r.temas)),
            ROTULOS_SENTIMENTO.get(r.ia_sentimento, "") if analisada else "",
            (r.ia_resumo or "") if analisada else "",
        ])
    return gerar_csv(cabecalho, saida)


def nome_csv(prefixo: str) -> str:
    return f"{prefixo}-{relogio.hoje().isoformat()}.csv"
