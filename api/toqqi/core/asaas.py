"""Adaptador do Asaas (cobrança): httpx, sem SDK.

Endereço: `ASAAS_URL` (Asaas falso local, testes) ou o da chave — `$aact_prod_…` → produção; qualquer outra →
sandbox (uma chave de formato desconhecido nunca cobra de verdade por engano). Cabeçalhos `access_token`,
`User-Agent: Toqqi/1.0` (obrigatório para contas novas do Asaas) e `Content-Type: application/json`; 20 s de tempo
limite e sem redirecionamento. Os testes trocam `transporte` por um `httpx.MockTransport` (o conftest bloqueia a rede).

Falhas (`FalhaAsaas.tipo`):
- `recusado`: 400 (e os outros 4xx que não estão abaixo) com `errors: [{code, description}]` — dado recusado;
- `configuracao`: 401/403 (chave errada ou sem permissão; log de erro) ou chave vazia;
- `nao_encontrado`: 404;
- `indisponivel`: 408, 429, 5xx, tempo esgotado, rede e resposta que não é um objeto JSON.
O log leva só método, caminho, status e os códigos de erro do Asaas: nunca a chave, o CPF/CNPJ ou as descrições dos
erros (que podem repetir o dado enviado).
"""
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from urllib.parse import quote

import httpx

from toqqi.core.config import config

log = logging.getLogger("toqqi.asaas")

transporte: httpx.BaseTransport | None = None  # os testes trocam por httpx.MockTransport

TEMPO_LIMITE = 20  # segundos por chamada
URL_PRODUCAO = "https://api.asaas.com/v3"
URL_SANDBOX = "https://api-sandbox.asaas.com/v3"
PREFIXO_PRODUCAO = "$aact_prod_"
AGENTE = "Toqqi/1.0"
POR_PAGINA = 100  # máximo do Asaas
MAX_PAGINAS = 10

# situação da cobrança no Asaas → nossa (a removida vem de `deleted: true` ou do 404)
PENDENTE = frozenset({"PENDING", "AWAITING_RISK_ANALYSIS"})
PAGA = frozenset({"CONFIRMED", "RECEIVED", "RECEIVED_IN_CASH", "DUNNING_RECEIVED"})
VENCIDA = frozenset({"OVERDUE", "DUNNING_REQUESTED"})
ESTORNADA = frozenset({"REFUNDED", "REFUND_REQUESTED", "REFUND_IN_PROGRESS", "AWAITING_CHARGEBACK_REVERSAL"})
FORMAS = {"PIX": "pix", "BOLETO": "boleto", "CREDIT_CARD": "cartao", "DEBIT_CARD": "cartao"}


class FalhaAsaas(Exception):
    """`tipo`: recusado | configuracao | nao_encontrado | indisponivel. `detalhe` nunca leva dado de cliente nem a
    chave; `erros` = [(code, description)] do Asaas (só para mostrar a quem digitou, nunca para o log)."""

    def __init__(self, tipo: str, detalhe: str, erros: list[tuple[str, str]] | None = None):
        assert tipo in ("recusado", "configuracao", "nao_encontrado", "indisponivel")
        super().__init__(detalhe)
        self.tipo = tipo
        self.detalhe = detalhe
        self.erros = erros or []


@dataclass(frozen=True)
class Cliente:
    """Dados do cliente no Asaas. `telefone` só com dígitos e o 55 (como guardamos)."""
    nome: str  # razão social (ou nome completo, com CPF)
    documento: str  # CPF (11 dígitos) ou CNPJ (14 caracteres; o alfanumérico vai em maiúsculas, como está)
    email: str
    telefone: str
    referencia: str  # "toqqi-conta-{id}"


def chave() -> str:
    return config().ASAAS_API_KEY.strip()


def disponivel() -> bool:
    return bool(chave())


def ambiente() -> str | None:
    """Ambiente do Asaas da chave configurada: `producao` ($aact_prod_…) ou `sandbox` (qualquer outra); None sem
    chave. Assinaturas e clientes de outro ambiente não existem para esta chave."""
    if not disponivel():
        return None
    return "producao" if chave().startswith(PREFIXO_PRODUCAO) else "sandbox"


def endereco() -> str:
    url = config().ASAAS_URL.strip()
    if url:
        return url.rstrip("/")
    return URL_PRODUCAO if chave().startswith(PREFIXO_PRODUCAO) else URL_SANDBOX


def _id(v: str) -> str:
    return quote(str(v), safe="")


def _erros(r: httpx.Response) -> list[tuple[str, str]]:
    try:
        lista = r.json().get("errors")
    except (ValueError, AttributeError):
        return []
    saida = []
    for e in lista if isinstance(lista, list) else []:
        if isinstance(e, dict):
            codigo = e.get("code") if isinstance(e.get("code"), str) else ""
            descricao = e.get("description") if isinstance(e.get("description"), str) else ""
            saida.append((codigo[:100], descricao[:300]))
    return saida


