"""Tarefas fora da requisição: robô (envio automático), lembretes e retomada de pendentes.

A lista de contas vem do modo sistema (só ids); todo o trabalho de cada conta roda em em_conta(conta).
"""
from datetime import time, timedelta

from sqlalchemy import and_, exists, func, not_, or_, select
from sqlalchemy.orm import Session, aliased

from toqqi.core import relogio
from toqqi.core.db import em_conta, modo_sistema
from toqqi.modelos import ConfigEnvios, Contato, Convite, Envio
from toqqi.modulos.envios.configuracao import na_janela, obter, prazo_aguardando, pronto
from toqqi.modulos.envios.fila import consulta_fila, data_local, descadastrado, dia_do_lembrete
from toqqi.modulos.envios.processamento import RETOMAR_APOS, criar_convite_email, novo_envio, processar_lista

LIMITE_ROBO = 100
LIMITE_LEMBRETES = 200
INTERVALO_ROBO = timedelta(hours=6)
MAX_FALHAS = 3
LEMBRETES_A_PARTIR = time(10, 0)


def _contas(*condicoes) -> list[int]:
    with modo_sistema() as s:
        return list(s.scalars(select(ConfigEnvios.conta_id).where(ConfigEnvios.envios_ativos.is_(True), *condicoes)
                              .order_by(ConfigEnvios.conta_id)))


# ---- robô -------------------------------------------------------------------

def robo_conta(conta_id: int, forcar: bool = False) -> dict | None:
    """Agenda os convites automáticos da conta. None se não era hora de rodar (ou faltou pré-condição).
    `forcar` ignora a janela e o intervalo de 6 h. Devolve {agendados, ignorados, envios}."""
    with em_conta(conta_id) as s:
        cfg = obter(s, travar=True)
        agora = relogio.agora()
        if not cfg.envio_automatico or not pronto(s, cfg):
            return None
        if not forcar and (not na_janela(cfg, agora)
                           or (cfg.robo_rodou_em and agora - cfg.robo_rodou_em < INTERVALO_ROBO)):
            return None
        cfg.robo_rodou_em = agora
        hoje = agora.date()
        q = consulta_fila(cfg, hoje)
        na_fila = and_(q.c.ativo.is_(True), q.c.situacao.in_(("na_fila", "nao_saiu")),
                       or_(q.c.proximo_envio.is_(None), q.c.proximo_envio <= hoje))
        elegivel = and_(q.c.email.is_not(None), q.c.descanso_ate.is_(None), q.c.falhas < MAX_FALHAS)
        ids = s.scalars(select(q.c.id).where(na_fila, elegivel)
                        .order_by(q.c.proximo_envio.asc().nulls_first(), q.c.id).limit(LIMITE_ROBO)).all()
        ignorados = s.scalar(select(func.count()).select_from(q).where(na_fila, not_(elegivel)))
        envios = [(conta_id, criar_convite_email(s, cfg, s.get(Contato, i), "automatico").id) for i in ids]
    return {"agendados": len(envios), "ignorados": ignorados, "envios": envios}


def robo() -> dict:
    total = {"contas": 0, "agendados": 0, "ignorados": 0}
    for conta_id in _contas(ConfigEnvios.envio_automatico.is_(True)):
        r = robo_conta(conta_id)
        if r is None:
            continue
        processar_lista(r["envios"])
        total["contas"] += 1
        total["agendados"] += r["agendados"]
        total["ignorados"] += r["ignorados"]
    return total


# ---- lembretes --------------------------------------------------------------

