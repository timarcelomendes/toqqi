"""Cota de IA do plano (etapa 5b): análises por mês do calendário de São Paulo, em `ia_uso_mensal.cota_usada`.

Limites (etapa 5g: parâmetros da plataforma, `ia.cota.{plano}` e `ia.cota.cortesia`; padrões Essencial 100,
Profissional 500, Empresa 2.000 e cortesia `IA_COTA_CORTESIA`, 500): a conta em teste usa a do plano dela (o do
teste) e a cortesia, a da cortesia; plano desconhecido vale como o de `teste.plano`. Mudou o limite: vale na próxima
reserva (abaixo do já usado no mês, sem saldo até o mês virar). Gastam a cota as perguntas ao assistente (5b) e o resumo do painel e o parecer dos relatórios
(5d), cada um com as análises do nível de modelo da conta (`ia_texto.analises_do_nivel`: 1 no Rápido e no
Equilibrado, 2 no Mais detalhado, desde 03/10). A análise de cada resposta (4b) e os passos das ações ficam fora
dela, só com o teto de segurança (`ia_uso_mensal.analises`).

A reserva de N análises é atômica (`INSERT … ON CONFLICT … DO UPDATE … WHERE cota_usada + N <= limite`): passa
inteira ou não passa (nunca só uma parte), e pedidos ao mesmo tempo não passam do limite. A `Reserva` guarda a
quantidade. Quem reserva faz commit antes da IA (que pode levar até 60 s) e, se ela falhar, devolve exatamente as N
análises no mês da reserva, mesmo que o mês já tenha virado.

Sem saldo para o custo do nível (`motivo_sem_saldo`): nenhuma análise restante → "cota_esgotada" (como antes);
restam algumas, mas menos que o custo (ex.: resta 1 e o Mais detalhado gasta 2) → "cota_insuficiente", com a
mensagem que sugere o nível mais barato que cabe no que resta, ou diz que a cota renova no próximo mês se nenhum cabe
(`mensagem_insuficiente`; revisão da 5g: antes, sempre o Equilibrado). `erro_sem_saldo` monta o 409 de quando a
reserva não passou.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core import ia_texto, parametros, relogio
from toqqi.core.db import em_conta
from toqqi.core.errors import AppError
from toqqi.modelos import Conta, IaUsoMensal

MSG_ESGOTADA = "O limite mensal de análises de IA do seu plano foi atingido. Ele renova no dia 1º."


@dataclass(frozen=True)
class Reserva:
    conta_id: int
    mes: date  # dia 1 do mês (São Paulo) em que as análises foram gastas
    usadas: int = 0  # `cota_usada` logo depois da reserva
    limite: int = 0  # o limite do mês na hora da reserva
    quantidade: int = 1  # análises reservadas (o custo do nível): a devolução volta exatamente estas


def mes_atual() -> date:
    return relogio.hoje().replace(day=1)


def chave_do_limite(conta: Conta) -> str:
    """O parâmetro da cota da conta: cortesia → `ia.cota.cortesia`; teste (ou teste expirado) sem assinatura →
    `ia.cota.teste` (etapa 5k; antes, a do plano do teste); Personalizado → `planos.personalizado` (a cota fica na
    conta, `limite`); demais → pelo plano da conta (desconhecido → o de `teste.plano`)."""
    if conta.situacao == "cortesia":
        return "ia.cota.cortesia"
    if conta.situacao in ("teste", "teste_expirado") and conta.primeiro_vencimento is None:
        return "ia.cota.teste"
    if conta.plano == "personalizado":
        return "planos.personalizado"
    plano = conta.plano if conta.plano in parametros.PLANOS else parametros.valor("teste.plano")
    return f"ia.cota.{plano}"


def limite(conta: Conta) -> int:
    """Análises por mês da conta (`chave_do_limite`; no Personalizado, a cota contratada gravada na conta)."""
    chave = chave_do_limite(conta)
    if chave == "planos.personalizado":
        return max(0, int(conta.cota_ia_personalizada or 0))
    return max(0, int(parametros.valor(chave)))


def estado(s: Session, conta: Conta) -> dict:
    """{usadas, limite, restantes, mes} do mês atual; `restantes` nunca é negativo."""
    mes = mes_atual()
    usadas = s.scalar(select(IaUsoMensal.cota_usada).where(IaUsoMensal.conta_id == conta.id,
                                                            IaUsoMensal.mes == mes)) or 0
    maximo = limite(conta)
    return {"usadas": usadas, "limite": maximo, "restantes": max(0, maximo - usadas), "mes": mes.strftime("%Y-%m")}


def reservar(s: Session, conta: Conta, quantidade: int = 1) -> Reserva | None:
    """Gasta `quantidade` análises do mês se todas couberem no limite (atômico; nunca só uma parte). None = sem saldo
    para elas, e nada foi gasto (`erro_sem_saldo` diz se a cota acabou ou se não dá para este custo)."""
    if quantidade < 1:
        raise ValueError("a reserva precisa de pelo menos 1 análise")
    maximo = limite(conta)
    if quantidade > maximo:
        return None
    mes = mes_atual()
    linha = s.execute(
        insert(IaUsoMensal).values(conta_id=conta.id, mes=mes, cota_usada=quantidade)
        .on_conflict_do_update(index_elements=[IaUsoMensal.conta_id, IaUsoMensal.mes],
                               set_={"cota_usada": IaUsoMensal.cota_usada + quantidade},
                               where=IaUsoMensal.cota_usada + quantidade <= maximo)
        .returning(IaUsoMensal.cota_usada)).first()
    return Reserva(conta.id, mes, linha[0], maximo, quantidade) if linha is not None else None


def motivo_sem_saldo(uso: dict, custo: int) -> str | None:
    """Por que não dá para gastar `custo` análises com a cota `uso` (de `estado`): "cota_esgotada" sem nenhuma
    restante, "cota_insuficiente" com menos que o custo (ex.: resta 1 e o nível gasta 2), None quando cabe."""
    if uso["restantes"] <= 0:
        return "cota_esgotada"
    if uso["restantes"] < custo:
        return "cota_insuficiente"
    return None


def nivel_que_cabe(restantes: int) -> str | None:
    """O nível mais barato que cabe em `restantes` análises (entre os de mesmo custo, o mais completo: com os padrões,
    o Equilibrado); None se nenhum cabe."""
    cabem = [(ia_texto.analises_do_nivel(n), -i, n) for i, n in enumerate(ia_texto.NIVEIS)
             if ia_texto.analises_do_nivel(n) <= restantes]
    return min(cabem)[2] if cabem else None


def mensagem_insuficiente(restantes: int, nivel: str | None) -> str:
    """"Resta 1 análise e o nível Mais detalhado gasta 2. Troque para o Equilibrado em Configurações › IA ou aguarde
    o próximo mês." (no plural a partir de 2), sugerindo o nível mais barato que cabe no que resta (`nivel_que_cabe`);
    se nenhum cabe, "Nenhum nível gasta tão pouco: a cota renova no dia 1º do próximo mês."."""
    resta = "Resta 1 análise" if restantes == 1 else f"Restam {restantes} análises"
    inicio = f"{resta} e o nível {ia_texto.rotulo_do_nivel(nivel)} gasta {ia_texto.analises_do_nivel(nivel)}."
    sugerido = nivel_que_cabe(restantes)
    if sugerido is None:
        return f"{inicio} Nenhum nível gasta tão pouco: a cota renova no dia 1º do próximo mês."
    return (f"{inicio} Troque para o {ia_texto.rotulo_do_nivel(sugerido)} em Configurações › IA ou aguarde o próximo "
            "mês.")


def erro_sem_saldo(s: Session, conta: Conta, nivel: str | None) -> AppError:
    """O 409 de quando a reserva do custo do nível não passou, pela cota lida de novo: `cota_insuficiente` se ainda
    restam análises (menos que o custo); senão `cota_esgotada`, como antes."""
    uso = estado(s, conta)
    if motivo_sem_saldo(uso, ia_texto.analises_do_nivel(nivel)) == "cota_insuficiente":
        return AppError(409, "cota_insuficiente", mensagem_insuficiente(uso["restantes"], nivel))
    return AppError(409, "cota_esgotada", MSG_ESGOTADA)


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
    """Devolve as análises reservadas (`reserva.quantidade`, no mês da reserva; nunca abaixo de zero). Sem `s`, numa
    transação própria."""
    with _sessao(reserva, s) as sessao:
        sessao.execute(update(IaUsoMensal)
                       .where(IaUsoMensal.conta_id == reserva.conta_id, IaUsoMensal.mes == reserva.mes)
                       .values(cota_usada=func.greatest(IaUsoMensal.cota_usada - reserva.quantidade, 0)))


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