def _falha_http(metodo: str, caminho: str, r: httpx.Response) -> FalhaAsaas:
    status = r.status_code
    if status in (401, 403):
        log.error("Asaas recusou a chave (HTTP %s em %s %s). Confira ASAAS_API_KEY e ASAAS_URL.", status, metodo,
                  caminho)
        return FalhaAsaas("configuracao", f"HTTP {status}")
    if status == 404:
        return FalhaAsaas("nao_encontrado", "HTTP 404")
    if status in (408, 429) or status >= 500:
        log.warning("Asaas indisponível (HTTP %s em %s %s).", status, metodo, caminho)
        return FalhaAsaas("indisponivel", f"HTTP {status}")
    erros = _erros(r)
    codigos = ", ".join(c for c, _ in erros if c) or "sem código"
    log.warning("Asaas recusou %s %s (HTTP %s; %s).", metodo, caminho, status, codigos)
    return FalhaAsaas("recusado", f"HTTP {status} ({codigos})", erros)


def _chamar(metodo: str, caminho: str, corpo: dict | None = None, params: dict | None = None) -> dict:
    if not disponivel():
        raise FalhaAsaas("configuracao", "ASAAS_API_KEY vazia")
    cabecalhos = {"access_token": chave(), "User-Agent": AGENTE, "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=TEMPO_LIMITE, follow_redirects=False, transport=transporte,
                          headers=cabecalhos) as c:
            r = c.request(metodo, endereco() + caminho, json=corpo, params=params)
    except httpx.TimeoutException:
        log.warning("Asaas: tempo esgotado em %s %s.", metodo, caminho)
        raise FalhaAsaas("indisponivel", "tempo esgotado") from None
    except httpx.HTTPError as e:
        log.warning("Asaas: falha de rede em %s %s (%s).", metodo, caminho, type(e).__name__)
        raise FalhaAsaas("indisponivel", f"falha de rede ({type(e).__name__})") from None
    if r.status_code >= 400:
        raise _falha_http(metodo, caminho, r)
    try:
        dados = r.json()
    except ValueError:
        dados = None
    if not isinstance(dados, dict):
        log.warning("Asaas: resposta que não é um objeto JSON em %s %s (HTTP %s).", metodo, caminho, r.status_code)
        raise FalhaAsaas("indisponivel", "resposta que não é um objeto JSON")
    return dados


def _id_criado(dados: dict, metodo: str, caminho: str) -> str:
    novo = dados.get("id")
    if not isinstance(novo, str) or not 1 <= len(novo) <= 100:
        log.warning("Asaas: resposta sem id em %s %s.", metodo, caminho)
        raise FalhaAsaas("indisponivel", "resposta sem id")
    return novo


# ---- clientes e assinaturas -----------------------------------------------------------

def telefone_local(telefone: str) -> str:
    """Só DDD + número (sem o 55), como o Asaas pede."""
    return telefone[2:] if telefone.startswith("55") and len(telefone) in (12, 13) else telefone


def corpo_cliente(c: Cliente) -> dict:
    """Celular (DDD + 9 dígitos) vai em `mobilePhone` e fixo (DDD + 8 dígitos) em `phone`; o outro campo vai vazio,
    para o Asaas apagar o número antigo quando o celular vira fixo (ou o contrário). CNPJ alfanumérico vai como está
    (maiúsculas, sem pontuação)."""
    local = telefone_local(c.telefone)
    celular = len(local) == 11
    return {"name": c.nome, "cpfCnpj": c.documento, "email": c.email, "mobilePhone": local if celular else "",
            "phone": "" if celular else local, "externalReference": c.referencia}


def criar_cliente(c: Cliente) -> str:
    return _id_criado(_chamar("POST", "/customers", corpo_cliente(c)), "POST", "/customers")


def _listar(caminho: str, params: dict) -> list[dict]:
    """Lista paginada do Asaas (até MAX_PAGINAS × 100)."""
    itens: list[dict] = []
    for _ in range(MAX_PAGINAS):
        dados = _chamar("GET", caminho, params={**params, "offset": len(itens), "limit": POR_PAGINA})
        pagina = [p for p in dados.get("data") or [] if isinstance(p, dict)]
        itens += pagina
        if dados.get("hasMore") is not True or not pagina:
            break
    return itens


def _da_referencia(itens: list[dict], referencia: str) -> list[dict]:
    """Só os itens com exatamente esta referência e um id: se o filtro do Asaas fosse ignorado, a lista traria os de
    outras contas (e a conciliação removeria assinaturas alheias)."""
    return [i for i in itens if i.get("externalReference") == referencia and isinstance(i.get("id"), str)
            and 1 <= len(i["id"]) <= 100]


