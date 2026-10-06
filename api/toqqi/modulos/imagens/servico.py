"""Imagens da conta: o logo da empresa, o logo de cada formulário e o banco de imagens (etapa 5e, `banco.py`).

Ficam no banco (tabela `imagens`; um logo por uso) e saem sem login em GET /publico/imagens/{chave}. A chave é
aleatória (43 caracteres url-safe): a URL não se adivinha e o conteúdo dela nunca muda. Trocar a imagem apaga a
anterior e grava outra com chave nova, então a URL muda e os caches (navegador, proxy de imagens do Gmail) se
renovam sozinhos. Só PNG ou JPEG, conferidos pelos primeiros bytes (não pela extensão): até 300 KB nos logos e até
1 MB no banco de imagens, que também guarda o nome do arquivo (limpo) e as dimensões lidas do cabeçalho.

Onde o cliente vê o logo (página da pesquisa e e-mails): o do formulário; sem ele, o da conta (`logo_para_cliente`).

Etapa 5l (docs/api-etapa-5l.md §4.6): imagens dos blocos de conteúdo (`conteudo_formulario`, até 1 MB) e logos do
formulário ficam ligadas ao formulário e não apagam as anteriores ao enviar (o rascunho pode trocar o logo sem quebrar o
que está no ar; desfazer no editor ainda acha a imagem). A limpeza (`limpar_do_formulario`) roda ao publicar e ao
descartar o rascunho: saem as do formulário que nenhum formulário da conta cita (publicado ou rascunho, no logo do tema
ou em algum HTML). Entre uma limpeza e outra, cada formulário guarda até 60 imagens (`LIMITE_POR_FORMULARIO`).
"""
import hashlib
import re
import secrets
import unicodedata

from sqlalchemy import delete, exists, func, select, text
from sqlalchemy.orm import Session

from toqqi.core.config import config
from toqqi.core.db import modo_sistema
from toqqi.core.errors import AppError
from toqqi.modelos import Imagem

LIMITE_BYTES = 300 * 1024  # 307200: logos
MSG_ARQUIVO = "Use uma imagem PNG ou JPG de até 300 KB."
LIMITE_BANCO = 1024 * 1024  # 1048576: banco de imagens e imagens dos blocos de conteúdo
MSG_BANCO = "Use uma imagem PNG ou JPG de até 1 MB."
USOS_DO_FORMULARIO = ("logo_formulario", "conteudo_formulario")
LIMITE_POR_FORMULARIO = 60
MSG_LIMITE_FORMULARIO = ("Este formulário chegou ao limite de 60 imagens enviadas. Publique ou descarte as alterações "
                         "para liberar as que não estão em uso.")
MAX_NOME = 120
MAX_DIMENSAO = 2**31 - 1  # coluna integer
CAMINHO = "/api/v1/publico/imagens/"
CACHE = "public, max-age=31536000, immutable"
_RE_CHAVE = re.compile(r"[A-Za-z0-9_-]{32,128}")
_ASSINATURAS = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"))
# marcadores SOF do JPEG (início do quadro, com as dimensões); C4 (DHT), C8 (JPG) e CC (DAC) não são
_SOF = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})


# ---- arquivo enviado ----------------------------------------------------------

def tipo_da_imagem(dados: bytes) -> str | None:
    """image/png ou image/jpeg pelos primeiros bytes; None se não for nenhum dos dois."""
    for assinatura, tipo in _ASSINATURAS:
        if dados.startswith(assinatura):
            return tipo
    return None


def ler_envio(arquivo, limite: int = LIMITE_BYTES, mensagem: str = MSG_ARQUIVO) -> tuple[bytes, str]:
    """(bytes, tipo) do arquivo enviado (multipart `arquivo`), lendo no máximo o limite + 1 byte. Tipo errado,
    arquivo vazio ou grande demais → 422 no campo `arquivo` (padrão: o limite e a mensagem dos logos)."""
    dados = arquivo.file.read(limite + 1)
    tipo = tipo_da_imagem(dados)
    if tipo is None or len(dados) > limite:
        raise AppError(422, "dados_invalidos", mensagem, {"arquivo": mensagem})
    return dados, tipo


