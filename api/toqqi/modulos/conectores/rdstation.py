"""Cliente da API v1 do RD Station CRM (https://crm.rdstation.com/api/v1), com o token de instância do cliente na
consulta (`?token=`). Só o que o conector usa: conferir o token, listar empresas e contatos (páginas de 200), ler uma
negociação e cadastrar/remover o webhook. A leitura dos campos é tolerante (o RD usa `id` ou `_id`, e o valor mensal
da negociação já veio como `amount_montly`)."""
import httpx

BASE = "https://crm.rdstation.com/api/v1"
TEMPO = httpx.Timeout(20.0, connect=10.0)
POR_PAGINA = 200


class ErroRd(Exception):
    """Falha ao falar com o RD (mensagem pronta para a tela)."""


def _pedir(metodo: str, caminho: str, token: str, params: dict | None = None, json: dict | None = None) -> dict:
    try:
        r = httpx.request(metodo, f"{BASE}{caminho}", params={"token": token, **(params or {})}, json=json,
                          timeout=TEMPO)
    except httpx.TimeoutException:
        raise ErroRd("O RD Station CRM demorou para responder. Tente de novo em instantes.")
    except httpx.HTTPError:
        raise ErroRd("Não conseguimos falar com o RD Station CRM. Tente de novo em instantes.")
    if r.status_code in (401, 403):
        raise ErroRd("O RD Station CRM recusou o token. Confira o token de instância (Perfil › Token de instância).")
    if r.status_code == 429:
        raise ErroRd("O RD Station CRM pediu uma pausa (limite de 120 pedidos por minuto). Tente de novo em 1 minuto.")
    if r.status_code >= 400:
        raise ErroRd(f"O RD Station CRM respondeu com erro ({r.status_code}).")
    try:
        return r.json() if r.content else {}
    except ValueError:
        raise ErroRd("O RD Station CRM respondeu num formato inesperado.")


def conferir_token(token: str) -> None:
    _pedir("GET", "/token/check", token)


def _paginas(caminho: str, chave: str, token: str, maximo: int):
    pagina, total = 1, 0
    while total < maximo:
        dados = _pedir("GET", caminho, token, {"page": pagina, "limit": POR_PAGINA})
        itens = dados.get(chave) or []
        for item in itens:
            yield item
            total += 1
            if total >= maximo:
                return
        if not itens or not dados.get("has_more"):
            return
        pagina += 1


def empresas(token: str, maximo: int):
    return _paginas("/organizations", "organizations", token, maximo)


def contatos(token: str, maximo: int):
    return _paginas("/contacts", "contacts", token, maximo)


def negociacao(token: str, deal_id: str) -> dict:
    return _pedir("GET", f"/deals/{deal_id}", token)


def anotar(token: str, deal_id: str, texto: str) -> None:
    """Anotação na negociação (POST /activities; o RD pede o autor: o dono da negociação ou o primeiro usuário)."""
    deal = negociacao(token, deal_id)
    dono = deal.get("user") if isinstance(deal.get("user"), dict) else {}
    autor = ident(dono) if dono else None
    if not autor:
        usuarios = _pedir("GET", "/users", token).get("users") or []
        autor = ident(usuarios[0]) if usuarios and isinstance(usuarios[0], dict) else None
    if not autor:
        raise ErroRd("O RD Station CRM não informou um usuário para a anotação.")
    _pedir("POST", "/activities", token, json={"activity": {"deal_id": deal_id, "user_id": autor, "text": texto}})


def criar_webhook(token: str, url: str) -> str | None:
    dados = _pedir("POST", "/webhooks", token, json={"event_type": "crm_deal_updated", "url": url,
                                                      "http_method": "POST"})
    return str(dados.get("uuid") or dados.get("id") or dados.get("_id") or "") or None


def remover_webhook(token: str, webhook_id: str) -> None:
    _pedir("DELETE", f"/webhooks/{webhook_id}", token)


# ---- leitura dos campos ---------------------------------------------------------------------

def ident(item: dict) -> str | None:
    v = item.get("id") or item.get("_id")
    return str(v) if v else None


def primeiro(lista, campo: str) -> str | None:
    for x in lista or []:
        v = (x or {}).get(campo) if isinstance(x, dict) else x
        if v:
            return str(v).strip()
    return None


def ganha(deal: dict) -> bool:
    return deal.get("win") is True or str(deal.get("status") or "").lower() == "won"


def valor_mensal(deal: dict):
    for campo in ("amount_monthly", "amount_montly"):
        if deal.get(campo):
            return deal[campo]
    return None
