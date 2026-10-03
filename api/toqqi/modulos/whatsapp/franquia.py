"""Conta de WhatsApp conectada e franquia mensal do WhatsApp automático.

A franquia vale por mês do calendário (São Paulo) e conta cada mensagem do WhatsApp automático (convites e o
lembrete), não o "link pronto" nem a mensagem de teste. A reserva acontece quando o envio é criado, com a
linha do mês travada (sem corrida entre robô, envio manual e eventos); se a mensagem não sair, ela volta
(`devolver`). Acabou: o envio cai para e-mail, salvo com o excedente ligado (cobrado à parte).
Avisos por e-mail aos administradores aos 80% e aos 100%, uma vez por mês.
"""
import math

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.avisos import avisar_admins
from toqqi.core.config import config
from toqqi.modelos import Conta, WhatsappConta, WhatsappUso

LIMITES = {"essencial": 40, "profissional": 90, "empresa": 200, "cortesia": 200, "teste": 20}
VALOR_EXCEDENTE = 1.50


def plano_da_franquia(conta: Conta) -> str:
    return conta.situacao if conta.situacao in ("cortesia", "teste") else conta.plano


def limite(conta: Conta) -> int:
    return LIMITES.get(plano_da_franquia(conta), 0)


def mes_atual() -> str:
    return relogio.agora().strftime("%Y-%m")


def conectada(s: Session) -> WhatsappConta | None:
    return s.scalar(select(WhatsappConta))


def disponivel(s: Session) -> WhatsappConta | None:
    """Conta de WhatsApp conectada e ligada (a franquia é conferida na reserva)."""
    wc = conectada(s)
    return wc if wc is not None and wc.ativo else None


def _uso(s: Session, travar: bool = False) -> WhatsappUso:
    mes = mes_atual()
    if travar:
        s.execute(insert(WhatsappUso).values(mes=mes).on_conflict_do_nothing())
    consulta = select(WhatsappUso).where(WhatsappUso.mes == mes)
    uso = s.scalar(consulta.with_for_update() if travar else consulta)
    return uso if uso is not None else WhatsappUso(mes=mes, usadas=0, excedentes=0)


def franquia_json(s: Session) -> dict:
    conta = s.scalar(select(Conta))
    wc, uso = conectada(s), _uso(s)
    return {"plano": plano_da_franquia(conta), "limite": limite(conta), "usadas_mes": uso.usadas,
            "excedente_ativo": bool(wc and wc.excedente_ativo), "excedentes_mes": uso.excedentes,
            "valor_excedente": VALOR_EXCEDENTE}


def reservar(s: Session, wc: WhatsappConta) -> str | None:
    """Gasta uma mensagem do mês: "franquia", "excedente" ou None (acabou e o excedente está desligado)."""
    lim = limite(s.scalar(select(Conta)))
    uso = _uso(s, travar=True)
    if uso.usadas < lim:
        uso.usadas += 1
        _avisar(s, uso, lim, wc)
        return "franquia"
    if wc.excedente_ativo:
        uso.excedentes += 1
        return "excedente"
    return None


def devolver(s: Session, cobranca: str) -> None:
    uso = _uso(s, travar=True)
    if cobranca == "franquia":
        uso.usadas = max(uso.usadas - 1, 0)
    else:
        uso.excedentes = max(uso.excedentes - 1, 0)


def _avisar(s: Session, uso: WhatsappUso, lim: int, wc: WhatsappConta) -> None:
    botao = ("Abrir Integrações", f"{config().FRONTEND_URL.rstrip('/')}/integracoes")
    ligar = "Para continuar no WhatsApp, ligue o excedente em Integrações (R$ 1,50 por mensagem)."
    if uso.usadas >= lim and not uso.avisou_100:
        uso.avisou_80 = uso.avisou_100 = True
        seguir = ("Como o excedente está ligado, as próximas mensagens continuam pelo WhatsApp e são cobradas à "
                  "parte (R$ 1,50 cada)." if wc.excedente_ativo else
                  f"Até o fim do mês, as pesquisas vão por e-mail para quem tiver e-mail. {ligar}")
        avisar_admins(s, wc.conta_id, "A franquia de WhatsApp do mês acabou", [
            f"A sua conta usou as {lim} mensagens de WhatsApp automático incluídas no plano neste mês.", seguir,
        ], botao)
    elif uso.usadas >= math.ceil(lim * 0.8) and not uso.avisou_80:
        uso.avisou_80 = True
        avisar_admins(s, wc.conta_id, "Você já usou 80% da franquia de WhatsApp do mês", [
            f"A sua conta já usou {uso.usadas} das {lim} mensagens de WhatsApp automático incluídas no plano "
            "neste mês.",
            f"Quando a franquia acabar, as pesquisas vão por e-mail para quem tiver e-mail. {ligar}",
        ], botao)
