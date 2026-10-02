"""Webhook do Asaas (POST /api/v1/asaas/webhook, sem login) e o reprocessamento pela tarefa `assinaturas`.

Sem `ASAAS_WEBHOOK_TOKEN` (ou com um token fora da regra: 32 a 255 caracteres, sem espaços nem acentos, diferente da
chave) a rota responde 404; cabeçalho `asaas-access-token` diferente (comparação em tempo constante) → 401.
1. O evento é gravado em `asaas_eventos` (modo sistema). O id do evento é a chave: repetido → 200 `{ok, repetido}` sem
   fazer nada. Só ids e tipo, nunca o corpo.
2. `PAYMENT_*` de uma assinatura nossa (do ambiente da chave atual) ou de uma cobrança já conhecida: depois da resposta
   (o Asaas pede 200 depressa), a cobrança é consultada no Asaas com a conta travada — a fonte da verdade é o Asaas,
   então evento fora de ordem ou forjado não muda nada —, gravada (ou marcada removida se o Asaas não acha mais) e a
   conta é recalculada.
   `PAYMENT_*` de uma assinatura desconhecida fica pendente (nunca ignorado em silêncio): a API pergunta ao Asaas de
   quem é a assinatura; com a referência de uma conta nossa ("toqqi-conta-{id}"), espera o que estiver em andamento na
   conta (um assinar ainda gravando) e, se ela continua desconhecida, concilia (log de erro: adota ou remove). A tarefa
   tenta resolver por até 1 hora; depois, ignorado (log de erro). O resto (outros eventos, cobrança avulsa, assinatura
   de outro ambiente ou de outro sistema) fica gravado como ignorado.
3. Erro no passo 2: o evento fica com `erro` e a tarefa tenta de novo. O Asaas fora do ar (ou a chave recusada) não
   gasta tentativa — a tarefa para e retoma na próxima vez —; os outros erros contam, até 5.
"""
import logging

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from toqqi.core import asaas
from toqqi.core.config import config
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.errors import AppError
from toqqi.core.log_seguro import descrever_erro, do_banco
from toqqi.modelos import AsaasEvento, Assinatura, Cobranca
from toqqi.modulos.assinatura import conferencia
from toqqi.modulos.assinatura.servico import (
    FORA_DO_AR,
    filtro_ambiente,
    recalcular,
    sincronizar_cobranca,
    travar_conta,
)

log = logging.getLogger("toqqi.asaas")

MAX_TENTATIVAS = 5
LOTE = 200
ESPERA = "2 minutes"  # o reprocessamento deixa o segundo plano da requisição terminar antes
PRAZO_DESCONHECIDA = "1 hour"  # aviso de assinatura desconhecida: tenta resolver por até 1 hora
_avisos: set[str] = set()


def _uma_vez(chave: str, mensagem: str) -> None:
    if chave not in _avisos:
        _avisos.add(chave)
        log.error(mensagem)


def token() -> str | None:
    """O token do webhook, se configurado e dentro da regra do Asaas (senão a rota fica desligada)."""
    cfg = config()
    t = cfg.ASAAS_WEBHOOK_TOKEN
    if not t:
        return None
    if not 32 <= len(t) <= 255 or not t.isascii() or any(ch.isspace() for ch in t):
        _uma_vez("tamanho", "ASAAS_WEBHOOK_TOKEN precisa ter de 32 a 255 caracteres, sem espaços nem acentos: "
                            "webhook desligado.")
        return None
    if t == cfg.ASAAS_API_KEY.strip():
        _uma_vez("igual", "ASAAS_WEBHOOK_TOKEN não pode ser igual à ASAAS_API_KEY: webhook desligado.")
        return None
    return t


def _texto(v, maximo: int) -> str | None:
    return v if isinstance(v, str) and 1 <= len(v) <= maximo else None


def _dono(s, assinatura_id: str | None, pagamento_id: str) -> tuple[int | None, bool]:
    """(conta, é de outro ambiente) pela assinatura ou pela cobrança já conhecidas."""
    linha = None
    if assinatura_id is not None:
        linha = s.execute(select(Assinatura.conta_id, Assinatura.ambiente)
                          .where(Assinatura.asaas_id == assinatura_id)).first()
    if linha is None:
        linha = s.execute(select(Cobranca.conta_id, Assinatura.ambiente)
                          .join(Assinatura, Assinatura.id == Cobranca.assinatura_id)
                          .where(Cobranca.asaas_id == pagamento_id)).first()
    if linha is None:
        return None, False
    amb = asaas.ambiente()
    if amb is not None and linha.ambiente != amb:
        return None, True
    return linha.conta_id, False