def _dimensoes_png(dados: bytes) -> tuple[int, int] | None:
    # assinatura (8) + tamanho do bloco (4) + "IHDR" (4) + largura (4) + altura (4), inteiros big-endian
    if len(dados) < 24 or dados[12:16] != b"IHDR":
        return None
    return int.from_bytes(dados[16:20], "big"), int.from_bytes(dados[20:24], "big")


def _dimensoes_jpeg(dados: bytes) -> tuple[int, int] | None:
    """Percorre os segmentos até o primeiro SOF: FF Cn, tamanho (2), precisão (1), altura (2), largura (2)."""
    i, n = 2, len(dados)
    while i + 4 <= n:
        if dados[i] != 0xFF:
            return None
        marcador = dados[i + 1]
        if marcador == 0xFF:  # bytes de preenchimento antes do marcador
            i += 1
            continue
        if marcador in (0x01, 0xD8) or 0xD0 <= marcador <= 0xD7:  # marcadores sem tamanho
            i += 2
            continue
        if marcador in (0xD9, 0xDA):  # fim da imagem ou início dos dados comprimidos, sem SOF antes
            return None
        tamanho = int.from_bytes(dados[i + 2:i + 4], "big")
        if tamanho < 2:
            return None
        if marcador in _SOF:
            if i + 9 > n:
                return None
            return int.from_bytes(dados[i + 7:i + 9], "big"), int.from_bytes(dados[i + 5:i + 7], "big")
        i += 2 + tamanho
    return None


def dimensoes(dados: bytes, tipo: str) -> tuple[int | None, int | None]:
    """(largura, altura) lidas do cabeçalho PNG (IHDR) ou JPEG (SOF); (None, None) se não der para ler."""
    medidas = _dimensoes_png(dados) if tipo == "image/png" else _dimensoes_jpeg(dados)
    if medidas is None or not all(0 < x <= MAX_DIMENSAO for x in medidas):
        return None, None
    return medidas


