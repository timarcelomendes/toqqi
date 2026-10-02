"""Painel (visão geral): "como estamos e o que preciso tratar hoje". Tudo agregado no banco.

Regras comuns: só respostas não arquivadas; a data é `data_resposta`; período inclusive em dias de São Paulo
(sem `de`/`ate` = todo o histórico); `grupo_id` = grupo da empresa da resposta; `so_ativos` tira as respostas de
empresas inativas (respostas sem empresa sempre contam). O bloco "Precisa de atenção" conta as ações abertas
sem o período (só com os filtros de empresa).

Desempenho: além do RLS, as consultas filtram `conta_id` de forma explícita (a política tem `OR app_sistema()`,
que impede o planejador de usar os índices `(conta_id, ...)`), e o JIT do PostgreSQL fica desligado na transação
do painel (compilar as consultas custava mais que executá-las).
"""
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import String, and_, any_, case, cast, func, or_, select
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.core.filtros import entre_datas, inicio_do_dia
from toqqi.core.relogio import FUSO_NOME
from toqqi.modelos import (
    Acao,
    ConfigEnvios,
    Contato,
    Convite,
    Empresa,
    Envio,
    PerfilContato,
    Responsavel,
    Resposta,
)
from toqqi.modulos.acoes.regras import aberta, ordem_urgencia
from toqqi.modulos.empresas.servico import ref
from toqqi.modulos.painel.palavras import contar
from toqqi.modulos.relatorios import picos as picos_mod
from toqqi.modulos.respostas import indicadores as ind
from toqqi.modulos.respostas.servico import gerar_csv
from toqqi.modulos.respostas.temas import CHAVES, ROTULOS

# convite que saiu: e-mail enviado (ou WhatsApp enviado/entregue/lido) ou link de WhatsApp aberto
SAIU_CONVITE = ("enviado", "entregue", "lido", "aberto_no_whatsapp")
AMOSTRA_PEQUENA = 20
MAX_MOVIMENTACAO = 20
MAX_EMPRESAS_ATENCAO = 5
MAX_TEMAS = 5
MAX_COMENTARIOS = 6
MESES_SEM_PERIODO = 6
MESES_COM_PERIODO = 24
MIN_RESPOSTAS_EMPRESA = 3
MAX_EMPRESAS_RANKING = 6
MAX_TEXTOS_PALAVRAS = 5000
MESES_EVOLUCAO_12M = 12
SENTIMENTOS = ("negativo", "misto", "neutro", "positivo")


@dataclass
class Filtro:
    conta_id: int
    de: date | None
    ate: date | None
    grupo_id: int | None
    so_ativos: bool

    @property
    def com_periodo(self) -> bool:
        return self.de is not None or self.ate is not None

    def empresa(self, coluna_empresa_id) -> list:
        """Filtros de empresa (pedem Empresa juntada pela `coluna_empresa_id`)."""
        conds = []
        if self.grupo_id is not None:
            conds.append(Empresa.grupo_id == self.grupo_id)
        if self.so_ativos:
            conds.append(or_(coluna_empresa_id.is_(None), Empresa.ativa.is_(True)))
        return conds

    def respostas(self, de: date | None = None, ate: date | None = None, periodo: bool = True) -> list:
        """Respostas que contam (pedem Empresa juntada pela empresa da resposta)."""
        conds = [Resposta.conta_id == self.conta_id, Resposta.arquivada.is_(False), *self.empresa(Resposta.empresa_id)]
        if periodo:
            conds += entre_datas(Resposta.data_resposta, de or self.de, ate or self.ate)
        return conds


def _com_empresa(consulta):
    return consulta.outerjoin(Empresa, Empresa.id == Resposta.empresa_id)


NPS = Resposta.tipo_nota == "nps"
CSAT = Resposta.tipo_nota == "csat"
COM_NOTA = Resposta.tipo_nota.in_(("nps", "csat"))


