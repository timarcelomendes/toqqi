"""Asaas falso para desenvolvimento local e para o teste integrado (ferramenta de desenvolvimento, não é código de
produção: tudo em memória, some ao reiniciar).

Implementa só o que o adaptador (`toqqi/core/asaas.py`) usa:
  GET (lista, filtro externalReference) e POST /v3/customers · GET e PUT /v3/customers/{id}
  GET (lista, filtros externalReference e customer) e POST /v3/subscriptions · GET, PUT e DELETE /v3/subscriptions/{id}
  GET /v3/subscriptions/{id}/payments · GET /v3/payments/{id}
Criar a assinatura gera a primeira cobrança (PENDING), com `invoiceUrl` apontando para uma página simples daqui
(`/fatura/{id}`, com botões para pagar). Para simular o resto do Asaas (cada um manda o webhook, com o cabeçalho
`asaas-access-token`, para ASAAS_FALSO_WEBHOOK_URL):
  POST /simular/pagar/{payment_id}?forma=PIX|BOLETO|CREDIT_CARD   RECEIVED (cartão: CONFIRMED) + PAYMENT_RECEIVED/…
  POST /simular/vencer/{payment_id}                               OVERDUE + PAYMENT_OVERDUE
  POST /simular/estornar/{payment_id}                             REFUNDED + PAYMENT_REFUNDED
  POST /simular/proxima/{subscription_id}                         cobrança do mês seguinte + PAYMENT_CREATED
  POST /simular/inativar/{subscription_id}?status=INACTIVE|EXPIRED assinatura sem gerar cobranças (sem aviso)
  POST /simular/reenviar/{evento_id}                              manda de novo um evento já enviado (repetido)
  GET  /simular/estado                                            clientes, assinaturas, cobranças e eventos

Rodar (na pasta api/; precisa de fastapi, uvicorn e httpx, já no requirements.txt):
  ASAAS_FALSO_WEBHOOK_TOKEN=<o ASAAS_WEBHOOK_TOKEN da API> python scripts/asaas_falso.py
Porta 8010 (ASAAS_FALSO_PORTA muda). ASAAS_FALSO_WEBHOOK_URL: padrão http://localhost:8000/api/v1/asaas/webhook.
ASAAS_FALSO_URL: endereço deste servidor nos links das faturas (padrão http://localhost:8010).
Na API: ASAAS_URL=http://localhost:8010/v3, ASAAS_API_KEY=<qualquer texto> e o mesmo ASAAS_WEBHOOK_TOKEN.
"""
import calendar
import html
import itertools
import os
import re
import secrets
from collections.abc import Callable
from datetime import date, datetime

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

FORMAS = ("PIX", "BOLETO", "CREDIT_CARD")


def _erro(status: int, codigo: str, descricao: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"errors": [{"code": codigo, "description": descricao}]})


def _pagina(lista: list, offset: int, limit: int) -> dict:
    limit = max(1, min(limit, 100))
    return {"object": "list", "hasMore": offset + limit < len(lista), "totalCount": len(lista), "limit": limit,
            "offset": offset, "data": lista[offset:offset + limit]}


def _mais_um_mes(d: date) -> date:
    ano, mes = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def enviar_webhook(url: str, token: str, corpo: dict) -> int | None:
    """POST do aviso para a API (status HTTP; None se não conectou)."""
    try:
        return httpx.post(url, json=corpo, headers={"asaas-access-token": token}, timeout=10).status_code
    except httpx.HTTPError:
        return None


