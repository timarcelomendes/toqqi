"""Cliente da API v1 do Pipedrive (https://api.pipedrive.com/v1), com o token de API pessoal do cliente no cabeçalho
`x-api-token`. Só o que o conector usa: conferir o token, listar organizações e pessoas (páginas de 500), as pessoas de
um negócio, cadastrar/remover o webhook de negócios (versão 2.0) e anotar no negócio. A leitura dos campos é tolerante
(e-mail e telefone vêm em lista de {value, primary}; `org_id` vem como número ou como {value, name})."""
import httpx

BASE = "https://api.pipedrive.com/v1"
TEMPO = httpx.Timeout(20.0, connect=10.0)
POR_PAGINA = 500


class ErroPipedrive(Exception):
    """Falha ao falar com o Pipedrive (mensagem pronta para a tela)."""


def _pedir(metodo: str, caminho: str, token: str, params: dict | None = None, json: dict | None = None) -> dict:
    try:
        r = httpx.request(metodo, f"{BASE}{caminho}", params=params, json=json, timeout=TEMPO,
                          headers={"x-api-token": token, "Accept": "application/json"})
    except httpx.TimeoutException:
        raise ErroPipedrive("O Pipedrive demorou para responder. Tente de novo em instantes.")
    except httpx.HTTPError:
        raise ErroPipedrive("Não conseguimos falar com o Pipedrive. Tente de novo em instantes.")
    if r.status_code in (401, 403):
        raise ErroPipedrive("O Pipedrive recusou o token. Confira o token de API (Configurações pessoais › API).")
    if r.status_code == 429:
        raise ErroPipedrive("O Pipedrive pediu uma pausa (limite de pedidos). Tente de novo em 1 minuto.")
    if r.status_code == 404:
        raise ErroPipedrive("O Pipedrive não encontrou o que pedimos.")
    if r.status_code >= 400:
        raise ErroPipedrive(f"O Pipedrive respondeu com erro ({r.status_code}).")
    try:
        dados = r.json() if r.content else {}
    except ValueError:
        raise ErroPipedrive("O Pipedrive respondeu num formato inesperado.")
    if isinstance(dados, dict) and dados.get("success") is False:
        raise ErroPipedrive(str(dados.get("error") or "O Pipedrive recusou o pedido.")[:200])
    return dados if isinstance(dados, dict) else {}


def conferir_token(token: str) -> None:
    _pedir("GET", "/users/me", token)


def _paginas(caminho: str, token: str, maximo: int):
    inicio, total = 0, 0
    while total < maximo:
        dados = _pedir("GET", caminho, token, {"start": inicio, "limit": POR_PAGINA})
        itens = dados.get("data") or []
        for item in itens:
            if isinstance(item, dict):
                yield item
                total += 1
                if total >= maximo:
                    return
        pag = ((dados.get("additional_data") or {}).get("pagination") or {})
        if not itens or not pag.get("more_items_in_collection"):
            return
        inicio = pag.get("next_start") or inicio + len(itens)


def empresas(token: str, maximo: int):
    for o in _paginas("/organizations", token, maximo):
        yield {"id": ident(o), "nome": o.get("name")}


def contatos(token: str, maximo: int):
    for p in _paginas("/persons", token, maximo):
        yield pessoa(p)


def pessoas_do_negocio(token: str, deal_id: str) -> list[dict]:
    dados = _pedir("GET", f"/deals/{deal_id}/persons", token)
    return [pessoa(p) for p in (dados.get("data") or []) if isinstance(p, dict)]


def uma_pessoa(token: str, person_id: str) -> dict | None:
    dados = _pedir("GET", f"/persons/{person_id}", token).get("data")
    return pessoa(dados) if isinstance(dados, dict) else None


def organizacao(token: str, org_id: str) -> dict | None:
    dados = _pedir("GET", f"/organizations/{org_id}", token).get("data")
    return {"id": ident(dados), "nome": dados.get("name")} if isinstance(dados, dict) else None


def criar_webhook(token: str, url: str) -> str | None:
    dados = _pedir("POST", "/webhooks", token, json={"subscription_url": url, "event_action": "change",
                                                     "event_object": "deal", "version": "2.0", "name": "Toqqi"})
    d = dados.get("data") or {}
    return str(d.get("id") or "") or None


def remover_webhook(token: str, webhook_id: str) -> None:
    _pedir("DELETE", f"/webhooks/{webhook_id}", token)


def anotar(token: str, deal_id: str, texto: str) -> None:
    _pedir("POST", "/notes", token, json={"content": texto, "deal_id": int(deal_id) if deal_id.isdigit() else deal_id})


# ---- leitura dos campos ---------------------------------------------------------------------

def ident(item) -> str | None:
    if isinstance(item, dict):
        item = item.get("value", item.get("id"))
    return str(item) if item not in (None, "", 0) else None


def primeiro(lista) -> str | None:
    """O principal (primary) da lista de {value, primary}; senão o primeiro com valor. Aceita texto solto."""
    if isinstance(lista, str):
        return lista.strip() or None
    itens = [x for x in (lista or []) if isinstance(x, dict) and str(x.get("value") or "").strip()]
    itens.sort(key=lambda x: not x.get("primary"))
    return str(itens[0]["value"]).strip() if itens else None


def pessoa(p: dict) -> dict:
    org = p.get("org_id")
    return {"id": ident(p.get("id")), "nome": p.get("name"),
            "email": primeiro(p.get("emails") or p.get("email")), "telefone": primeiro(p.get("phones") or p.get("phone")),
            "empresa_id": ident(org), "empresa_nome": org.get("name") if isinstance(org, dict) else None}


def negocio_do_aviso(corpo: dict) -> tuple[dict, dict] | None:
    """(negócio atual, valores anteriores) do aviso de negócio, nas versões 2.0 (`data`/`previous`) e 1.0
    (`current`/`previous`). None se o aviso não é de negócio alterado."""
    if not isinstance(corpo, dict):
        return None
    meta = corpo.get("meta") or {}
    entidade = meta.get("entity") or meta.get("object")
    if entidade and entidade != "deal":
        return None
    atual = corpo.get("data") if isinstance(corpo.get("data"), dict) else corpo.get("current")
    if not isinstance(atual, dict):
        return None
    anterior = corpo.get("previous") if isinstance(corpo.get("previous"), dict) else {}
    return atual, anterior


def acabou_de_ganhar(atual: dict, anterior: dict) -> bool:
    """O aviso é da passagem para ganho: status "won" agora e outro antes (a versão 2.0 manda em `previous` só os
    campos que mudaram; sem `status` lá, o status não mudou neste aviso)."""
    if str(atual.get("status") or "").lower() != "won":
        return False
    return "status" in anterior and str(anterior.get("status") or "").lower() != "won"