def _grupos(condicao=None) -> list:
    extra = [condicao] if condicao is not None else []
    return [func.count().filter(NPS, Resposta.grupo == g, *extra) for g in ("promotor", "neutro", "detrator")]


# ---- blocos -----------------------------------------------------------------

def _contagens_tom() -> list:
    """Colunas do tom (respostas NPS e CSAT): total, com comentário, analisadas, pendentes e uma por sentimento."""
    texto = Resposta.comentario_cliente != ""
    analisada = and_(texto, Resposta.ia_situacao == "analisada", Resposta.ia_sentimento.in_(SENTIMENTOS))
    return [func.count().filter(COM_NOTA), func.count().filter(COM_NOTA, texto),
            func.count().filter(COM_NOTA, analisada),
            func.count().filter(COM_NOTA, texto, Resposta.ia_situacao == "pendente"),
            *[func.count().filter(COM_NOTA, analisada, Resposta.ia_sentimento == x) for x in SENTIMENTOS]]


def _nps_csat(s: Session, conds: list) -> tuple[dict, dict, tuple]:
    """NPS, CSAT e as contagens do tom do período numa consulta só (as junções com contato e perfil são 1:1)."""
    decisor = cast(PerfilContato.nome, String).ilike("decisor")
    consulta = select(
        *_grupos(), *_grupos(decisor),
        func.count().filter(CSAT), func.count().filter(CSAT, Resposta.grupo == "satisfeito"),
        func.coalesce(func.sum(Resposta.nota).filter(CSAT), 0),
        *_contagens_tom(),
    ).select_from(Resposta).outerjoin(Contato, Contato.id == Resposta.contato_id) \
        .outerjoin(PerfilContato, PerfilContato.id == Contato.perfil_id)
    p, n, d, dp, dn, dd, csat_total, satisfeitos, soma, *tom = s.execute(_com_empresa(consulta).where(*conds)).one()
    nps = ind.bloco_nps(p, n, d)
    nps["pct"] = {"promotores": ind.percentual(p, nps["total"], 1) or 0.0,
                  "neutros": ind.percentual(n, nps["total"], 1) or 0.0,
                  "detratores": ind.percentual(d, nps["total"], 1) or 0.0}
    decisores = dp + dn + dd
    nps["decisores"] = {"valor": ind.nps(dp, dd, decisores), "total": decisores}
    csat = {"percentual": ind.percentual(satisfeitos, csat_total), "media": ind.media(soma, csat_total),
            "total": csat_total, "satisfeitos": satisfeitos}
    return nps, csat, tuple(tom)


def _nps_de(s: Session, conds: list) -> int | None:
    p, n, d = s.execute(_com_empresa(select(*_grupos()).select_from(Resposta)).where(*conds)).one()
    return ind.nps(p, d, p + n + d)


def _taxa_resposta(s: Session, f: Filtro, canal: str | None = None) -> dict:
    """Convidados = contatos ativos com convite que saiu no período; responderam = os que responderam no período.
    `canal` (relatório de operação) conta só os convites daquele canal."""
    saiu = (select(Envio.id).where(Envio.conta_id == f.conta_id, Envio.convite_id == Convite.id,
                                   Envio.tipo == "convite", Envio.situacao.in_(SAIU_CONVITE)).exists())
    do_canal = [Convite.canal == canal] if canal else []
    convidados = (select(Convite.contato_id).distinct()
                  .join(Contato, Contato.id == Convite.contato_id)
                  .outerjoin(Empresa, Empresa.id == Contato.empresa_id)
                  .where(Convite.conta_id == f.conta_id, Contato.ativo.is_(True), *do_canal,
                         *entre_datas(Convite.criado_em, f.de, f.ate), saiu, *f.empresa(Contato.empresa_id))
                  .subquery())
    responderam_ = (select(Resposta.contato_id).distinct()
                    .where(Resposta.conta_id == f.conta_id, Resposta.contato_id.is_not(None),
                           Resposta.arquivada.is_(False), *entre_datas(Resposta.data_resposta, f.de, f.ate))
                    .subquery())
    total, responderam = s.execute(
        select(func.count(), func.count(responderam_.c.contato_id))
        .select_from(convidados.outerjoin(responderam_, responderam_.c.contato_id == convidados.c.contato_id))).one()
    pct = ind.percentual(responderam, total)
    return {"percentual": pct, "responderam": responderam, "convidados": total,
            "amostra_pequena": pct is not None and pct < AMOSTRA_PEQUENA}


