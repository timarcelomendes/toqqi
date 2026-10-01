"""Imagens da conta: o logo da empresa e o logo de cada formulário.

Ficam no banco (tabela `imagens`, uma por uso) e saem sem login em GET /publico/imagens/{chave}. A chave é
aleatória (43 caracteres url-safe): a URL não se adivinha e o conteúdo dela nunca muda. Trocar a imagem apaga a
anterior e grava outra com chave nova, então a URL muda e os caches (navegador, proxy de imagens do Gmail) se
renovam sozinhos. Só PNG ou JPEG, conferidos pelos primeiros bytes (não pela extensão), até 300 KB.

Onde o cliente vê o logo (página da pesquisa e e-mails): o do formulário; sem ele, o da conta (`logo_para_cliente`).
"""
import hashlib
import re
import secrets

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from toqqi.core.config import config
from toqqi.core.db import modo_sistema
from toqqi.core.errors import AppError
from toqqi.modelos import Imagem

LIMITE_BYTES = 300 * 1024  # 307200
MSG_ARQUIVO = "Use uma imagem PNG ou JPG de até 300 KB."
CAMINHO = "/api/v1/publico/imagens/"
CACHE = "public, max-age=31536000, immutable"
_RE_CHAVE = re.compile(r"[A-Za-z0-9_-]{32,128}")
_ASSINATURAS = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"))


# ---- arquivo enviado ----------------------------------------------------------

def tipo_da_imagem(dados: bytes) -> str | None:
    """image/png ou image/jpeg pelos primeiros bytes; None se não for nenhum dos dois."""
    for assinatura, tipo in _ASSINATURAS:
        if dados.startswith(assinatura):
            return tipo
    return None


def ler_envio(arquivo) -> tuple[bytes, str]:
    """(bytes, tipo) do arquivo enviado (multipart `arquivo`), lendo no máximo o limite + 1 byte. Tipo errado,
    arquivo vazio ou grande demais → 422 no campo `arquivo`."""
    dados = arquivo.file.read(LIMITE_BYTES + 1)
    tipo = tipo_da_imagem(dados)
    if tipo is None or len(dados) > LIMITE_BYTES:
        raise AppError(422, "dados_invalidos", MSG_ARQUIVO, {"arquivo": MSG_ARQUIVO})
    return dados, tipo


# ---- URLs ---------------------------------------------------------------------

def prefixo_publico() -> str:
    return config().API_PUBLIC_URL.rstrip("/") + CAMINHO


def url_publica(chave: str) -> str:
    return prefixo_publico() + chave


def chave_da_url(url: str | None) -> str | None:
    """A chave, se `url` é o endereço de uma imagem da plataforma; senão None."""
    prefixo = prefixo_publico()
    if url and url.startswith(prefixo) and _RE_CHAVE.fullmatch(url[len(prefixo):]):
        return url[len(prefixo):]
    return None


def url_aceita_no_tema(url: str) -> bool:
    """Endereço aceito em `tema.logo_url`: https://..., ou imagem da plataforma (com http:// só fora de produção,
    onde a API costuma rodar em http://localhost). `data:` e o resto, não."""
    if url.startswith("https://"):
        return True
    return chave_da_url(url) is not None and config().AMBIENTE != "producao"


# ---- gravação -----------------------------------------------------------------

def gravar(s: Session, uso: str, dados: bytes, tipo: str, conta_id: int, formulario_id: int | None = None) -> str:
    """Troca a imagem do uso (logo da conta ou do formulário): apaga a anterior e grava outra, com chave nova.
    Quem chama trava o dono (conta ou formulário) antes, para duas trocas ao mesmo tempo não colidirem no índice
    único. Devolve a URL pública."""
    dono = Imagem.formulario_id == formulario_id if uso == "logo_formulario" else Imagem.conta_id == conta_id
    s.execute(delete(Imagem).where(Imagem.conta_id == conta_id, Imagem.uso == uso, dono))
    chave = secrets.token_urlsafe(32)
    s.add(Imagem(conta_id=conta_id, uso=uso, formulario_id=formulario_id, chave=chave, tipo=tipo, dados=dados,
                 tamanho=len(dados), sha256=hashlib.sha256(dados).hexdigest()))
    s.flush()
    return url_publica(chave)


def copiar_para_formulario(s: Session, url: str | None, conta_id: int, formulario_id: int) -> str | None:
    """Formulário copiado: se `url` é uma imagem da plataforma desta conta, grava uma cópia como logo do formulário
    novo (chave nova) e devolve a URL dela; senão None (endereço de fora fica como está)."""
    chave = chave_da_url(url)
    if chave is None:
        return None
    original = s.scalar(select(Imagem).where(Imagem.conta_id == conta_id, Imagem.chave == chave))
    if original is None:
        return None
    return gravar(s, "logo_formulario", original.dados, original.tipo, conta_id, formulario_id)


def apagar_logo_conta(s: Session, conta_id: int) -> bool:
    """Apaga o logo da conta; True se havia um."""
    return s.execute(delete(Imagem).where(Imagem.conta_id == conta_id, Imagem.uso == "logo_conta")).rowcount > 0


# ---- leitura ------------------------------------------------------------------

def logo_da_conta(s: Session, conta_id: int) -> str | None:
    chave = s.scalar(select(Imagem.chave).where(Imagem.conta_id == conta_id, Imagem.uso == "logo_conta"))
    return url_publica(chave) if chave else None


def logo_para_cliente(s: Session, conta_id: int, logo_formulario: str | None) -> str | None:
    """Logo que o cliente vê: o do formulário (`tema.logo_url`); sem ele, o da conta. Uma imagem da plataforma
    que não existe mais (trocada no editor sem salvar o formulário, ou de um formulário copiado que mudou de logo)
    também cai no logo da conta, em vez de uma imagem quebrada."""
    if logo_formulario:
        chave = chave_da_url(logo_formulario)
        if chave is None or s.scalar(select(exists().where(Imagem.conta_id == conta_id, Imagem.chave == chave))):
            return logo_formulario
    return logo_da_conta(s, conta_id)


def _mesma_versao(if_none_match: str | None, sha256: str) -> bool:
    """If-None-Match (lista de ETags, fracas ou não, ou "*") contém a versão atual?"""
    if not if_none_match:
        return False
    for etag in if_none_match.split(","):
        etag = etag.strip()
        if etag == "*":
            return True
        if etag.startswith("W/"):
            etag = etag[2:]
        if etag.strip('"') == sha256:
            return True
    return False


def abrir_publica(chave: str, if_none_match: str | None = None) -> tuple[str, str, bytes | None] | None:
    """(tipo, sha256, bytes) da imagem pela chave; bytes None quando o cliente já tem esta versão (If-None-Match).
    None se a chave não existe. A conta é desconhecida: busca em modo sistema, só pela chave."""
    if not _RE_CHAVE.fullmatch(chave or ""):
        return None
    with modo_sistema() as s:
        linha = s.execute(select(Imagem.id, Imagem.tipo, Imagem.sha256).where(Imagem.chave == chave)).one_or_none()
        if linha is None:
            return None
        if _mesma_versao(if_none_match, linha.sha256):
            return linha.tipo, linha.sha256, None
        return linha.tipo, linha.sha256, s.scalar(select(Imagem.dados).where(Imagem.id == linha.id))