def _lembretes_devidos(cfg: ConfigEnvios, hoje):
    """(convite, contato, pode_receber) dos convites por e-mail com lembrete devido até `hoje` (inclusive),
    e a expressão da data devida (para a prévia)."""
    dia = dia_do_lembrete(cfg, Convite.lembretes_enviados)
    data_convite = data_local(Convite.criado_em)
    devido = data_convite + dia
    mais_novo = aliased(Convite)
    ultimo_envio = (select(Envio.situacao).where(Envio.convite_id == Convite.id, Envio.tipo == "convite")
                    .order_by(Envio.id.desc()).limit(1).correlate(Convite).scalar_subquery())
    pendente = exists().where(Envio.convite_id == Convite.id, Envio.situacao == "pendente")
    pode_receber = and_(Contato.ativo.is_(True), Contato.recebe_pesquisas.is_(True), Contato.email.is_not(None),
                        not_(descadastrado(Contato.email)))
    condicoes = [
        Convite.canal == "email", Convite.respondido_em.is_(None),
        Convite.lembretes_enviados < cfg.lembretes,
        data_convite >= hoje - timedelta(days=prazo_aguardando(cfg)),
        or_(Convite.ultimo_lembrete_em.is_(None), data_local(Convite.ultimo_lembrete_em) < hoje),
        not_(exists().where(mais_novo.contato_id == Convite.contato_id, mais_novo.id != Convite.id,
                            mais_novo.criado_em >= Convite.criado_em)),
        ultimo_envio == "enviado",
        not_(pendente),
    ]
    base = select(Convite, Contato, pode_receber.label("pode")).join(Contato, Contato.id == Convite.contato_id)
    return base.where(*condicoes), devido


def lembretes_conta(conta_id: int, forcar: bool = False) -> dict | None:
    """Agenda os lembretes do dia. None se não era hora de rodar. `forcar` ignora horário e o "uma vez
    por dia" da conta (cada convite continua recebendo no máximo um lembrete por dia)."""
    with em_conta(conta_id) as s:
        cfg = obter(s, travar=True)
        agora = relogio.agora()
        hoje = agora.date()
        if cfg.lembretes == 0 or not pronto(s, cfg):
            return None
        if not forcar and (agora.time() < LEMBRETES_A_PARTIR or not na_janela(cfg, agora)
                           or cfg.lembretes_rodou_em == hoje):
            return None
        cfg.lembretes_rodou_em = hoje
        consulta, devido = _lembretes_devidos(cfg, hoje)
        linhas = s.execute(consulta.where(devido <= hoje).order_by(Convite.criado_em, Convite.id)
                           .limit(LIMITE_LEMBRETES)).all()
        envios, ignorados = [], 0
        for convite, contato, pode in linhas:
            if not pode:
                ignorados += 1
                continue
            convite.ultimo_lembrete_em = agora
            e = novo_envio(s, contato, "lembrete", "lembrete", convite_id=convite.id,
                           lembrete=convite.lembretes_enviados + 1)
            envios.append((conta_id, e.id))
    return {"enviados": len(envios), "ignorados": ignorados, "envios": envios}


def lembretes() -> dict:
    total = {"contas": 0, "enviados": 0, "ignorados": 0}
    for conta_id in _contas(ConfigEnvios.lembretes > 0):
        r = lembretes_conta(conta_id)
        if r is None:
            continue
        processar_lista(r["envios"])
        total["contas"] += 1
        total["enviados"] += r["enviados"]
        total["ignorados"] += r["ignorados"]
    return total


def previa_lembretes(s: Session) -> dict:
    cfg = obter(s, criar=False)
    hoje = relogio.hoje()
    if cfg.lembretes == 0:
        return {"hoje": 0, "amanha": 0}
    consulta, devido = _lembretes_devidos(cfg, hoje)
    consulta = consulta.where(consulta.selected_columns.pode)

    def contar(*cond) -> int:
        return s.scalar(select(func.count()).select_from(consulta.where(*cond).subquery()))

    return {"hoje": contar(devido <= hoje), "amanha": contar(devido == hoje + timedelta(days=1))}


# ---- pendentes --------------------------------------------------------------

def pendentes() -> int:
    """Retoma envios pendentes há mais de 10 minutos (queda do processo)."""
    limite = relogio.agora() - RETOMAR_APOS
    with modo_sistema() as s:
        pares = s.execute(select(Envio.conta_id, Envio.id)
                          .where(Envio.situacao == "pendente", func.coalesce(Envio.tentativa_em, Envio.criado_em) < limite)
                          .order_by(Envio.id)).all()
    processar_lista([(c, i) for c, i in pares])
    return len(pares)