def _movimentacao(s: Session, f: Filtro) -> dict:
    """Por contato: a última resposta NPS (no período, se houver) contra a anterior a ela (qualquer data)."""
    ordem = (Resposta.data_resposta, Resposta.id)
    todas = (select(
        Resposta.id, Resposta.contato_id, Resposta.empresa_id, Resposta.nota, Resposta.data_resposta,
        func.lag(Resposta.nota).over(partition_by=Resposta.contato_id, order_by=ordem).label("nota_anterior"),
        func.lag(Resposta.data_resposta).over(partition_by=Resposta.contato_id, order_by=ordem)
        .label("data_anterior"),
    ).where(Resposta.conta_id == f.conta_id, Resposta.arquivada.is_(False), NPS, Resposta.contato_id.is_not(None))
        .subquery("todas"))
    ultimas = (select(
        todas,
        func.row_number().over(partition_by=todas.c.contato_id,
                               order_by=(todas.c.data_resposta.desc(), todas.c.id.desc())).label("n"),
    ).select_from(todas).outerjoin(Empresa, Empresa.id == todas.c.empresa_id)
        .where(*entre_datas(todas.c.data_resposta, f.de, f.ate), *f.empresa(todas.c.empresa_id))
        .subquery("ultimas"))
    tipo = case((and_(ultimas.c.nota_anterior <= 6, ultimas.c.nota >= 9), "resgatado"),
                (and_(ultimas.c.nota_anterior >= 9, ultimas.c.nota <= 8), "deixou_de_ser_promotor"))
    mudancas = (select(ultimas, tipo.label("tipo"))
                .where(ultimas.c.n == 1, ultimas.c.nota_anterior.is_not(None)).subquery("mudancas"))
    # uma consulta só: as mudanças (no máximo uma por contato), mais recentes primeiro; contagem aqui
    linhas = s.execute(
        select(mudancas.c.id, mudancas.c.tipo, mudancas.c.contato_id, mudancas.c.empresa_id, mudancas.c.nota,
               mudancas.c.nota_anterior, mudancas.c.data_resposta, mudancas.c.data_anterior,
               Contato.nome.label("contato_nome"), Empresa.nome.label("empresa_nome"))
        .select_from(mudancas)
        .join(Contato, Contato.id == mudancas.c.contato_id)
        .outerjoin(Empresa, Empresa.id == mudancas.c.empresa_id)
        .where(mudancas.c.tipo.is_not(None)).order_by(mudancas.c.data_resposta.desc(), mudancas.c.id.desc())
    ).all()
    return {"resgatados": sum(1 for x in linhas if x.tipo == "resgatado"),
            "deixaram_de_ser_promotores": sum(1 for x in linhas if x.tipo == "deixou_de_ser_promotor"), "itens": [
                {"tipo": x.tipo, "contato": {"id": x.contato_id, "nome": x.contato_nome},
                 "empresa": ref(x.empresa_id, x.empresa_nome), "nota_anterior": x.nota_anterior, "nota_atual": x.nota,
                 "data_anterior": x.data_anterior, "data_atual": x.data_resposta}
                for x in linhas[:MAX_MOVIMENTACAO]]}