def criar_app(webhook_url: str | None = None, webhook_token: str | None = None, url_publica: str | None = None,
              enviar: Callable[[str, str, dict], int | None] | None = None,
              hoje: Callable[[], date] = date.today) -> FastAPI:
    """App com estado novo. `enviar(url, token, corpo)` troca o envio dos webhooks (o teste integrado guarda numa
    lista); `hoje` é o dia usado para recusar vencimento no passado e marcar pagamentos."""
    webhook_url = webhook_url or os.environ.get("ASAAS_FALSO_WEBHOOK_URL", "http://localhost:8000/api/v1/asaas/webhook")
    webhook_token = webhook_token if webhook_token is not None else (
        os.environ.get("ASAAS_FALSO_WEBHOOK_TOKEN") or os.environ.get("ASAAS_WEBHOOK_TOKEN", ""))
    url_publica = (url_publica or os.environ.get("ASAAS_FALSO_URL", "http://localhost:8010")).rstrip("/")
    enviar = enviar or enviar_webhook
    seq = itertools.count(1)
    clientes: dict[str, dict] = {}
    assinaturas: dict[str, dict] = {}
    cobrancas: dict[str, dict] = {}
    eventos: dict[str, dict] = {}
    app = FastAPI(title="Asaas falso (Toqqi)")
    app.state.dados = {"clientes": clientes, "assinaturas": assinaturas, "cobrancas": cobrancas, "eventos": eventos}

    def novo_id(prefixo: str) -> str:
        """Em ordem e sem repetir entre reinícios (o banco da API guarda os ids de antes)."""
        return f"{prefixo}_{next(seq):04d}_{secrets.token_hex(3)}"

    def agora_texto() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def avisar(evento: str, pagamento: dict) -> dict:
        corpo = {"id": f"evt_{secrets.token_hex(16)}&{next(seq)}", "event": evento, "dateCreated": agora_texto(),
                 "payment": dict(pagamento)}
        eventos[corpo["id"]] = corpo
        status = enviar(webhook_url, webhook_token, corpo) if webhook_token else None
        return {"evento": corpo["id"], "webhook_status": status}

    def nova_cobranca(assinatura: dict, vencimento: date) -> dict:
        pid = novo_id("pay")
        p = {"object": "payment", "id": pid, "dateCreated": hoje().isoformat(), "customer": assinatura["customer"],
             "subscription": assinatura["id"], "value": assinatura["value"],
             "netValue": round(assinatura["value"] - 0.99, 2), "billingType": "UNDEFINED", "status": "PENDING",
             "dueDate": vencimento.isoformat(), "originalDueDate": vencimento.isoformat(), "paymentDate": None,
             "clientPaymentDate": None, "invoiceUrl": f"{url_publica}/fatura/{pid}", "deleted": False,
             "description": assinatura["description"], "externalReference": assinatura["externalReference"]}
        cobrancas[pid] = p
        return p

    @app.middleware("http")
    async def _chave(request: Request, chamar):
        if request.url.path.startswith("/v3/") and not request.headers.get("access_token"):
            return _erro(401, "invalid_access_token", "A chave de API informada não pertence a este ambiente.")
        return await chamar(request)

    # ---- clientes ---------------------------------------------------------------------

    def validar_cliente(corpo: dict) -> JSONResponse | None:
        documento = str(corpo.get("cpfCnpj") or "")
        if not re.fullmatch(r"[0-9]{11}|[0-9A-Z]{12}[0-9]{2}", documento):  # CPF ou CNPJ (também o alfanumérico)
            return _erro(400, "invalid_cpfCnpj", "O CPF/CNPJ informado é inválido.")
        if "@" not in str(corpo.get("email") or ""):
            return _erro(400, "invalid_email", "O email informado é inválido.")
        telefone = re.sub(r"\D", "", str(corpo.get("mobilePhone") or corpo.get("phone") or ""))
        if len(telefone) not in (10, 11):
            return _erro(400, "invalid_mobilePhone", "O celular informado é inválido.")
        if not str(corpo.get("name") or "").strip():
            return _erro(400, "invalid_name", "O nome do cliente deve ser informado.")
        return None

    @app.get("/v3/customers")
    def listar_clientes(externalReference: str | None = None, offset: int = 0, limit: int = 10):  # noqa: N803
        lista = [c for c in clientes.values() if not c.get("deleted")
                 and (externalReference is None or c.get("externalReference") == externalReference)]
        return _pagina(lista, offset, limit)

    @app.get("/v3/customers/{cid}")
    def obter_cliente(cid: str):
        if cid not in clientes:
            return _erro(404, "not_found", "Cliente não encontrado.")
        return clientes[cid]

    @app.post("/v3/customers")
    def criar_cliente(corpo: dict):
        if (erro := validar_cliente(corpo)) is not None:
            return erro
        cid = novo_id("cus")
        clientes[cid] = {"object": "customer", "id": cid, "deleted": False, **corpo}
        return clientes[cid]

    @app.put("/v3/customers/{cid}")
    def atualizar_cliente(cid: str, corpo: dict):
        if cid not in clientes:
            return _erro(404, "not_found", "Cliente não encontrado.")
        if (erro := validar_cliente({**clientes[cid], **corpo})) is not None:
            return erro
        clientes[cid].update(corpo)
        return clientes[cid]

    # ---- assinaturas ------------------------------------------------------------------

    @app.get("/v3/subscriptions")
    def listar_assinaturas(externalReference: str | None = None, customer: str | None = None,  # noqa: N803
                           includeDeleted: bool = False, offset: int = 0, limit: int = 10):  # noqa: N803
        lista = [a for a in assinaturas.values() if (includeDeleted or not a["deleted"])
                 and (externalReference is None or a.get("externalReference") == externalReference)
                 and (customer is None or a["customer"] == customer)]
        return _pagina(lista, offset, limit)

    @app.post("/v3/subscriptions")
    def criar_assinatura(corpo: dict):
        if corpo.get("customer") not in clientes:
            return _erro(400, "invalid_customer", "Cliente inválido ou não informado.")
        try:
            vencimento = date.fromisoformat(str(corpo.get("nextDueDate")))
        except ValueError:
            return _erro(400, "invalid_nextDueDate", "A data de vencimento é inválida.")
        if vencimento < hoje():
            return _erro(400, "invalid_nextDueDate", "A data de vencimento não pode ser anterior a hoje.")
        if not isinstance(corpo.get("value"), (int, float)) or corpo["value"] <= 0:
            return _erro(400, "invalid_value", "O valor da assinatura é inválido.")
        sid = novo_id("sub")
        assinaturas[sid] = {"object": "subscription", "id": sid, "dateCreated": hoje().isoformat(),
                            "status": "ACTIVE", "deleted": False,
                            "customer": corpo["customer"], "billingType": corpo.get("billingType", "UNDEFINED"),
                            "value": float(corpo["value"]), "nextDueDate": vencimento.isoformat(),
                            "cycle": corpo.get("cycle", "MONTHLY"), "description": corpo.get("description", ""),
                            "externalReference": corpo.get("externalReference")}
        nova_cobranca(assinaturas[sid], vencimento)
        return assinaturas[sid]

    @app.get("/v3/subscriptions/{sid}")
    def obter_assinatura(sid: str):
        if sid not in assinaturas:
            return _erro(404, "not_found", "Assinatura não encontrada.")
        return assinaturas[sid]

    @app.put("/v3/subscriptions/{sid}")
    def atualizar_assinatura(sid: str, corpo: dict):
        a = assinaturas.get(sid)
        if a is None or a["deleted"]:
            return _erro(404, "not_found", "Assinatura não encontrada.")
        for campo in ("value", "description"):
            if campo in corpo:
                a[campo] = corpo[campo]
        if corpo.get("updatePendingPayments"):
            for p in cobrancas.values():
                if p["subscription"] == sid and p["status"] == "PENDING" and not p["deleted"]:
                    p["value"], p["netValue"] = a["value"], round(a["value"] - 0.99, 2)
                    p["description"] = a["description"]
        return a

    @app.delete("/v3/subscriptions/{sid}")
    def remover_assinatura(sid: str):
        a = assinaturas.get(sid)
        if a is None or a["deleted"]:
            return _erro(404, "not_found", "Assinatura não encontrada.")
        a["deleted"], a["status"] = True, "INACTIVE"
        for p in cobrancas.values():  # o Asaas apaga junto as pendentes e vencidas
            if p["subscription"] == sid and p["status"] in ("PENDING", "OVERDUE"):
                p["deleted"] = True
        return {"deleted": True, "id": sid}

    @app.get("/v3/subscriptions/{sid}/payments")
    def cobrancas_da_assinatura(sid: str, offset: int = 0, limit: int = 10):
        if sid not in assinaturas:
            return _erro(404, "not_found", "Assinatura não encontrada.")
        lista = sorted((p for p in cobrancas.values() if p["subscription"] == sid and not p["deleted"]),
                       key=lambda p: (p["dueDate"], p["id"]), reverse=True)
        return _pagina(lista, offset, limit)

    @app.get("/v3/payments/{pid}")
    def obter_cobranca(pid: str):
        if pid not in cobrancas:
            return _erro(404, "not_found", "Cobrança não encontrada.")
        return cobrancas[pid]

    # ---- simulações ----------------------------------------------------------------------

    def cobranca_ou_404(pid: str) -> dict | JSONResponse:
        p = cobrancas.get(pid)
        return p if p is not None and not p["deleted"] else _erro(404, "not_found", "Cobrança não encontrada.")

    @app.post("/simular/pagar/{pid}")
    def pagar(pid: str, forma: str = "PIX", voltar: bool = False):
        p = cobranca_ou_404(pid)
        if isinstance(p, JSONResponse):
            return p
        forma = forma.upper()
        if forma not in FORMAS:
            return _erro(400, "invalid_billingType", f"Use uma destas formas: {', '.join(FORMAS)}.")
        p.update(billingType=forma, status="CONFIRMED" if forma == "CREDIT_CARD" else "RECEIVED",
                 paymentDate=hoje().isoformat(), clientPaymentDate=hoje().isoformat())
        resultado = avisar("PAYMENT_CONFIRMED" if forma == "CREDIT_CARD" else "PAYMENT_RECEIVED", p)
        return RedirectResponse(f"/fatura/{pid}", status_code=303) if voltar else {"cobranca": p, **resultado}

    @app.post("/simular/vencer/{pid}")
    def vencer(pid: str):
        p = cobranca_ou_404(pid)
        if isinstance(p, JSONResponse):
            return p
        p["status"] = "OVERDUE"
        return {"cobranca": p, **avisar("PAYMENT_OVERDUE", p)}

    @app.post("/simular/estornar/{pid}")
    def estornar(pid: str):
        p = cobranca_ou_404(pid)
        if isinstance(p, JSONResponse):
            return p
        p["status"] = "REFUNDED"
        return {"cobranca": p, **avisar("PAYMENT_REFUNDED", p)}

    @app.post("/simular/proxima/{sid}")
    def proxima(sid: str):
        a = assinaturas.get(sid)
        if a is None or a["deleted"]:
            return _erro(404, "not_found", "Assinatura não encontrada.")
        ultima = max(date.fromisoformat(p["dueDate"]) for p in cobrancas.values() if p["subscription"] == sid)
        p = nova_cobranca(a, _mais_um_mes(ultima))
        a["nextDueDate"] = p["dueDate"]
        return {"cobranca": p, **avisar("PAYMENT_CREATED", p)}

    @app.post("/simular/inativar/{sid}")
    def inativar(sid: str, status: str = "INACTIVE"):
        a = assinaturas.get(sid)
        if a is None or a["deleted"]:
            return _erro(404, "not_found", "Assinatura não encontrada.")
        if status not in ("INACTIVE", "EXPIRED"):
            return _erro(400, "invalid_status", "Use INACTIVE ou EXPIRED.")
        a["status"] = status
        return a

    @app.post("/simular/reenviar/{evento_id}")
    def reenviar(evento_id: str):
        corpo = eventos.get(evento_id)
        if corpo is None:
            return _erro(404, "not_found", "Evento não encontrado.")
        return {"evento": evento_id, "webhook_status": enviar(webhook_url, webhook_token, corpo)}

    @app.get("/simular/estado")
    def estado():
        return app.state.dados

    @app.get("/fatura/{pid}", response_class=HTMLResponse)
    def fatura(pid: str):
        p = cobrancas.get(pid)
        if p is None:
            return HTMLResponse("<h1>Fatura não encontrada</h1>", status_code=404)
        botoes = "".join(
            f'<button formaction="/simular/pagar/{html.escape(pid)}?forma={f}&voltar=true">{rotulo}</button> '
            for f, rotulo in (("PIX", "Pagar com Pix"), ("BOLETO", "Pagar com boleto"),
                              ("CREDIT_CARD", "Pagar com cartão")))
        pagar_ = (f'<form method="post">{botoes}</form>' if p["status"] in ("PENDING", "OVERDUE") and not p["deleted"]
                  else "")
        valor = f"R$ {p['value']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return (f"<!doctype html><meta charset='utf-8'><title>Fatura {html.escape(pid)}</title>"
                f"<body style='font-family:sans-serif;max-width:32rem;margin:2rem auto'>"
                f"<p><small>Asaas falso · ambiente de desenvolvimento</small></p>"
                f"<h1>{html.escape(str(p['description'] or 'Fatura'))}</h1>"
                f"<p>Valor: <b>{valor}</b><br>Vencimento: {html.escape(p['dueDate'])}<br>"
                f"Situação: <b>{html.escape(p['status'])}</b>{' (removida)' if p['deleted'] else ''}</p>{pagar_}")

    return app


app = criar_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("ASAAS_FALSO_PORTA", "8010")))
