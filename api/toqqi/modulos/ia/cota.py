"""Cota de IA do plano (etapa 5b): análises por mês do calendário de São Paulo, em `ia_uso_mensal.cota_usada`.

Essencial 100, Profissional 500, Empresa 2.000; a conta em teste usa a do plano do teste e a cortesia usa
`IA_COTA_CORTESIA`. Hoje só o assistente gasta a cota (1 análise por pergunta); a análise de cada resposta (4b) fica
fora dela, só com o teto de segurança (`ia_uso_mensal.analises`).

A reserva é atômica (`INSERT … ON CONFLICT … DO UPDATE … WHERE cota_usada < limite`): duas perguntas ao mesmo tempo
não passam do limite. Quem reserva faz commit antes da conversa (que pode levar até 60 s) e, se ela falhar, devolve
a análise no mesmo mês da reserva, mesmo que o mês já tenha virado.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.config import config
from toqqi.core.db import em_conta
from toqqi.modelos import Conta, IaUsoMensal

COTA_PLANO = {"essencial": 100, "profissional": 500, "empresa": 2000}
PLANO_PADRAO = "profissional"


@dataclass(frozen=True)
class Reserva:
    conta_id: int
    mes: date  # dia 1 do mês (São Paulo) em que a análise foi gasta
    usadas: int = 0  # `cota_usada` logo depois da reserva
    limite: int = 0  # o limite do mês na hora da reserva


def mes_atual() -> date:
    return relogio.hoje().replace(day=1)


def limite(conta: Conta) -> int:
    """Análises por mês: cortesia → IA_COTA_CORTESIA; demais situações (inclusive teste) → pelo plano da conta."""
    if conta.situacao == "cortesia":
        return max(0, config().IA_COTA_CORTESIA)
    return COTA_PLANO.get(conta.plano or PLANO_PADRAO, COTA_PLANO[PLANO_PADRAO])


def estado(s: Session, conta: Conta) -> dict:
    """{usadas, limite, restantes, mes} do mês atual; `restantes` nunca é negativo."""
    mes = mes_atual()
    usadas = s.scalar(select(IaUsoMensal.cota_usada).where(IaUsoMensal.conta_id == conta.id,
                                                            IaUsoMensal.mes == mes)) or 0
    maximo = limite(conta)
    return {"usadas": usadas, "limite": maximo, "restantes": max(0, maximo - usadas), "mes": mes.strftime("%Y-%m")}


def reservar(s: Session, conta: Conta) -> Reserva | None:
    """Gasta 1 análise do mês, se houver saldo (atômico). None = cota esgotada."""
    maximo = limite(conta)
    if maximo <= 0:
        return None
    mes = mes_atual()
    linha = s.execute(
        insert(IaUsoMensal).values(conta_id=conta.id, mes=mes, cota_usada=1)
        .on_conflict_do_update(index_elements=[IaUsoMensal.conta_id, IaUsoMensal.mes],
                               set_={"cota_usada": IaUsoMensal.cota_usada + 1},
                               where=IaUsoMensal.cota_usada < maximo)
        .returning(IaUsoMensal.cota_usada)).first()
    return Reserva(conta.id, mes, linha[0], maximo) if linha is not None else None


def estado_da_reserva(reserva: Reserva) -> dict:
    """{usadas, limite, restantes, mes} como ficaram logo depois da reserva (para quando não dá para ler o banco)."""
    return {"usadas": reserva.usadas, "limite": reserva.limite,
            "restantes": max(0, reserva.limite - reserva.usadas), "mes": reserva.mes.strftime("%Y-%m")}


@contextmanager
def _sessao(reserva: Reserva, s: Session | None):
    if s is not None:
        yield s
    else:
        with em_conta(reserva.conta_id) as nova:
            yield nova


def devolver(reserva: Reserva, s: Session | None = None) -> None:
    """Devolve a análise reservada (no mês da reserva). Sem `s`, numa transação própria."""
    with _sessao(reserva, s) as sessao:
        sessao.execute(update(IaUsoMensal)
                       .where(IaUsoMensal.conta_id == reserva.conta_id, IaUsoMensal.mes == reserva.mes)
                       .values(cota_usada=func.greatest(IaUsoMensal.cota_usada - 1, 0)))


def somar_tokens(reserva: Reserva, entrada: int, saida: int, s: Session | None = None) -> None:
    """Soma os tokens de todas as chamadas da pergunta (no mês da reserva). Sem `s`, numa transação própria."""
    entrada, saida = max(0, int(entrada)), max(0, int(saida))
    if not entrada and not saida:
        return
    with _sessao(reserva, s) as sessao:
        sessao.execute(update(IaUsoMensal)
                       .where(IaUsoMensal.conta_id == reserva.conta_id, IaUsoMensal.mes == reserva.mes)
                       .values(cota_tokens_entrada=IaUsoMensal.cota_tokens_entrada + entrada,
                               cota_tokens_saida=IaUsoMensal.cota_tokens_saida + saida))