def _atencao(s: Session, f: Filtro, conds: list, hoje: date) -> dict:
    conds_acao = [Acao.conta_id == f.conta_id, aberta(), *f.empresa(Acao.empresa_id)]
    vencida = Acao.prazo < hoje
    abertas, vencidas = s.execute(
        select(func.count(), func.count().filter(vencida)).select_from(Acao)
        .outerjoin(Empresa, Empresa.id == Acao.empresa_id).where(*conds_acao)).one()
    por_empresa = s.execute(
        select(Acao.empresa_id, Empresa.nome, Empresa.responsavel_id, Responsavel.nome.label("responsavel_nome"),
               func.count().label("abertas"), func.count().filter(vencida).label("vencidas"),
               func.min(Acao.criada_em).label("desde"))
        .select_from(Acao).join(Empresa, Empresa.id == Acao.empresa_id)
        .outerjoin(Responsavel, Responsavel.id == Empresa.responsavel_id)
        .where(*conds_acao)
        .group_by(Acao.empresa_id, Empresa.nome, Empresa.responsavel_id, Responsavel.nome)
        .order_by((func.count().filter(vencida) > 0).desc(), func.min(Acao.criada_em), Acao.empresa_id)
        .limit(MAX_EMPRESAS_ATENCAO)).all()
    ids = [x.empresa_id for x in por_empresa]
    nps_empresa, comentario, urgente = {}, {}, {}
    if ids:
        for empresa_id, p, n, d in s.execute(
                _com_empresa(select(Resposta.empresa_id, *_grupos()).select_from(Resposta))
                .where(*conds, Resposta.empresa_id.in_(ids)).group_by(Resposta.empresa_id)):
            nps_empresa[empresa_id] = ind.nps(p, d, p + n + d)
        comentario = dict(s.execute(  # só texto escrito pelo cliente (não o resumo das outras respostas)
            select(Resposta.empresa_id, Resposta.comentario_cliente).distinct(Resposta.empresa_id)
            .where(Resposta.conta_id == f.conta_id, Resposta.empresa_id.in_(ids), Resposta.arquivada.is_(False), NPS,
                   Resposta.grupo == "detrator", Resposta.comentario_cliente != "")
            .order_by(Resposta.empresa_id, Resposta.data_resposta.desc(), Resposta.id.desc())).all())
        urgente = dict(s.execute(
            select(Acao.empresa_id, Acao.id).distinct(Acao.empresa_id)
            .where(Acao.conta_id == f.conta_id, aberta(), Acao.empresa_id.in_(ids))
            .order_by(Acao.empresa_id, *ordem_urgencia(hoje))).all())
    detratores = (_com_empresa(select(Resposta.empresa_id).select_from(Resposta))
                  .where(*conds, NPS, Resposta.grupo == "detrator", Resposta.empresa_id.is_not(None))
                  .distinct().subquery())
    # carteira: soma do valor mensal das empresas no filtro (grupo; só ativas se pedido), sem olhar respostas;
    # subconsulta escalar na mesma consulta da receita em risco
    carteira_ = (select(func.sum(Empresa.valor_mensal))
                 .where(Empresa.conta_id == f.conta_id, *f.empresa(Empresa.id)).scalar_subquery())
    valor, empresas, sem_valor, carteira = s.execute(
        select(func.coalesce(func.sum(Empresa.valor_mensal), 0), func.count(),
               func.count().filter(Empresa.valor_mensal.is_(None)), carteira_)
        .select_from(Empresa).join(detratores, detratores.c.empresa_id == Empresa.id)).one()
    return {
        "acoes_abertas": abertas, "acoes_vencidas": vencidas, "tudo_em_dia": abertas == 0,
        "empresas": [
            {"empresa": {"id": x.empresa_id, "nome": x.nome}, "nps": nps_empresa.get(x.empresa_id),
             "acoes_abertas": x.abertas, "acoes_vencidas": x.vencidas, "desde": x.desde,
             "responsavel": ref(x.responsavel_id, x.responsavel_nome),
             "ultimo_comentario_detrator": comentario.get(x.empresa_id), "acao_id": urgente.get(x.empresa_id)}
            for x in por_empresa],
        "receita_em_risco": {"valor": valor, "empresas": empresas, "sem_valor": sem_valor, "carteira": carteira},
    }