def receber(dados: dict) -> tuple[dict, str | None]:
    """Grava o evento. Devolve (resposta, id do evento a processar depois da resposta, ou None)."""
    evento_id, tipo = _texto(dados.get("id"), 200), _texto(dados.get("event"), 100)
    if evento_id is None or tipo is None:
        raise AppError(422, "dados_invalidos", "Aviso do Asaas em formato inválido.")
    pagamento = dados.get("payment") if isinstance(dados.get("payment"), dict) else {}
    pagamento_id = _texto(pagamento.get("id"), 100)
    assinatura_id = _texto(pagamento.get("subscription"), 100)
    with modo_sistema() as s:  # a conta ainda é desconhecida
        conta_id, pendente = None, False
        if tipo.startswith("PAYMENT_") and pagamento_id is not None:
            conta_id, de_outro_ambiente = _dono(s, assinatura_id, pagamento_id)
            # assinatura desconhecida: pendente (a API descobre de quem é perguntando ao Asaas)
            pendente = conta_id is not None or (assinatura_id is not None and not de_outro_ambiente)
        ignorado = not pendente
        novo = s.scalar(insert(AsaasEvento).values(
            id=evento_id, tipo=tipo, conta_id=conta_id, cobranca_asaas_id=pagamento_id,
            assinatura_asaas_id=assinatura_id, ignorado=ignorado, processado_em=func.now() if ignorado else None,
        ).on_conflict_do_nothing(index_elements=[AsaasEvento.id]).returning(AsaasEvento.id))
    if novo is None:
        return {"ok": True, "repetido": True}, None
    if ignorado:
        return {"ok": True, "ignorado": True}, None
    return {"ok": True}, evento_id


def _conta_local(assinatura_id: str) -> int | None:
    with modo_sistema() as s:
        return s.scalar(select(Assinatura.conta_id).where(Assinatura.asaas_id == assinatura_id, filtro_ambiente()))


def _resolver(pagamento_id: str) -> int | None:
    """Conta de um aviso de assinatura desconhecida, pelo que o Asaas diz (não pelo corpo do aviso): a cobrança → a
    assinatura → a referência "toqqi-conta-{id}". None: não é nossa (ou o Asaas não acha mais)."""
    try:
        pagamento = asaas.obter_cobranca(pagamento_id)
    except asaas.FalhaAsaas as f:
        if f.tipo == "nao_encontrado":
            return None
        raise
    sub_id = _texto(pagamento.get("subscription"), 100)
    if sub_id is None:
        return None
    conta_id = _conta_local(sub_id)  # um assinar pode ter gravado a assinatura depois do aviso
    if conta_id is not None:
        return conta_id
    try:
        sub = asaas.obter_assinatura(sub_id)
    except asaas.FalhaAsaas as f:
        if f.tipo == "nao_encontrado":
            return None
        raise
    dona = conferencia.conta_da_referencia(sub.get("externalReference"))
    if dona is None:
        return None  # de outro sistema na mesma conta do Asaas
    return conferencia.conciliar_por_aviso(dona, sub_id)


def _aplicar(conta_id: int, pagamento_id: str) -> bool:
    """Consulta a cobrança no Asaas com a conta travada e grava; False se ela não é de uma assinatura da conta (deste
    ambiente)."""
    with em_conta(conta_id) as s:
        conta = travar_conta(s, conta_id)
        if conta is None:
            return False
        try:
            pagamento = asaas.obter_cobranca(pagamento_id)
        except asaas.FalhaAsaas as f:
            if f.tipo != "nao_encontrado":
                raise
            pagamento = None  # o Asaas não acha mais: removida
        assinatura = None
        if pagamento is not None:
            sub = pagamento.get("subscription")
            if isinstance(sub, str):  # a da conta (RLS), pelo que o Asaas diz, e não pelo aviso
                assinatura = s.scalar(select(Assinatura).where(Assinatura.asaas_id == sub, filtro_ambiente()))
            conhecida = s.scalar(select(Cobranca.id).where(Cobranca.asaas_id == pagamento_id))
            if assinatura is None and conhecida is None:
                return False
        sincronizar_cobranca(s, conta_id, pagamento_id, pagamento, assinatura)
        recalcular(s, conta)
        return True


