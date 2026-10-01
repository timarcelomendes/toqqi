"""Temas do comentário por palavras-chave, sem IA. Funções puras (usadas também pela migração 0005).

Normalização: minúsculas, sem acento; hífen, pontuação e quebras de linha viram espaço. Palavra simples casa com
o início de uma palavra (`\\bentreg` acha "entrega", "entregou", mas não "reentrega"); expressão com espaço casa a
sequência inteira ("fazer pedido"), também a partir do início de uma palavra. Uma resposta pode ter vários temas
ou nenhum; a lista sai na ordem da tabela.
"""
import re
import unicodedata

# (chave, rótulo, palavras) — nesta ordem (é também a ordem de desempate no painel)
TEMAS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("prazo_entrega", "Prazo e entrega", (
        "atras", "demor", "prazo", "entreg", "chegou", "chegada", "frete", "transportadora", "motorista", "coleta",
        "logistica")),
    ("produto_avarias", "Produto e avarias", (
        "avaria", "quebrad", "danificad", "amassad", "estragad", "vencid", "validade", "defeito", "qualidade",
        "embalage", "produto errado", "faltando", "troca", "devoluc", "devolv")),
    ("atendimento", "Atendimento", (
        "atendiment", "atendente", "atencios", "vendedor", "representante", "educad", "grosseir", "simpati",
        "cordial", "prestativ", "suporte", "sac", "pos venda")),
    ("preco_condicoes", "Preço e condições", (
        "preco", "caro", "valor", "desconto", "promoc", "condic", "pagamento", "boleto", "parcel", "juros",
        "credito", "tabela", "custo", "barat")),
    ("comunicacao", "Comunicação", (
        "comunica", "informac", "inform", "avis", "retorno", "contato", "ligac", "telefone", "whatsapp", "email",
        "e mail", "rastre", "acompanhament", "atualizac")),
    ("sistema_pedidos", "Sistema e pedidos", (
        "sistema", "site", "aplicativo", "app", "portal", "plataforma", "fazer pedido", "tirar pedido",
        "pedido errado", "pedido incompleto", "erro no pedido", "digitac", "nota fiscal", "nf", "nfe",
        "faturament", "cadastro", "login", "senha")),
)

CHAVES: tuple[str, ...] = tuple(c for c, _, _ in TEMAS)
ROTULOS: dict[str, str] = {c: r for c, r, _ in TEMAS}
_PADROES = [(c, re.compile(r"\b(?:" + "|".join(re.escape(p) for p in palavras) + ")")) for c, _, palavras in TEMAS]
_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")


def normalizar(texto: str | None) -> str:
    """ "Pós-venda: ÓTIMO!" → "pos venda otimo"."""
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return _NAO_ALFANUMERICO.sub(" ", t).strip()


def detectar(texto: str | None) -> list[str]:
    """Chaves dos temas encontrados no texto, na ordem da tabela."""
    t = normalizar(texto)
    if not t:
        return []
    return [chave for chave, padrao in _PADROES if padrao.search(t)]


def lista() -> list[dict]:
    return [{"chave": c, "rotulo": r} for c, r, _ in TEMAS]


def ordenar(chaves) -> list[str]:
    """Só chaves conhecidas, sem repetição, na ordem da tabela."""
    conj = set(chaves or ())
    return [c for c in CHAVES if c in conj]