def _mencoes(s: Session, conds: list):
    """(tema, menções, soma das notas, reclamações) das respostas NPS das condições."""
    sq = (_com_empresa(select(func.unnest(Resposta.temas).label("tema"), Resposta.nota.label("nota"),
                              Resposta.temas_reclamacao.label("reclamacao")).select_from(Resposta))
          .where(*conds, NPS).subquery())
    return s.execute(select(sq.c.tema, func.count(), func.sum(sq.c.nota),
                            func.count().filter(sq.c.tema == any_(sq.c.reclamacao))).group_by(sq.c.tema)).all()


def _temas(s: Session, conds: list, conds_anterior: list | None = None) -> list[dict]:
    """Só respostas NPS: menções por tema, nota média e reclamações; os mais citados (empate: ordem da tabela).
    `variacao` = menções no período − menções no período anterior de mesmo tamanho (null sem `de`/`ate`)."""
    contagem = {t: (n, soma, reclamacoes) for t, n, soma, reclamacoes in _mencoes(s, conds)}
    citados = sorted((t for t in CHAVES if t in contagem), key=lambda t: (-contagem[t][0], CHAVES.index(t)))[:MAX_TEMAS]
    anterior = None
    if conds_anterior is not None and citados:
        anterior = {t: n for t, n, _, _ in _mencoes(s, conds_anterior)}
    return [{"chave": t, "rotulo": ROTULOS[t], "mencoes": contagem[t][0],
             "nota_media": ind.media(contagem[t][1], contagem[t][0], 1), "reclamacoes": contagem[t][2],
             "variacao": None if anterior is None else contagem[t][0] - anterior.get(t, 0)} for t in citados]


def _comentarios(s: Session, conds: list) -> list[dict]:
    """As mais recentes (NPS e CSAT) com texto escrito pelo cliente; mostra esse texto, não o resumo."""
    linhas = s.execute(
        _com_empresa(select(Resposta.id, Resposta.data_resposta, Resposta.nota, Resposta.tipo_nota, Resposta.grupo,
                            Resposta.comentario_cliente, Resposta.contato_id, Contato.nome.label("contato_nome"),
                            Resposta.empresa_id, Empresa.nome.label("empresa_nome"))
                     .select_from(Resposta).outerjoin(Contato, Contato.id == Resposta.contato_id))
        .where(*conds, Resposta.tipo_nota.in_(("nps", "csat")), Resposta.comentario_cliente != "")
        .order_by(Resposta.data_resposta.desc(), Resposta.id.desc()).limit(MAX_COMENTARIOS)).all()
    return [{"resposta_id": x.id, "data": x.data_resposta, "nota": x.nota, "tipo_nota": x.tipo_nota,
             "grupo": x.grupo, "comentario": x.comentario_cliente, "contato": ref(x.contato_id, x.contato_nome),
             "empresa": ref(x.empresa_id, x.empresa_nome)} for x in linhas]


def _evolucao(s: Session, f: Filtro, conds: list) -> list[dict]:
    mes = func.to_char(func.timezone(FUSO_NOME, Resposta.data_resposta), "YYYY-MM")
    limite = MESES_COM_PERIODO if f.com_periodo else MESES_SEM_PERIODO
    linhas = s.execute(_com_empresa(select(mes.label("mes"), *_grupos()).select_from(Resposta))
                       .where(*conds, NPS).group_by(mes).order_by(mes.desc()).limit(limite)).all()
    return [{"mes": m, "nps": ind.nps(p, d, p + n + d), "total": p + n + d} for m, p, n, d in reversed(linhas)]


