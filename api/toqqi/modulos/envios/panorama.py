"""Panorama de Envios (pedido do Marcelo em 08/10/2026: "melhore a tela enviar … assuma o papel de melhor arquiteto,
design e gestor de produtos"): o topo da tela responde se as pesquisas estão saindo sozinhas e quando é a próxima
rodada, o que sai nos próximos 14 dias e quantos responderam nos últimos 30 (docs/api-envios-panorama.md).

- `automatico`: o estado do envio automático (`desligado` = envios desligados; `parado` = falta uma pré-condição;
  `manual` = envios ligados sem o automático; `ligado`), a próxima rodada prevista (hora de São Paulo; só com o
  automático ligado e pronto), quantos ela leva (a fila que pode receber, até 100 por rodada), quantos da fila ficam
  de fora (sem canal, em descanso ou com 3 falhas seguidas), a janela, os dias úteis, o intervalo, o canal e, com a
  fila vazia, o dia em que o próximo contato entra nela.
- `agenda`: 14 dias a partir de hoje, cada um com `pesquisas` (hoje: a fila que pode receber; depois: quem tem o
  próximo envio no dia) e `lembretes` (o próximo lembrete devido no dia). O que cairia num dia sem envio (fim de
  semana com "só dias úteis", ou hoje depois da janela) vai para o próximo dia em que sai. `sai` diz se o dia tem
  envio.
- `respostas`: das pesquisas que saíram (e-mail e WhatsApp) nos últimos 30 dias, quantas foram respondidas, a taxa,
  o tempo até a metade delas responder (horas) e o mesmo nos 30 dias anteriores; por canal.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import and_, exists, func, not_, or_, select

from toqqi.core import relogio
from toqqi.core.db import em_conta, sem_jit
from toqqi.core.deps import Contexto
from toqqi.core.filtros import entre_datas
from toqqi.core.relogio import FUSO
from toqqi.modelos import ConfigEnvios, Convite, Envio
from toqqi.modulos.envios.automacao import INTERVALO_ROBO, LIMITE_ROBO, MAX_FALHAS
from toqqi.modulos.envios.configuracao import obter, pre_condicoes
from toqqi.modulos.envios.fila import SAIU, consulta_fila
from toqqi.modulos.envios.processamento import whatsapp_da_config

DIAS_AGENDA = 14
DIAS_RESPOSTAS = 30


def _sai(cfg: ConfigEnvios, d: date) -> bool:
    return not (cfg.so_dias_uteis and d.weekday() >= 5)


def proxima_rodada(cfg: ConfigEnvios, agora: datetime) -> datetime | None:
    """Quando o robô pode rodar de novo: dentro da janela (e dos dias úteis), 6 horas depois da última rodada. As
    tarefas passam a cada 30 minutos, então a rodada sai até meia hora depois disso."""
    candidato = agora.astimezone(FUSO)
    if cfg.robo_rodou_em is not None:
        candidato = max(candidato, (cfg.robo_rodou_em + INTERVALO_ROBO).astimezone(FUSO))
    for _ in range(16):
        d = candidato.date()
        if not _sai(cfg, d) or candidato.time() >= cfg.janela_fim:
            candidato = datetime.combine(d + timedelta(days=1), cfg.janela_inicio, tzinfo=FUSO)
            continue
        if candidato.time() < cfg.janela_inicio:
            return datetime.combine(d, cfg.janela_inicio, tzinfo=FUSO)
        return candidato
    return None


def _dia_de_saida(cfg: ConfigEnvios, d: date, hoje: date, agora: datetime) -> date:
    """O dia em que sai de fato o que está previsto para `d` (fim de semana e hoje depois da janela vão adiante)."""
    if d == hoje and agora.time() >= cfg.janela_fim:
        d += timedelta(days=1)
    while not _sai(cfg, d):
        d += timedelta(days=1)
    return d


def _agenda(s, cfg: ConfigEnvios, q, tem_canal, hoje: date, agora: datetime, na_fila: int) -> list[dict]:
    fim = hoje + timedelta(days=DIAS_AGENDA - 1)
    vivo = and_(q.c.ativo.is_(True), not_(q.c.saiu))
    futuros = dict(s.execute(select(q.c.proximo_envio, func.count()).where(
        vivo, tem_canal, q.c.proximo_envio > hoje, q.c.proximo_envio <= fim)
        .group_by(q.c.proximo_envio)).all())
    lembretes = dict(s.execute(select(q.c.proximo_lembrete, func.count()).where(
        vivo, q.c.proximo_lembrete.is_not(None), q.c.proximo_lembrete <= fim)
        .group_by(q.c.proximo_lembrete)).all())
    dias = [hoje + timedelta(days=i) for i in range(DIAS_AGENDA)]
    agenda = {d: {"dia": d, "pesquisas": 0, "lembretes": 0, "sai": _sai(cfg, d)} for d in dias}
    if agora.time() >= cfg.janela_fim:
        agenda[hoje]["sai"] = False

    def somar(d: date, campo: str, n: int):
        saida = _dia_de_saida(cfg, d, hoje, agora)
        if saida in agenda:
            agenda[saida][campo] += n

    somar(hoje, "pesquisas", na_fila)
    for d, n in futuros.items():
        somar(d, "pesquisas", n)
    for d, n in lembretes.items():
        somar(max(d, hoje), "lembretes", n)
    return [agenda[d] for d in dias]


def _respostas(s, conta_id: int, de: date, ate: date) -> dict:
    saiu = exists().where(Envio.conta_id == conta_id, Envio.convite_id == Convite.id, Envio.tipo == "convite",
                          Envio.situacao.in_(SAIU))
    linhas = s.execute(select(
        Convite.canal, func.count(), func.count().filter(Convite.respondido_em.is_not(None)),
    ).where(Convite.conta_id == conta_id, Convite.canal.in_(("email", "whatsapp")), saiu,
            *entre_datas(Convite.criado_em, de, ate)).group_by(Convite.canal)).all()
    horas = s.scalar(select(func.percentile_cont(0.5).within_group(
        func.extract("epoch", Convite.respondido_em - Convite.criado_em) / 3600))
        .where(Convite.conta_id == conta_id, Convite.canal.in_(("email", "whatsapp")), saiu,
               Convite.respondido_em.is_not(None), *entre_datas(Convite.criado_em, de, ate)))
    canais = sorted(({"canal": c, "enviadas": n, "respondidas": r, "taxa": _taxa(r, n)} for c, n, r in linhas),
                    key=lambda x: x["canal"])
    enviadas = sum(x["enviadas"] for x in canais)
    respondidas = sum(x["respondidas"] for x in canais)
    return {"de": de, "ate": ate, "enviadas": enviadas, "respondidas": respondidas, "taxa": _taxa(respondidas, enviadas),
            "horas_ate_metade": round(float(horas), 1) if horas is not None else None, "canais": canais}


def _taxa(parte: int, total: int) -> int | None:
    return round(parte * 100 / total) if total else None


def panorama(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        sem_jit(s)
        cfg = obter(s, criar=False)
        agora = relogio.agora()
        hoje = agora.date()
        pc = pre_condicoes(s, cfg)
        q = consulta_fila(cfg, hoje)
        wa = whatsapp_da_config(s, cfg)
        tem_canal = q.c.email.is_not(None) if wa is None else or_(q.c.email.is_not(None), q.c.telefone.is_not(None))
        devidos = and_(q.c.ativo.is_(True), q.c.situacao.in_(("na_fila", "nao_saiu")),
                       or_(q.c.proximo_envio.is_(None), q.c.proximo_envio <= hoje))
        elegivel = and_(tem_canal, q.c.descanso_ate.is_(None), q.c.falhas < MAX_FALHAS)
        na_fila, fora = s.execute(select(func.count().filter(elegivel), func.count().filter(not_(elegivel)))
                                  .select_from(q).where(devidos)).one()
        if not cfg.envios_ativos:
            estado = "desligado"
        elif not pc["pronto"]:
            estado = "parado"
        elif not cfg.envio_automatico:
            estado = "manual"
        else:
            estado = "ligado"
        proximo_contato = None
        if not na_fila:
            proximo_contato = s.scalar(select(func.min(q.c.proximo_envio)).where(
                q.c.ativo.is_(True), not_(q.c.saiu), tem_canal, q.c.proximo_envio > hoje))
        dados = {
            "automatico": {
                "estado": estado,
                "proxima_rodada": proxima_rodada(cfg, agora) if estado == "ligado" else None,
                "na_fila": na_fila,
                "fora_da_rodada": fora,
                "por_rodada": LIMITE_ROBO,
                "proximo_contato": proximo_contato,
                "janela_inicio": cfg.janela_inicio.strftime("%H:%M"),
                "janela_fim": cfg.janela_fim.strftime("%H:%M"),
                "so_dias_uteis": cfg.so_dias_uteis,
                "intervalo_dias": cfg.intervalo_dias,
                "canal": cfg.canal,
                "lembretes": cfg.lembretes,
            },
            "agenda": _agenda(s, cfg, q, tem_canal, hoje, agora, na_fila),
            "respostas": {
                **_respostas(s, ctx.conta_id, hoje - timedelta(days=DIAS_RESPOSTAS - 1), hoje),
                "anterior": _respostas(s, ctx.conta_id, hoje - timedelta(days=2 * DIAS_RESPOSTAS - 1),
                                       hoje - timedelta(days=DIAS_RESPOSTAS)),
            },
        }
    return dados

