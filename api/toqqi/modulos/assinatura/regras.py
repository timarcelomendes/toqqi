"""Regras da assinatura sem banco: quando os envios estão liberados, quando param, o aviso do topo das telas e o
primeiro vencimento. Saem só da linha da conta (lida a cada requisição): `situacao` (decidida por
`servico.recalcular`), `teste_ate`, `pago_ate`, `atrasada_desde` e `primeiro_vencimento` (cópia do da assinatura
ativa). Dias no fuso de São Paulo (`relogio`; os testes trocam o relógio).

Liberada (envios, robô, lembretes, CSAT, análise por IA, e-mails de pico e resumo semanal):
- `cortesia` e `ativa`: sempre;
- `teste` e `cancelada`: até o mais tarde entre o fim do teste e o fim do dia `pago_ate` (o "+14 dias" dentro de um
  período pago e o cancelamento depois de pagar no teste não abrem buraco); quem assinou durante o teste (o primeiro
  vencimento cai no último dia dele) e ainda não pagou segue liberado pela carência da primeira fatura, até o fim do
  7º dia depois do primeiro vencimento — sem buraco entre a meia-noite do vencimento e a tarefa que muda a situação
  para `atrasada`;
- `atrasada`: até o fim do 7º dia depois de `atrasada_desde`;
- `teste_expirado`: nunca.
"""
import calendar
from datetime import date, datetime, time, timedelta, timezone

from toqqi.core import relogio
from toqqi.modelos import Conta

DIAS_ATRASO = 7  # envios liberados até o fim do 7º dia depois do vencimento da fatura em atraso
DIAS_AVISO_TESTE = 5  # "teste acabando" com 5 dias ou menos
SEMPRE_LIBERADAS = ("cortesia", "ativa")

MSG_TESTE = "O período de teste acabou. Assine um plano para voltar a enviar."
MSG_AGUARDANDO = "Os envios voltam quando a fatura da assinatura for paga."
MSG_ATRASADA = "Os envios estão pausados por falta de pagamento. Pague a fatura em aberto para voltar a enviar."
MSG_CANCELADA = "A assinatura foi cancelada e o período pago terminou. Assine um plano para voltar a enviar."


def inicio_do_dia(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=relogio.FUSO)


def dia_de(momento: datetime) -> date:
    return momento.astimezone(relogio.FUSO).date()


def mais_um_mes(d: date) -> date:
    """Mesmo dia no mês seguinte (31/01 → 28/02 ou 29/02)."""
    ano, mes = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def fim_do_periodo_pago(vencimento: date) -> date:
    """Último dia coberto pelo pagamento de uma fatura: vencimento + 1 mês − 1 dia."""
    return mais_um_mes(vencimento) - timedelta(days=1)


def ultimo_dia_do_teste(conta: Conta) -> date | None:
    """Dia (São Paulo) do fim do teste; um fim exatamente à meia-noite fica no dia anterior."""
    if conta.teste_ate is None:
        return None
    return dia_de(conta.teste_ate - timedelta(microseconds=1))


def assinou_no_teste(conta: Conta) -> bool:
    """Tem assinatura ativa feita durante o teste (o primeiro vencimento cai até o último dia dele)."""
    ultimo = ultimo_dia_do_teste(conta)
    return conta.primeiro_vencimento is not None and ultimo is not None and conta.primeiro_vencimento <= ultimo


def dia_da_pausa(atrasada_desde: date) -> date:
    """Primeiro dia sem envios de uma conta em atraso (venceu 10/10 → param em 18/10)."""
    return atrasada_desde + timedelta(days=DIAS_ATRASO + 1)


def fim_do_teste(conta: Conta) -> datetime | None:
    """Fim do teste; quem assinou durante ele segue até o fim da carência da primeira fatura (7 dias depois do
    vencimento, que cai no último dia do teste), se for depois."""
    if conta.teste_ate is None:
        return None
    if assinou_no_teste(conta):
        return max(conta.teste_ate, inicio_do_dia(dia_da_pausa(conta.primeiro_vencimento)))
    return conta.teste_ate


def fim_do_periodo_pago_em(conta: Conta) -> datetime | None:
    """Fim do dia `pago_ate` (00:00 do dia seguinte, São Paulo)."""
    return inicio_do_dia(conta.pago_ate + timedelta(days=1)) if conta.pago_ate is not None else None


def _prazo(conta: Conta) -> datetime | None:
    """Momento em que os envios param pela situação (None: não há prazo — nunca liberada)."""
    if conta.situacao in ("teste", "cancelada"):
        return max((m for m in (fim_do_teste(conta), fim_do_periodo_pago_em(conta)) if m is not None), default=None)
    if conta.situacao == "atrasada" and conta.atrasada_desde is not None:
        return inicio_do_dia(dia_da_pausa(conta.atrasada_desde))
    return None


def liberada(conta: Conta, agora: datetime | None = None) -> bool:
    """Envios, robô, lembretes, CSAT, IA e e-mails do painel podem rodar (regra no cabeçalho)."""
    if conta.situacao in SEMPRE_LIBERADAS:
        return True
    prazo = _prazo(conta)
    return prazo is not None and (agora or relogio.agora()) < prazo