def _concluir(evento_id: str, ignorado: bool, erro: str | None = None) -> None:
    with modo_sistema() as s:
        s.execute(update(AsaasEvento).where(AsaasEvento.id == evento_id)
                  .values(processado_em=func.now(), erro=erro, ignorado=ignorado))


def _falhou(evento_id: str, conta_id: int | None, e: Exception) -> str:
    fora_do_ar = isinstance(e, asaas.FalhaAsaas) and e.tipo in FORA_DO_AR
    if isinstance(e, asaas.FalhaAsaas):
        detalhe = f"Asaas: {e.detalhe}"
    elif do_banco(e):
        detalhe = f"banco: {descrever_erro(e)}"
    else:
        detalhe = type(e).__name__
    valores: dict = {"erro": detalhe[:300]}
    if not fora_do_ar:
        valores["tentativas"] = AsaasEvento.tentativas + 1
    with modo_sistema() as s:
        tentativas = s.scalar(update(AsaasEvento).where(AsaasEvento.id == evento_id).values(**valores)
                              .returning(AsaasEvento.tentativas))
    if fora_do_ar:
        log.warning("Asaas: o evento %s (conta %s) fica para depois: %s (não conta como tentativa).", evento_id,
                    conta_id, detalhe)
        return "erro_asaas"
    nivel = logging.ERROR if (tentativas or 0) >= MAX_TENTATIVAS else logging.WARNING
    log.log(nivel, "Asaas: erro ao processar o evento %s da conta %s (tentativa %s de %s): %s.", evento_id, conta_id,
            tentativas, MAX_TENTATIVAS, detalhe)
    return "erro"


def processar_evento(evento_id: str) -> str:
    """Processa um evento ainda não processado: "ok", "ignorado", "nada" (já processado), "erro" ou "erro_asaas"
    (o Asaas está fora ou recusou a chave: os próximos também falhariam)."""
    with modo_sistema() as s:
        linha = s.execute(select(
            AsaasEvento.conta_id, AsaasEvento.cobranca_asaas_id, AsaasEvento.processado_em,
            AsaasEvento.recebido_em < func.now() - text(f"interval '{PRAZO_DESCONHECIDA}'"),
        ).where(AsaasEvento.id == evento_id)).first()
    if linha is None or linha[2] is not None or linha[1] is None:
        return "nada"
    conta_id, pagamento_id, _, passou_do_prazo = linha
    try:
        if conta_id is None:  # assinatura desconhecida
            if passou_do_prazo:
                log.error("Asaas: o evento %s, de uma assinatura desconhecida, não foi resolvido em 1 hora; ignorado.",
                          evento_id)
                _concluir(evento_id, ignorado=True, erro="assinatura desconhecida")
                return "ignorado"
            conta_id = _resolver(pagamento_id)
            if conta_id is None:
                _concluir(evento_id, ignorado=True)
                return "ignorado"
            with modo_sistema() as s:
                s.execute(update(AsaasEvento).where(AsaasEvento.id == evento_id).values(conta_id=conta_id))
        nosso = _aplicar(conta_id, pagamento_id)
    except Exception as e:  # noqa: BLE001 - fica com erro para a tarefa tentar de novo
        return _falhou(evento_id, conta_id, e)
    _concluir(evento_id, ignorado=not nosso)
    return "ok" if nosso else "ignorado"


def processar_depois(evento_id: str) -> None:
    """Segundo plano da requisição do webhook (não levanta exceção)."""
    try:
        processar_evento(evento_id)
    except Exception:  # noqa: BLE001 - a tarefa retoma
        log.exception("Asaas: erro inesperado ao processar o evento %s.", evento_id)


def reprocessar() -> int:
    """Tarefa: eventos ainda não processados (com erro, de assinatura desconhecida, ou o processo caiu antes), até 5
    tentativas. Para no primeiro erro do Asaas (fora do ar ou chave recusada). Devolve quantos foram concluídos."""
    with modo_sistema() as s:
        ids = s.scalars(select(AsaasEvento.id).where(
            AsaasEvento.processado_em.is_(None), AsaasEvento.ignorado.is_(False),
            AsaasEvento.tentativas < MAX_TENTATIVAS,
            AsaasEvento.recebido_em < func.now() - text(f"interval '{ESPERA}'"),
        ).order_by(AsaasEvento.recebido_em).limit(LOTE)).all()
    feitos = 0
    for evento_id in ids:
        resultado = processar_evento(evento_id)
        if resultado in ("ok", "ignorado"):
            feitos += 1
        elif resultado == "erro_asaas":
            break
    return feitos
