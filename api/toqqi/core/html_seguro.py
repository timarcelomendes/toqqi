"""HTML dos formulários (etapa 5l, docs/api-etapa-5l.md §3): lista permitida, limpeza com nh3 e variáveis no HTML.

A página da pesquisa fica no mesmo endereço do app (onde está a sessão de quem usa o app). Por isso o HTML dos blocos de
conteúdo e dos finais é limpo por lista permitida a cada gravação (criar, PATCH, rascunho, publicar, duplicar e
modelos) e de novo no navegador (DOMPurify, com a mesma lista). Fica só o que está em `TAGS` e `ATRIBUTOS`:
- links: `href` só `https:`, `http:`, `mailto:` e `tel:` (endereço relativo cai), sempre com `target="_blank"` e
  `rel="noopener noreferrer nofollow ugc"`;
- imagens: só da plataforma (`imagens.prefixo_publico()` + chave válida); as outras saem inteiras (a página da
  pesquisa não chama outros sites); `width`/`height` inteiros de 1 a 2000;
- `colspan`/`rowspan` de 1 a 20; `style` só com `text-align` (left, center, right, justify) em p, h2–h4, div, td e th.
Cai todo o resto: `class`, `id`, `name`, `on*`, outros estilos, comentários, `data:`, `javascript:`, e as tags fora da
lista (script, style, iframe, svg, math, mídia e formulários caem junto com o que têm dentro; nas outras, fica o texto).

Variáveis {empresa} {nome} {assunto} {referencia} no HTML: `renderizar_html` troca pelo valor escapado e não junta
espaços. Citações `{{ID}}` (respostas anteriores, §2.7) nunca são tocadas aqui: quem troca é o navegador.
"""
import html
import re
import secrets
from collections.abc import Callable

import nh3

TAGS = frozenset({
    "p", "br", "strong", "b", "em", "i", "u", "s", "a", "ul", "ol", "li", "h2", "h3", "h4", "blockquote", "hr", "img",
    "span", "div", "table", "thead", "tbody", "tr", "th", "td", "caption", "small", "sub", "sup", "code", "pre",
    "figure", "figcaption",
})
_ALINHAVEIS = ("p", "h2", "h3", "h4", "div", "td", "th")
ATRIBUTOS: dict[str, set[str]] = {
    "a": {"href", "title"},
    "img": {"src", "alt", "width", "height"},
    **{t: {"style"} for t in _ALINHAVEIS},
}
for _t in ("td", "th"):
    ATRIBUTOS[_t] = ATRIBUTOS[_t] | {"colspan", "rowspan"}
# caem junto com o conteúdo (nas outras tags fora da lista, o texto de dentro fica)
SEM_CONTEUDO = frozenset({
    "script", "style", "iframe", "frame", "frameset", "object", "embed", "applet", "svg", "math", "template",
    "noscript", "noembed", "noframes", "title", "xmp", "plaintext", "textarea", "select", "video", "audio",
    "canvas", "head",
})
ESQUEMAS = frozenset({"https", "http", "mailto", "tel"})
REL = "noopener noreferrer nofollow ugc"
ALINHAMENTOS = ("left", "center", "right", "justify")
MAX_ENTRADA = 50_000  # caracteres recebidos
MAX_HTML = 20_000  # caracteres depois da limpeza
MSG_GRANDE = "Este conteúdo está grande demais (máx. 20.000 caracteres)."

_RE_CHAVE = re.compile(r"[A-Za-z0-9_-]{32,128}")
_RE_INTEIRO = re.compile(r"[0-9]{1,6}")
# depois da limpeza, "<" e ">" só aparecem como início e fim de tag (o nh3 escapa os dois nos valores de atributo)
_RE_IMG = re.compile(r"<img\b[^>]*>")
_RE_TAG = re.compile(r"<[^>]*>")
_RE_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# citação de resposta anterior (§2.7): nada entre as chaves duplas é variável
RE_CITACAO = re.compile(r"\{\{[^{}]*\}\}")
VARIAVEIS = ("empresa", "nome", "assunto", "referencia")


def _prefixo_padrao() -> str:
    from toqqi.modulos.imagens.servico import prefixo_publico  # core não depende de módulo ao importar

    return prefixo_publico()


def _inteiro_entre(valor: str, minimo: int, maximo: int) -> str | None:
    v = valor.strip()
    if not _RE_INTEIRO.fullmatch(v) or not minimo <= int(v) <= maximo:
        return None
    return str(int(v))


def _alinhamento(estilo: str) -> str | None:
    """Do `style`, só a última declaração `text-align` com um valor permitido; o resto cai."""
    escolhido = None
    for declaracao in estilo.split(";"):
        nome, _, valor = declaracao.partition(":")
        if nome.strip().lower() == "text-align" and valor.strip().lower() in ALINHAMENTOS:
            escolhido = valor.strip().lower()
    return f"text-align: {escolhido}" if escolhido else None