def _mes_seguinte(d: date) -> date:
    return date(d.year + d.month // 12, d.month % 12 + 1, 1)


def _evolucao_12m(s: Session, f: Filtro, hoje: date) -> list[dict]:
    """Sempre 12 meses (São Paulo) terminando no mês de `ate` (sem `ate`: hoje, ou `de` se ele é futuro); grupo e
    só ativas valem, o período não. `no_periodo` = o mês cruza o período (sem período, nenhum)."""
    fim = f.ate or (max(hoje, f.de) if f.de else hoje)
    meses = [date(fim.year, fim.month, 1)]
    for _ in range(MESES_EVOLUCAO_12M - 1):
        anterior = meses[0] - timedelta(days=1)
        meses.insert(0, date(anterior.year, anterior.month, 1))
    mes = func.to_char(func.timezone(FUSO_NOME, Resposta.data_resposta), "YYYY-MM")
    janela = [Resposta.data_resposta >= inicio_do_dia(meses[0]),
              Resposta.data_resposta < inicio_do_dia(_mes_seguinte(meses[-1]))]
    linhas = {m: (p, n, d) for m, p, n, d in s.execute(
        _com_empresa(select(mes, *_grupos()).select_from(Resposta))
        .where(*f.respostas(periodo=False), NPS, *janela).group_by(mes))}
    itens = []
    for m in meses:
        p, n, d = linhas.get(m.strftime("%Y-%m"), (0, 0, 0))
        ultimo = _mes_seguinte(m) - timedelta(days=1)
        no_periodo = f.com_periodo and (f.de is None or ultimo >= f.de) and (f.ate is None or m <= f.ate)
        itens.append({"mes": m.strftime("%Y-%m"), "nps": ind.nps(p, d, p + n + d), "total": p + n + d,
                      "no_periodo": bool(no_periodo)})
    return itens


def _tom(s: Session, f: Filtro, contagens: tuple, anterior: tuple[date, date] | None) -> dict:
    """Tom (sentimento da IA) dos comentários do cliente nas respostas NPS e CSAT do filtro (a contagem do relatório
    de temas). `contagens` = as colunas de `_contagens_tom` do período (vêm da consulta de `_nps_csat`);
    `analisados` = analisadas pela IA com sentimento; `pendentes` = com comentário e análise na fila;
    `anterior` só com período completo."""
    total, com_comentario, analisados, pendentes, *sentimentos = contagens
    antes = None
    if anterior is not None:
        _, _, a_analisados, _, a_negativo, *_ = s.execute(_com_empresa(
            select(*_contagens_tom()).select_from(Resposta)).where(*f.respostas(*anterior))).one()
        antes = {"analisados": a_analisados, "negativo": a_negativo}
    return {"analisados": analisados, "com_comentario": com_comentario, "total_respostas": total,
            "pendentes": pendentes, **dict(zip(SENTIMENTOS, sentimentos, strict=True)), "anterior": antes}


def _empresas(s: Session, conds: list) -> dict:
    """Empresas com 3+ respostas NPS: as de menor e as de maior NPS (até 6 cada, sem repetir)."""
    linhas = s.execute(
        _com_empresa(select(Resposta.empresa_id, Empresa.nome, Empresa.valor_mensal, *_grupos()).select_from(Resposta))
        .where(*conds, NPS, Resposta.empresa_id.is_not(None))
        .group_by(Resposta.empresa_id, Empresa.nome, Empresa.valor_mensal)
        .having(func.count() >= MIN_RESPOSTAS_EMPRESA)).all()
    itens = [{"empresa": {"id": e, "nome": nome}, "nps": ind.nps(p, d, p + n + d), "respostas": p + n + d,
              "valor_mensal": valor} for e, nome, valor, p, n, d in linhas]
    # quantas vão para "menor": metade (arredondada para cima), até 6; o resto (até 6) para "maior"
    qtd_menor = min(MAX_EMPRESAS_RANKING, (len(itens) + 1) // 2)
    piores = sorted(itens, key=lambda x: (x["nps"], -x["respostas"], str(x["empresa"]["nome"]).lower()))
    menor = piores[:qtd_menor]
    usados = {x["empresa"]["id"] for x in menor}
    melhores = sorted((x for x in itens if x["empresa"]["id"] not in usados),
                      key=lambda x: (-x["nps"], -x["respostas"], str(x["empresa"]["nome"]).lower()))
    return {"menor": menor, "maior": melhores[:MAX_EMPRESAS_RANKING]}


def _palavras(s: Session, conds: list) -> list[dict]:
    """Palavras do que os clientes escreveram (até 5.000 respostas mais recentes do filtro)."""
    textos = s.scalars(_com_empresa(select(Resposta.comentario_cliente).select_from(Resposta))
                       .where(*conds, Resposta.comentario_cliente != "")
                       .order_by(Resposta.data_resposta.desc(), Resposta.id.desc())
                       .limit(MAX_TEXTOS_PALAVRAS)).all()
    return contar(textos)


def _primeiros_passos(s: Session) -> dict:
    contatos, envios_ligados, primeiro_envio, primeira_resposta = s.execute(select(
        select(Contato.id).exists(),
        select(ConfigEnvios.conta_id).where(ConfigEnvios.envios_ativos.is_(True)).exists(),
        select(Envio.id).where(Envio.tipo == "convite", Envio.situacao.in_(SAIU_CONVITE)).exists(),
        select(Resposta.id).exists(),
    )).one()
    return {"contatos": contatos, "envios_ligados": envios_ligados, "primeiro_envio": primeiro_envio,
            "primeira_resposta": primeira_resposta}


# ---- painel -----------------------------------------------------------------

def _validar_periodo(de: date | None, ate: date | None) -> None:
    if de and ate and de > ate:
        msg = "A data inicial precisa ser igual ou anterior à final."
        raise AppError(422, "dados_invalidos", "Confira o período.", {"de": msg})


def painel(ctx: Contexto, de: date | None, ate: date | None, grupo_id: int | None, so_ativos: bool) -> dict:
    _validar_periodo(de, ate)
    f = Filtro(ctx.conta_id, de, ate, grupo_id, so_ativos)
    anterior = None
    if de and ate:  # período anterior de mesmo tamanho, imediatamente antes
        dias = (ate - de).days + 1
        anterior = (de - timedelta(days=dias), de - timedelta(days=1))
    hoje = relogio.hoje()
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        conds = f.respostas()
        nps, csat, contagens_tom = _nps_csat(s, conds)
        variacao = None
        if anterior is not None and nps["valor"] is not None:
            valor_anterior = _nps_de(s, f.respostas(*anterior))
            if valor_anterior is not None:
                variacao = {"valor": nps["valor"] - valor_anterior, "anterior": valor_anterior}
        return {
            "periodo": {"de": de, "ate": ate,
                        "anterior": {"de": anterior[0], "ate": anterior[1]} if anterior else None},
            "nps": nps,
            "variacao": variacao,
            "csat": csat,
            "taxa_resposta": _taxa_resposta(s, f),
            "movimentacao": _movimentacao(s, f),
            "atencao": _atencao(s, f, conds, hoje),
            "temas": _temas(s, conds, f.respostas(*anterior) if anterior else None),
            "comentarios": _comentarios(s, conds),
            "evolucao": _evolucao(s, f, conds),
            "evolucao_12m": _evolucao_12m(s, f, hoje),
            "tom": _tom(s, f, contagens_tom, anterior),
            "empresas": _empresas(s, conds),
            "palavras": _palavras(s, conds),
            "primeiros_passos": _primeiros_passos(s),
            "picos": picos_mod.calcular(s, ctx.conta_id, hoje),
        }


def exportar_csv(ctx: Contexto, de: date | None, ate: date | None, grupo_id: int | None, so_ativos: bool) -> str:
    """O CSV de /respostas.csv com os filtros do painel."""
    _validar_periodo(de, ate)
    f = Filtro(ctx.conta_id, de, ate, grupo_id, so_ativos)
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        return gerar_csv(s, f.respostas())
