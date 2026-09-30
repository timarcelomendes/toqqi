"""Convites individuais para responder uma pesquisa (link com token de uso único).

O token só existe no link: no banco fica apenas o sha256 dele.
"""
from sqlalchemy.orm import Session

from toqqi.core.config import config
from toqqi.core.security import novo_token_uso_unico
from toqqi.modelos import Contato, Convite

CANAIS_CONVITE = ("email", "whatsapp", "link_manual")
# canal do convite → canal gravado na resposta
CANAL_RESPOSTA = {"email": "email", "whatsapp": "whatsapp", "link_manual": "link"}
CHAVES_CONTEXTO = ("pedido", "nota_fiscal", "rota", "motorista", "filial", "transportadora")
MAX_CONTEXTO = 120


def limpar_contexto(contexto: dict | None) -> dict:
    """Só as chaves conhecidas, como texto de até 120 caracteres; vazias são descartadas."""
    saida = {}
    for k in CHAVES_CONTEXTO:
        v = (contexto or {}).get(k)
        if v is None or isinstance(v, (dict, list)):
            continue
        v = str(v).strip()[:MAX_CONTEXTO]
        if v:
            saida[k] = v
    return saida


def link_do_convite(token: str) -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}/r/{token}"


def criar_convite(
    s: Session,
    formulario_id: int,
    contato_id: int | None = None,
    canal: str = "link_manual",
    assunto: str | None = None,
    referencia: str | None = None,
    contexto: dict | None = None,
    empresa_id: int | None = None,
) -> str:
    """Cria o convite na conta da transação e devolve o token (mostrado só agora)."""
    assert canal in CANAIS_CONVITE
    if contato_id is not None and empresa_id is None:
        c = s.get(Contato, contato_id)
        empresa_id = c.empresa_id if c else None
    token, h = novo_token_uso_unico()
    s.add(Convite(token_hash=h, formulario_id=formulario_id, contato_id=contato_id, empresa_id=empresa_id,
                  canal=canal, assunto=(assunto or None), referencia=(referencia or None),
                  contexto=limpar_contexto(contexto)))
    s.flush()
    return token
