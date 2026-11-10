"""Cliente da API do HubSpot (https://api.hubapi.com), com a chave de serviço do cliente (Bearer; Development › Keys ›
Service keys). Desde 26/10/2026 o HubSpot não deixa criar aplicativos privados novos; o token de um aplicativo privado
que já existe também funciona. Escopos que o conector pede: `crm.objects.contacts.read`,
`crm.objects.companies.read` e `crm.objects.deals.read`.

A chave de serviço não recebe webhooks (só chamadas à API), então o negócio ganho é consultado pela tarefa
`conectores` (a cada rodada, os negócios ganhos alterados desde a última consulta)."""
from datetime import datetime

import httpx

BASE = "https://api.hubapi.com"
TEMPO = httpx.Timeout(20.0, connect=10.0)
POR_PAGINA = 100
PROPRIEDADES_CONTATO = ["email", "firstname", "lastname", "phone", "mobilephone"]


class ErroHubspot(Exception):
    """Falha ao falar com o HubSpot (mensagem pronta para a tela)."""


def _pedir(metodo: str, caminho: str, token: str, params: dict | None = None, json: dict | None = None) -> dict:
    try:
        r = httpx.request(metodo, f"{BASE}{caminho}", params=params, json=json, timeout=TEMPO,
                          headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    except httpx.TimeoutException:
        raise ErroHubspot("O HubSpot demorou para responder. Tente de novo em instantes.")
    except httpx.HTTPError:
        raise ErroHubspot("Não conseguimos falar com o HubSpot. Tente de novo em instantes.")
    if r.status_code == 401:
        raise ErroHubspot("O HubSpot recusou a chave. Confira a chave de serviço (Development › Keys › Service keys).")
    if r.status_code == 403:
        raise ErroHubspot("A chave do HubSpot não tem os escopos necessários: leitura de contatos, empresas e "
                          "negócios (crm.objects.contacts.read, crm.objects.companies.read e crm.objects.deals.read).")
    if r.status_code == 429:
        raise ErroHubspot("O HubSpot pediu uma pausa (limite de pedidos). Tente de novo em 1 minuto.")
    if r.status_code >= 400:
        raise ErroHubspot(f"O HubSpot respondeu com erro ({r.status_code}).")
    try:
        dados = r.json() if r.content else {}
    except ValueError:
        raise ErroHubspot("O HubSpot respondeu num formato inesperado.")
    return dados if isinstance(dados, dict) else {}


def conferir_token(token: str) -> None:
    """Lê 1 contato, 1 empresa e 1 negócio: confere o token e os três escopos de uma vez."""
    for objeto in ("contacts", "companies", "deals"):
        _pedir("GET", f"/crm/v3/objects/{objeto}", token, {"limit": 1})


def _paginas(objeto: str, token: str, maximo: int, params: dict):
    depois, total = None, 0
    while total < maximo:
        dados = _pedir("GET", f"/crm/v3/objects/{objeto}", token,
                       {**params, "limit": POR_PAGINA, **({"after": depois} if depois else {})})
        itens = dados.get("results") or []
        for item in itens:
            if isinstance(item, dict):
                yield item
                total += 1
                if total >= maximo:
                    return
        depois = (((dados.get("paging") or {}).get("next") or {}).get("after"))
        if not itens or not depois:
            return


def empresas(token: str, maximo: int):
    for c in _paginas("companies", token, maximo, {"properties": "name"}):
        yield {"id": str(c.get("id") or "") or None, "nome": (c.get("properties") or {}).get("name")}


def contatos(token: str, maximo: int):
    params = {"properties": ",".join(PROPRIEDADES_CONTATO), "associations": "companies"}
    for c in _paginas("contacts", token, maximo, params):
        yield contato(c)


def negocios_ganhos(token: str, desde: datetime, maximo: int = 200) -> list[dict]:
    """Negócios ganhos alterados desde `desde` (e fechados nos 7 dias antes de `desde` ou depois), do mais antigo para
    o mais novo: [{id, nome, alterado_em (ms)}]."""
    ms = int(desde.timestamp() * 1000)
    corpo = {"filterGroups": [{"filters": [
        {"propertyName": "hs_is_closed_won", "operator": "EQ", "value": "true"},
        {"propertyName": "hs_lastmodifieddate", "operator": "GTE", "value": str(ms)},
        {"propertyName": "closedate", "operator": "GTE", "value": str(ms - 7 * 24 * 3600 * 1000)}]}],
        "properties": ["dealname", "hs_lastmodifieddate"],
        "sorts": [{"propertyName": "hs_lastmodifieddate", "direction": "ASCENDING"}], "limit": 100}
    itens, depois = [], None
    while len(itens) < maximo:
        dados = _pedir("POST", "/crm/v3/objects/deals/search", token, json={**corpo, **({"after": depois} if depois else {})})
        for d in dados.get("results") or []:
            p = d.get("properties") or {}
            itens.append({"id": str(d.get("id")), "nome": p.get("dealname"), "alterado_em": _ms(p.get("hs_lastmodifieddate"))})
        depois = (((dados.get("paging") or {}).get("next") or {}).get("after"))
        if not depois:
            break
    return itens[:maximo]


def _associados(token: str, deal_id: str, para: str) -> list[str]:
    dados = _pedir("GET", f"/crm/v4/objects/deals/{deal_id}/associations/{para}", token, {"limit": 100})
    return [str(x.get("toObjectId")) for x in dados.get("results") or [] if isinstance(x, dict) and x.get("toObjectId")]


def contatos_do_negocio(token: str, deal_id: str, maximo: int) -> tuple[list[dict], dict | None]:
    """(contatos do negócio, a empresa do negócio {id, nome} ou None)."""
    ids = _associados(token, deal_id, "contacts")[:maximo]
    pessoas = []
    if ids:
        dados = _pedir("POST", "/crm/v3/objects/contacts/batch/read", token,
                       json={"properties": PROPRIEDADES_CONTATO, "inputs": [{"id": i} for i in ids]})
        pessoas = [contato(c) for c in dados.get("results") or [] if isinstance(c, dict)]
    empresa = None
    empresas_ids = _associados(token, deal_id, "companies")
    if empresas_ids:
        c = _pedir("GET", f"/crm/v3/objects/companies/{empresas_ids[0]}", token, {"properties": "name"})
        empresa = {"id": empresas_ids[0], "nome": (c.get("properties") or {}).get("name")}
    return pessoas, empresa


# ---- leitura dos campos ---------------------------------------------------------------------

def _ms(v) -> int | None:
    """hs_lastmodifieddate vem em ISO 8601 (ou em milissegundos, em contas antigas)."""
    if v is None:
        return None
    texto = str(v)
    if texto.isdigit():
        return int(texto)
    try:
        return int(datetime.fromisoformat(texto.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def contato(c: dict) -> dict:
    p = c.get("properties") or {}
    nome = " ".join(x for x in (p.get("firstname"), p.get("lastname")) if x and str(x).strip()) or None
    empresas_ = (((c.get("associations") or {}).get("companies") or {}).get("results") or [])
    empresa_id = next((str(x.get("id")) for x in empresas_ if isinstance(x, dict) and x.get("id")), None)
    return {"id": str(c.get("id") or "") or None, "nome": nome, "email": (p.get("email") or "").strip() or None,
            "telefone": (p.get("mobilephone") or p.get("phone") or "").strip() or None, "empresa_id": empresa_id,
            "empresa_nome": None}
