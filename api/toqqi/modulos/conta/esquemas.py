import re
from typing import Annotated
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, BeforeValidator, Field
from pydantic_core import PydanticCustomError

from toqqi.core.validacao import Documento, EmailOpcional, Telefone, TextoAte, dominio_valido


class SegurancaIn(BaseModel):
    sessao_minutos: Annotated[int, Field(ge=30, le=1440)]
    dominios: list[Annotated[str, Field(max_length=253)]] = Field(default_factory=list, max_length=50)


# ---- dados da empresa -----------------------------------------------------------

UFS = ("AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
       "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO")
MSG_NOME = "Informe o nome da empresa."
MSG_SITE = "Informe um site válido, como www.suaempresa.com.br."
MSG_CEP = "Informe o CEP com 8 números, como 01310-100."
MSG_UF = "Escolha um estado (UF) da lista."
MAX_NOME = 120
MAX_SITE = 200


def _erro(tipo: str, msg: str) -> PydanticCustomError:
    return PydanticCustomError(f"toqqi_{tipo}", msg)


def _vazio(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _nome(v):
    v = v.strip() if isinstance(v, str) else v
    if not isinstance(v, str) or len(v) < 2:
        raise _erro("nome", MSG_NOME)
    if len(v) > MAX_NOME:
        raise _erro("nome", f"Use no máximo {MAX_NOME} caracteres.")
    return v


def _host_valido(host: str) -> bool:
    try:
        ascii_ = host.encode("idna").decode("ascii")  # aceita domínios com acento (açaí.com.br)
    except UnicodeError:
        return False
    return dominio_valido(ascii_)


def _site(v):
    """Sem esquema vira https://; só http/https, domínio com ponto, sem usuário/senha, até 200 caracteres."""
    if _vazio(v):
        return None
    if not isinstance(v, str) or re.search(r"\s", v.strip()):
        raise _erro("site", MSG_SITE)
    v = v.strip()
    if "://" not in v:
        v = "https://" + v
    try:
        partes = urlsplit(v)
        _ = partes.port  # porta inválida levanta ValueError
    except ValueError:
        raise _erro("site", MSG_SITE)
    esquema = partes.scheme.lower()
    host = partes.hostname or ""
    if esquema not in ("http", "https") or partes.username or partes.password or not _host_valido(host):
        raise _erro("site", MSG_SITE)
    v = urlunsplit((esquema, partes.netloc.lower(), partes.path, partes.query, partes.fragment))
    if len(v) > MAX_SITE:
        raise _erro("site", MSG_SITE)
    return v


def _cep(v):
    if _vazio(v):
        return None
    d = re.sub(r"[\s.-]", "", v) if isinstance(v, str) else ""
    if not re.fullmatch(r"[0-9]{8}", d):
        raise _erro("cep", MSG_CEP)
    return d


def _uf(v):
    if _vazio(v):
        return None
    sigla = v.strip().upper() if isinstance(v, str) else ""
    if sigla not in UFS:
        raise _erro("uf", MSG_UF)
    return sigla


class DadosEmpresaIn(BaseModel):
    """PUT /conta/dados: todos os campos de texto (os opcionais vazios ou nulos ficam sem valor)."""
    nome: Annotated[str | None, BeforeValidator(_nome), Field(validate_default=True)] = None
    razao_social: TextoAte(200) = None
    documento: Documento = None
    telefone: Telefone = None
    email_contato: EmailOpcional = None
    site: Annotated[str | None, BeforeValidator(_site)] = None
    cep: Annotated[str | None, BeforeValidator(_cep)] = None
    logradouro: TextoAte(150) = None
    numero: TextoAte(20) = None
    complemento: TextoAte(80) = None
    bairro: TextoAte(80) = None
    cidade: TextoAte(80) = None
    uf: Annotated[str | None, BeforeValidator(_uf)] = None