def _filtro(prefixo_imagens: str | None) -> Callable[[str, str, str], str | None]:
    prefixos: list[str] = [] if prefixo_imagens is None else [prefixo_imagens]

    def filtrar(tag: str, atributo: str, valor: str) -> str | None:
        if tag == "img" and atributo == "src":
            if not prefixos:  # só lê a configuração se houver imagem
                prefixos.append(_prefixo_padrao())
            prefixo = prefixos[0]
            resto = valor[len(prefixo):] if prefixo and valor.startswith(prefixo) else ""
            return valor if _RE_CHAVE.fullmatch(resto) else None
        if tag == "img" and atributo in ("width", "height"):
            return _inteiro_entre(valor, 1, 2000)
        if tag in ("td", "th") and atributo in ("colspan", "rowspan"):
            return _inteiro_entre(valor, 1, 20)
        if atributo == "style":
            return _alinhamento(valor) if tag in _ALINHAVEIS else None
        return valor

    return filtrar


def _sem_imagens_soltas(limpo: str) -> str:
    """Tira as `<img>` que ficaram sem `src` (imagem de fora da plataforma): a imagem sai inteira."""
    if "<img" not in limpo:
        return limpo
    return _RE_IMG.sub(lambda m: m.group(0) if ' src="' in m.group(0) else "", limpo)


def limpar_html(texto: str | None, prefixo_imagens: str | None = None) -> str:
    """O HTML só com a lista permitida (§3.1). Não confere tamanho (quem chama confere `MAX_ENTRADA` antes e `MAX_HTML`
    depois). Limpar o que já está limpo não muda nada."""
    if not texto:
        return ""
    limpo = nh3.clean(
        _RE_CONTROLE.sub("", texto),
        tags=set(TAGS),
        clean_content_tags=set(SEM_CONTEUDO),
        attributes={t: set(a) for t, a in ATRIBUTOS.items()},
        attribute_filter=_filtro(prefixo_imagens),
        strip_comments=True,
        link_rel=REL,
        url_schemes=set(ESQUEMAS),
        url_relative="deny",
        set_tag_attribute_values={"a": {"target": "_blank"}},
    )
    return _sem_imagens_soltas(limpo).strip()


def sem_conteudo(limpo: str) -> bool:
    """O HTML (já limpo) não mostra nada: sem texto, imagem nem linha (ex.: `<p></p>` ou `<p>&nbsp;</p>`)."""
    if "<img" in limpo or "<hr" in limpo:
        return False
    return not html.unescape(_RE_TAG.sub("", limpo)).strip()


# ---- citações e variáveis ----------------------------------------------------------------

def proteger_citacoes(texto: str, valores=()) -> tuple[str, Callable[[str], str]]:
    """Troca cada `{{…}}` por uma marca que nenhuma regra de variável toca (e que não está no texto nem nos `valores`
    que vão entrar nele); devolve o texto e a função que põe as citações de volta."""
    citacoes = RE_CITACAO.findall(texto)
    if not citacoes:
        return texto, lambda t: t
    junto = texto + "".join(str(x) for x in valores if x)
    marca = "" + secrets.token_hex(8)
    while marca in junto:
        marca = "" + secrets.token_hex(8)
    contador = iter(range(len(citacoes)))
    protegido = RE_CITACAO.sub(lambda _m: f"{marca}#{next(contador)}#{marca}", texto)
    padrao = re.compile(re.escape(marca) + r"#([0-9]+)#" + re.escape(marca))
    return protegido, lambda t: padrao.sub(lambda m: citacoes[int(m.group(1))], t)


def _sem_nome_no_inicio(m: re.Match) -> str:
    return m.group(1) + m.group(2).upper()


def renderizar_html(texto: str | None, v: dict) -> str | None:
    """Troca as variáveis de `v` no HTML (já limpo) pelo valor escapado (`& < > " '`), sem juntar espaços e sem tocar
    nas citações `{{…}}`. Variável vazia some junto com o espaço antes; {nome} vazio também leva a vírgula antes, e no
    começo de um parágrafo leva a vírgula depois ("<p>{nome}, tudo bem?</p>" → "<p>Tudo bem?</p>")."""
    if not texto or "{" not in texto:
        return texto
    texto, restaurar = proteger_citacoes(texto, v.values())
    for chave in v:
        marca = "{" + chave + "}"
        if marca not in texto:
            continue
        valor = str(v.get(chave) or "")
        if valor:
            texto = texto.replace(marca, html.escape(valor, quote=True))
            continue
        if chave == "nome":
            texto = re.sub(r",[ \t]*\{nome\}", "", texto)
            texto = re.sub(r"(^|>)[ \t]*\{nome\}[ \t]*[,!]?[ \t]*(\w?)", _sem_nome_no_inicio, texto)
        texto = re.sub(r"[ \t]*" + re.escape(marca), "", texto)
    return restaurar(texto)
