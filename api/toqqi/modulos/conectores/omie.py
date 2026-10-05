"""Cliente da API do Omie (POST JSON em https://app.omie.com.br/api/v1/<grupo>/<recurso>/ com `call`, `app_key`,
`app_secret` e `param`). Só o que o conector usa: conferir as chaves, listar os clientes (páginas de 100) e consultar
um cliente. Os avisos (webhooks) do Omie são cadastrados pelo próprio cliente no portal do desenvolvedor do Omie, com o
endereço que o Toqqi mostra; a leitura do aviso é tolerante ao nome do campo do cliente."""
import re

import httpx

BASE = "https://app.omie.com.br/api/v1"
TEMPO = httpx.Timeout(30.0, connect=10.0)
POR_PAGINA = 100


class ErroOmie(Exception):
    """Falha ao falar com o Omie (mensagem pronta para a tela)."""


def _chamar(caminho: str, call: str, chaves: dict, param: dict) -> dict:
    corpo = {"call": call, "app_key": chaves["app_key"], "app_secret": chaves["app_secret"], "param": [param]}
    try:
        r = httpx.post(f"{BASE}{caminho}", json=corpo, timeout=TEMPO)
    except httpx.TimeoutException:
        raise ErroOmie("O Omie demorou para responder. Tente de novo em instantes.")
    except httpx.HTTPError:
        raise ErroOmie("Não conseguimos falar com o Omie. Tente de novo em instantes.")
    try:
        dados = r.json() if r.content else {}
    except ValueError:
        raise ErroOmie("O Omie respondeu num formato inesperado.")
    falha = dados.get("faultstring") if isinstance(dados, dict) else None
    if r.status_code >= 400 or falha:
        texto = str(falha or "")
        if re.search(r"app_key|app_secret|chave|acesso", texto, re.I):
            raise ErroOmie("O Omie recusou as chaves. Confira o App Key e o App Secret do aplicativo.")
        if "Não existem registros" in texto:
            return {}
        raise ErroOmie(f"O Omie respondeu com erro: {texto[:150] or r.status_code}")
    return dados


def conferir(chaves: dict) -> None:
    _chamar("/geral/clientes/", "ListarClientes", chaves,
            {"pagina": 1, "registros_por_pagina": 1, "apenas_importado_api": "N"})


def clientes(chaves: dict, maximo: int):
    pagina, total = 1, 0
    while total < maximo:
        dados = _chamar("/geral/clientes/", "ListarClientes", chaves,
                        {"pagina": pagina, "registros_por_pagina": POR_PAGINA, "apenas_importado_api": "N"})
        itens = dados.get("clientes_cadastro") or []
        for item in itens:
            yield item
            total += 1
            if total >= maximo:
                return
        if not itens or pagina >= int(dados.get("total_de_paginas") or 1):
            return
        pagina += 1


def cliente(chaves: dict, codigo: str) -> dict:
    return _chamar("/geral/clientes/", "ConsultarCliente", chaves, {"codigo_cliente_omie": int(codigo)})


# ---- leitura dos campos ---------------------------------------------------------------------

def primeiro_email(texto) -> str | None:
    for parte in re.split(r"[;,\s]+", str(texto or "")):
        if "@" in parte:
            return parte.strip().lower()
    return None


def telefone(c: dict) -> str | None:
    numero = re.sub(r"\D", "", f"{c.get('telefone1_ddd') or ''}{c.get('telefone1_numero') or ''}")
    return numero or None


def documento(c: dict) -> str | None:
    d = re.sub(r"[^0-9A-Za-z]", "", str(c.get("cnpj_cpf") or "")).upper()
    return d if len(d) in (11, 14) else None


def nome_empresa(c: dict) -> str | None:
    return (str(c.get("nome_fantasia") or "").strip() or str(c.get("razao_social") or "").strip() or None)


def ativo(c: dict) -> bool:
    return str(c.get("inativo") or "N").upper() != "S"


CAMPOS_CLIENTE = ("idCliente", "codigo_cliente_omie", "codigo_cliente", "nCodCli", "codCliente")


def cliente_do_aviso(evento: dict) -> str | None:
    """O código do cliente no aviso, procurando os nomes que o Omie usa (também dentro de `cabecalho`)."""
    for lugar in (evento, evento.get("cabecalho") or {}, evento.get("pedido") or {}):
        if isinstance(lugar, dict):
            for campo in CAMPOS_CLIENTE:
                if lugar.get(campo):
                    return str(lugar[campo])
    return None


TOPICOS_PESQUISA = ("VendaProduto.Faturada", "NFe.NotaAutorizada", "OrdemServico.Faturada", "NFSe.NotaAutorizada")