def nome_do_arquivo(nome: str | None) -> str | None:
    """Nome do arquivo enviado, sem pastas, sem caracteres de controle nem invisíveis (formato e controles
    bidirecionais), com os espaços juntos e até 120 caracteres; vazio = None."""
    base = (nome or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = "".join(" " if unicodedata.category(c) == "Cc" else c for c in base
                   if unicodedata.category(c) not in ("Cf", "Cs"))
    return " ".join(base.split())[:MAX_NOME].strip() or None


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

def nova_imagem(conta_id: int, uso: str, dados: bytes, tipo: str, **campos) -> Imagem:
    """Imagem nova (ainda não gravada) com chave aleatória e o sha256 dos bytes."""
    return Imagem(conta_id=conta_id, uso=uso, chave=secrets.token_urlsafe(32), tipo=tipo, dados=dados,
                  tamanho=len(dados), sha256=hashlib.sha256(dados).hexdigest(), **campos)


def gravar(s: Session, uso: str, dados: bytes, tipo: str, conta_id: int, formulario_id: int | None = None) -> str:
    """Troca a imagem do uso (logo da conta): apaga a anterior e grava outra, com chave nova. Quem chama trava o dono
    antes, para duas trocas ao mesmo tempo não colidirem no índice único. Devolve a URL pública. (Os logos de
    formulário, desde a etapa 5l, usam `gravar_do_formulario`, que não apaga o anterior.)"""
    dono = Imagem.formulario_id == formulario_id if uso == "logo_formulario" else Imagem.conta_id == conta_id
    s.execute(delete(Imagem).where(Imagem.conta_id == conta_id, Imagem.uso == uso, dono))
    imagem = nova_imagem(conta_id, uso, dados, tipo, formulario_id=formulario_id)
    s.add(imagem)
    s.flush()
    return url_publica(imagem.chave)


def gravar_do_formulario(s: Session, uso: str, dados: bytes, tipo: str, conta_id: int, formulario_id: int,
                         **campos) -> Imagem:
    """Grava uma imagem do formulário (logo ou conteúdo) sem apagar as anteriores. Quem chama trava o formulário antes
    (a contagem não corre). 409 `limite_imagens` com 60 imagens guardadas no formulário."""
    assert uso in USOS_DO_FORMULARIO
    total = s.scalar(select(func.count()).select_from(Imagem)
                     .where(Imagem.conta_id == conta_id, Imagem.formulario_id == formulario_id))
    if total >= LIMITE_POR_FORMULARIO:
        raise AppError(409, "limite_imagens", MSG_LIMITE_FORMULARIO)
    imagem = nova_imagem(conta_id, uso, dados, tipo, formulario_id=formulario_id, **campos)
    s.add(imagem)
    s.flush()
    return imagem


def chaves_citadas(*textos: str | None) -> list[str]:
    """As chaves das imagens da plataforma citadas nos textos (URL no logo do tema ou `src` no HTML), sem repetir."""
    padrao = re.compile(re.escape(prefixo_publico()) + r"([A-Za-z0-9_-]{32,128})")
    return list(dict.fromkeys(m for t in textos if t for m in padrao.findall(t)))


def copiar_para_formulario(s: Session, textos: list[str], conta_id: int, formulario_id: int) -> dict[str, str]:
    """Formulário copiado: cada imagem da plataforma citada nos textos (logo e HTML, do publicado e do rascunho) que é
    desta conta e não é do banco de imagens ganha uma cópia no formulário novo (chave nova): trocar ou limpar as de um
    não mexe no outro. Devolve {url antiga: url nova}; endereço de fora e imagem do banco ficam como estão."""
    trocas: dict[str, str] = {}
    for chave in chaves_citadas(*textos):
        original = s.scalar(select(Imagem).where(Imagem.conta_id == conta_id, Imagem.chave == chave,
                                                 Imagem.uso != "banco"))
        if original is None:
            continue
        uso = "conteudo_formulario" if original.uso == "conteudo_formulario" else "logo_formulario"
        copia = nova_imagem(conta_id, uso, original.dados, original.tipo, formulario_id=formulario_id,
                            nome=original.nome, largura=original.largura, altura=original.altura)
        s.add(copia)
        s.flush()
        trocas[url_publica(chave)] = url_publica(copia.chave)
    return trocas


def limpar_do_formulario(s: Session, conta_id: int, formulario_id: int) -> int:
    """Apaga as imagens do formulário (logo e conteúdo) que nenhum formulário da conta cita, no publicado ou no
    rascunho (a chave é aleatória e longa: aparecer no JSON é estar citada). Devolve quantas saíram."""
    return s.execute(text("""
        DELETE FROM imagens i
         WHERE i.conta_id = :conta AND i.formulario_id = :formulario
           AND i.uso IN ('logo_formulario', 'conteudo_formulario')
           AND NOT EXISTS (
               SELECT 1 FROM formularios f
                WHERE f.conta_id = :conta
                  AND (strpos(f.tema::text, i.chave) > 0 OR strpos(f.perguntas::text, i.chave) > 0
                       OR strpos(f.finais::text, i.chave) > 0 OR strpos(coalesce(f.rascunho::text, ''), i.chave) > 0))
    """), {"conta": conta_id, "formulario": formulario_id}).rowcount


def formulario_que_cita(s: Session, conta_id: int, chave: str) -> str | None:
    """Nome de um formulário (não arquivado) que cita a imagem, no publicado ou no rascunho; None se nenhum."""
    return s.scalar(text("""
        SELECT nome FROM formularios
         WHERE conta_id = :conta AND NOT arquivado
           AND (strpos(tema::text, :chave) > 0 OR strpos(perguntas::text, :chave) > 0
                OR strpos(finais::text, :chave) > 0 OR strpos(coalesce(rascunho::text, ''), :chave) > 0)
         ORDER BY id LIMIT 1
    """), {"conta": conta_id, "chave": chave})


def citadas_em_formularios(s: Session, conta_id: int) -> str:
    """Todo o JSON dos formulários não arquivados da conta (publicado e rascunho), para conferir várias chaves."""
    return "\n".join(s.scalars(text("""
        SELECT tema::text || perguntas::text || finais::text || coalesce(rascunho::text, '')
          FROM formularios WHERE conta_id = :conta AND NOT arquivado
    """), {"conta": conta_id}).all())


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