def buscar_clientes(referencia: str) -> list[dict]:
    """Clientes (não removidos) com o nosso externalReference ("toqqi-conta-{id}")."""
    return [c for c in _da_referencia(_listar("/customers", {"externalReference": referencia}), referencia)
            if c.get("deleted") is not True]


def obter_cliente(cliente_id: str) -> dict:
    return _chamar("GET", f"/customers/{_id(cliente_id)}")


def atualizar_cliente(cliente_id: str, c: Cliente) -> None:
    _chamar("PUT", f"/customers/{_id(cliente_id)}", corpo_cliente(c))


def valor_json(valor: Decimal) -> float:
    return float(valor.quantize(Decimal("0.01")))


def corpo_assinatura(cliente_id: str, valor: Decimal, vencimento: date, descricao: str, referencia: str) -> dict:
    return {"customer": cliente_id, "billingType": "UNDEFINED", "value": valor_json(valor),
            "nextDueDate": vencimento.isoformat(), "cycle": "MONTHLY", "description": descricao,
            "externalReference": referencia}


def criar_assinatura(cliente_id: str, valor: Decimal, vencimento: date, descricao: str, referencia: str) -> str:
    corpo = corpo_assinatura(cliente_id, valor, vencimento, descricao, referencia)
    return _id_criado(_chamar("POST", "/subscriptions", corpo), "POST", "/subscriptions")


def atualizar_assinatura(assinatura_id: str, valor: Decimal, descricao: str) -> None:
    """Muda o valor (e a descrição) também das faturas em aberto (`updatePendingPayments`)."""
    _chamar("PUT", f"/subscriptions/{_id(assinatura_id)}",
            {"value": valor_json(valor), "description": descricao, "updatePendingPayments": True})


def obter_assinatura(assinatura_id: str) -> dict:
    return _chamar("GET", f"/subscriptions/{_id(assinatura_id)}")


def listar_assinaturas(referencia: str) -> list[dict]:
    """Assinaturas com o nosso externalReference ("toqqi-conta-{id}"), de qualquer cliente."""
    return _da_referencia(_listar("/subscriptions", {"externalReference": referencia}), referencia)


def assinatura_viva(assinatura: dict) -> bool:
    """Cobrando: não removida (`deleted`) nem INACTIVE/EXPIRED (o Asaas não gera mais faturas)."""
    return assinatura.get("deleted") is not True and assinatura.get("status", "ACTIVE") not in ("INACTIVE", "EXPIRED")


def remover_assinatura(assinatura_id: str) -> None:
    """O Asaas apaga junto as faturas pendentes e vencidas da assinatura."""
    _chamar("DELETE", f"/subscriptions/{_id(assinatura_id)}")


def cobrancas_da_assinatura(assinatura_id: str) -> list[dict]:
    return _listar(f"/subscriptions/{_id(assinatura_id)}/payments", {})


def obter_cobranca(cobranca_id: str) -> dict:
    return _chamar("GET", f"/payments/{_id(cobranca_id)}")


# ---- leitura de uma cobrança --------------------------------------------------------------

def situacao(pagamento: dict) -> str | None:
    """pendente | paga | vencida | estornada | removida; None para uma situação desconhecida."""
    if pagamento.get("deleted") is True:
        return "removida"
    st = pagamento.get("status")
    if not isinstance(st, str):
        return None
    if st in PENDENTE:
        return "pendente"
    if st in PAGA:
        return "paga"
    if st in VENCIDA:
        return "vencida"
    if st in ESTORNADA or st.startswith("CHARGEBACK_"):
        return "estornada"
    return None


def forma(pagamento: dict) -> str | None:
    return FORMAS.get(pagamento.get("billingType"))


def data(v) -> date | None:
    """"2026-10-15" (ou com hora depois) → date; o resto → None."""
    if not isinstance(v, str) or len(v) < 10:
        return None
    try:
        return date.fromisoformat(v[:10])
    except ValueError:
        return None


def data_do_pagamento(pagamento: dict) -> date | None:
    """`clientPaymentDate` (quando o cliente pagou) ou `paymentDate`."""
    return data(pagamento.get("clientPaymentDate")) or data(pagamento.get("paymentDate"))


def vencimento(pagamento: dict) -> date | None:
    return data(pagamento.get("dueDate"))


def valor(v) -> Decimal | None:
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        return None
    try:
        d = Decimal(str(v))
    except ArithmeticError:
        return None
    return d.quantize(Decimal("0.01")) if d.is_finite() and abs(d) < Decimal("100000000") else None


def link(pagamento: dict) -> str | None:
    url = pagamento.get("invoiceUrl")
    if isinstance(url, str) and url.startswith(("https://", "http://")) and len(url) <= 500:
        return url
    return None