def pausa_em(conta: Conta, agora: datetime | None = None) -> datetime | None:
    """Quando os envios vão parar (UTC, como as outras datas e horas da API), se estão liberados com prazo; None se
    não param (cortesia, ativa) ou já pararam."""
    if conta.situacao in SEMPRE_LIBERADAS:
        return None
    prazo = _prazo(conta)
    if prazo is None or (agora or relogio.agora()) >= prazo:
        return None
    return prazo.astimezone(timezone.utc)


def _aviso(tipo: str, data: date | None = None, dias: int | None = None) -> dict:
    return {"tipo": tipo, "data": data, "dias": dias}


def aviso(conta: Conta, agora: datetime | None = None) -> dict | None:
    """Aviso do topo das telas: {tipo, data, dias} ou None.
    - teste_acabando: teste liberado com 5 dias ou menos; data = último dia do teste, dias = dias até ele (0 = hoje);
    - teste_expirado: data = último dia do teste;
    - atrasada: dentro dos 7 dias; data = dia em que os envios param, dias = dias até lá;
    - pausada: atrasada depois dos 7 dias; data = vencimento da fatura em atraso;
    - cancelada: ainda liberada pelo período pago; data = último dia com envios (o `pago_ate`, ou o fim do teste se
      for depois), dias = dias até ele (0 = hoje);
    - cancelada_encerrada: data = `pago_ate`;
    - aguardando_pagamento: tem assinatura ativa ainda sem pagamento (no lugar dos avisos de teste e de cancelada);
      data = primeiro vencimento, dias = dias até ele. Assinou no teste (liberada): só a partir de 5 dias antes do
      vencimento (e, vencida, o aviso de atrasada da carência); assinou sem teste válido (envios pausados até pagar):
      sempre."""
    agora = agora or relogio.agora()
    hoje = dia_de(agora)
    situacao = conta.situacao
    livre = liberada(conta, agora)
    if conta.primeiro_vencimento is not None and situacao in ("teste", "teste_expirado", "cancelada"):
        dias = (conta.primeiro_vencimento - hoje).days
        if livre and dias < 0:  # a primeira fatura venceu: carência (a tarefa já vai marcar atrasada)
            para = dia_da_pausa(conta.primeiro_vencimento)
            return _aviso("atrasada", para, (para - hoje).days)
        if livre and dias > DIAS_AVISO_TESTE:
            return None
        return _aviso("aguardando_pagamento", conta.primeiro_vencimento, dias)
    if situacao in ("teste", "cancelada") and livre:
        if conta.teste_ate is not None and agora < conta.teste_ate and not (
                situacao == "cancelada" and conta.pago_ate is not None and conta.pago_ate >= hoje):
            ultimo = ultimo_dia_do_teste(conta)  # o teste ainda corre
            dias = (ultimo - hoje).days
            return _aviso("teste_acabando", ultimo, dias) if dias <= DIAS_AVISO_TESTE else None
        ultimo = dia_de(_prazo(conta) - timedelta(microseconds=1))  # liberada pelo período pago (pagou e cancelou)
        return _aviso("cancelada", ultimo, (ultimo - hoje).days)
    if situacao in ("teste", "teste_expirado"):
        return _aviso("teste_expirado", ultimo_dia_do_teste(conta))
    if situacao == "atrasada":
        if livre:
            para = dia_da_pausa(conta.atrasada_desde)
            return _aviso("atrasada", para, (para - hoje).days)
        return _aviso("pausada", conta.atrasada_desde)
    if situacao == "cancelada":
        return _aviso("cancelada_encerrada", conta.pago_ate)
    return None


def cobranca_json(conta: Conta, agora: datetime | None = None) -> dict:
    """`conta.cobranca` em /eu e no login. `assinada` = tem assinatura ativa."""
    agora = agora or relogio.agora()
    return {"liberada": liberada(conta, agora), "assinada": conta.primeiro_vencimento is not None,
            "pago_ate": conta.pago_ate, "atrasada_desde": conta.atrasada_desde, "pausa_em": pausa_em(conta, agora),
            "aviso": aviso(conta, agora)}


def mensagem_pausa(conta: Conta) -> str:
    """Texto da pré-condição `assinatura` dos envios quando a conta não está liberada."""
    if conta.situacao == "atrasada":
        return MSG_ATRASADA
    if conta.primeiro_vencimento is not None:
        return MSG_AGUARDANDO  # assinou sem teste válido: volta quando a primeira fatura for paga
    if conta.situacao == "cancelada":
        return MSG_CANCELADA
    return MSG_TESTE


def primeiro_vencimento(conta: Conta, agora: datetime | None = None) -> date:
    """Primeira fatura de uma assinatura nova: no último dia do teste (se ele ainda vale); no dia seguinte ao
    `pago_ate` (se ainda no futuro); senão amanhã. Com os dois, o mais tarde."""
    agora = agora or relogio.agora()
    hoje = dia_de(agora)
    candidatos = []
    if conta.teste_ate is not None and agora < conta.teste_ate:
        candidatos.append(ultimo_dia_do_teste(conta))
    if conta.pago_ate is not None and conta.pago_ate >= hoje:
        candidatos.append(conta.pago_ate + timedelta(days=1))
    return max(candidatos) if candidatos else hoje + timedelta(days=1)
