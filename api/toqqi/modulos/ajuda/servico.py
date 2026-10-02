"""Ajuda (etapa 5b): um conteúdo só, `conteudo.json` (ao lado deste arquivo), servido em GET /ajuda para a tela e
consultado pelo assistente (`buscar`).

Formato: {versao, topicos: [{id, titulo, resumo, secoes: [{id, titulo, somente_admin, atalho, palavras, blocos}]}]},
blocos `paragrafo` e `dica` (texto) e `passos` e `lista` (itens). O arquivo é lido uma vez por processo (cache em
memória) e servido como está; `validar` (usada nos testes) confere ids em kebab-case e únicos, tipos de bloco, atalhos
da lista do assistente, textos não vazios e nada de `<`, `http`, `www.` ou `**`. Arquivo ausente ou inválido: o erro
vai para o log e a Ajuda fica vazia até o arquivo ser lido com sucesso.

Busca: sem acento e sem diferenciar maiúsculas; cada palavra do termo com 3+ letras (menos as muito comuns, como
"como" e "para") vale 3 pontos se aparece no título da seção, 3 se aparece nas `palavras` e 1 se aparece no texto dos
blocos. A palavra casa pelo começo das palavras do texto, pela raiz ("importo" acha "importar").
"""
import json
import logging
import re
import threading
from pathlib import Path

from toqqi.core.ia import cortar
from toqqi.core.texto import sem_acento
from toqqi.modulos.assistente.atalhos import CHAVES as ATALHOS

log = logging.getLogger("toqqi.ajuda")

CAMINHO = Path(__file__).with_name("conteudo.json")
TOPICOS = ("primeiros-passos", "contatos", "formularios", "envios", "respostas", "painel", "relatorios",
           "planos-de-acao", "crescimento", "integracoes", "configuracoes", "equipe", "assinatura", "minha-conta",
           "assistente")
BLOCOS = {"paragrafo": "texto", "dica": "texto", "passos": "itens", "lista": "itens"}
CAMPOS_TOPICO = {"id", "titulo", "resumo", "secoes"}
CAMPOS_SECAO = {"id", "titulo", "somente_admin", "atalho", "palavras", "blocos"}
PROIBIDOS = ("<", "http", "www.", "**")
MAX_RESULTADOS = 3
MAX_TEXTO = 1500
MIN_LETRAS = 3
COMUNS = frozenset({
    "como", "para", "que", "qual", "quais", "onde", "quando", "uma", "uns", "umas", "com", "sem", "por", "pelo",
    "pela", "dos", "das", "nos", "nas", "num", "numa", "meu", "meus", "minha", "minhas", "seu", "seus", "sua", "suas",
    "esse", "essa", "este", "esta", "isso", "isto", "aqui", "fazer", "faco", "posso", "pode", "consigo", "tem",
    "ter", "sao", "voce", "nao", "sim", "mais", "muito", "toqqi", "ajuda", "preciso", "quero",
})
_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")

_cache: dict[Path, dict] = {}
_trava = threading.Lock()


def _vazia() -> dict:
    return {"versao": 1, "topicos": []}


def carregar(caminho: Path | str | None = None) -> dict:
    """O conteúdo como está no arquivo (padrão: `conteudo.json`), lido uma vez por processo. Não altere o que volta."""
    caminho = Path(caminho) if caminho else CAMINHO
    dados = _cache.get(caminho)
    if dados is not None:
        return dados
    with _trava:
        if caminho in _cache:
            return _cache[caminho]
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError) as erro:
            log.error("Ajuda: não foi possível ler %s (%s).", caminho.name, type(erro).__name__)
            return _vazia()
        if not isinstance(dados, dict) or not isinstance(dados.get("topicos"), list):
            log.error("Ajuda: %s fora do formato combinado.", caminho.name)
            return _vazia()
        _cache[caminho] = dados
        return dados


def limpar_cache() -> None:
    _cache.clear()


# ---- validação (testes) ----------------------------------------------------------------

def validar(dados) -> list[str]:
    """Problemas do conteúdo (lista vazia = válido)."""
    erros: list[str] = []

    def texto(valor, onde: str) -> None:
        if not isinstance(valor, str) or not valor.strip():
            erros.append(f"{onde}: texto vazio")
            return
        baixo = valor.lower()
        erros.extend(f"{onde}: contém {p!r}" for p in PROIBIDOS if p in baixo)

    def chaves(obj: dict, esperadas: set[str], onde: str) -> None:
        faltam, sobram = sorted(esperadas - set(obj)), sorted(set(obj) - esperadas)
        if faltam:
            erros.append(f"{onde}: faltam os campos {', '.join(faltam)}")
        if sobram:
            erros.append(f"{onde}: campos desconhecidos {', '.join(sobram)}")

    if not isinstance(dados, dict):
        return ["o conteúdo não é um objeto"]
    chaves(dados, {"versao", "topicos"}, "raiz")
    versao = dados.get("versao")
    if not isinstance(versao, int) or isinstance(versao, bool) or versao < 1:
        erros.append("versao: precisa ser um inteiro a partir de 1")
    topicos = dados.get("topicos")
    if not isinstance(topicos, list) or not topicos:
        return erros + ["topicos: lista vazia"]
    ids_topicos: set[str] = set()
    for i, topico in enumerate(topicos):
        if not isinstance(topico, dict):
            erros.append(f"topicos[{i}]: não é um objeto")
            continue
        tid = topico.get("id")
        onde = f"tópico {tid or i}"
        chaves(topico, CAMPOS_TOPICO, onde)
        if not isinstance(tid, str) or not _ID.fullmatch(tid):
            erros.append(f"{onde}: id fora do kebab-case")
        elif tid in ids_topicos:
            erros.append(f"{onde}: id repetido")
        ids_topicos.add(tid)
        texto(topico.get("titulo"), f"{onde}, titulo")
        texto(topico.get("resumo"), f"{onde}, resumo")
        secoes = topico.get("secoes")
        if not isinstance(secoes, list) or not secoes:
            erros.append(f"{onde}: sem seções")
            continue
        ids_secoes: set[str] = set()
        for j, secao in enumerate(secoes):
            if not isinstance(secao, dict):
                erros.append(f"{onde}, secoes[{j}]: não é um objeto")
                continue
            sid = secao.get("id")
            lugar = f"{onde}, seção {sid or j}"
            chaves(secao, CAMPOS_SECAO, lugar)
            if not isinstance(sid, str) or not _ID.fullmatch(sid):
                erros.append(f"{lugar}: id fora do kebab-case")
            elif sid in ids_secoes:
                erros.append(f"{lugar}: id repetido no tópico")
            ids_secoes.add(sid)
            texto(secao.get("titulo"), f"{lugar}, titulo")
            if not isinstance(secao.get("somente_admin"), bool):
                erros.append(f"{lugar}: somente_admin precisa ser true ou false")
            if secao.get("atalho") is not None and secao.get("atalho") not in ATALHOS:
                erros.append(f"{lugar}: atalho desconhecido ({secao.get('atalho')})")
            palavras = secao.get("palavras")
            if not isinstance(palavras, list):
                erros.append(f"{lugar}: palavras precisa ser uma lista")
            else:
                for p in palavras:
                    texto(p, f"{lugar}, palavras")
            blocos = secao.get("blocos")
            if not isinstance(blocos, list) or not blocos:
                erros.append(f"{lugar}: sem blocos")
                continue
            for k, bloco in enumerate(blocos):
                _validar_bloco(bloco, f"{lugar}, blocos[{k}]", erros, texto)
    return erros


def _validar_bloco(bloco, onde: str, erros: list[str], texto) -> None:
    if not isinstance(bloco, dict) or bloco.get("tipo") not in BLOCOS:
        erros.append(f"{onde}: tipo de bloco inválido")
        return
    campo = BLOCOS[bloco["tipo"]]
    if set(bloco) != {"tipo", campo}:
        erros.append(f"{onde}: um bloco {bloco['tipo']} leva só tipo e {campo}")
    if campo == "texto":
        texto(bloco.get("texto"), onde)
        return
    itens = bloco.get("itens")
    if not isinstance(itens, list) or not itens:
        erros.append(f"{onde}: sem itens")
        return
    for item in itens:
        texto(item, onde)


# ---- busca ----------------------------------------------------------------------------

def normalizar(texto: str) -> str:
    """ "Configurações › Envios" → "configuracoes envios"."""
    return " ".join(_NAO_ALFANUMERICO.sub(" ", sem_acento(texto.lower())).split())


def _raiz(palavra: str) -> str:
    """Começo da palavra que casa com as variações dela: "importo" → "impor", "contatos" → "contat"."""
    return palavra if len(palavra) <= 4 else palavra[: max(4, len(palavra) - 2)]


def raizes(termo: str) -> list[str]:
    vistas: dict[str, None] = {}
    for p in normalizar(termo or "").split():
        if len(p) >= MIN_LETRAS and p not in COMUNS:
            vistas.setdefault(_raiz(p))
    return list(vistas)


def _casa(raiz: str, texto: str) -> bool:
    return texto.startswith(raiz) or f" {raiz}" in texto


def _textos(lista) -> list[str]:
    return [x for x in lista if isinstance(x, str)] if isinstance(lista, list) else []


def texto_da_secao(secao: dict) -> str:
    """Os blocos juntados (passos numerados, itens com "- ", dica com "Dica:"), até 1.500 caracteres."""
    partes = ["Só administrador."] if secao.get("somente_admin") is True else []
    for bloco in secao.get("blocos") or []:
        if not isinstance(bloco, dict):
            continue
        tipo = bloco.get("tipo")
        if tipo in ("paragrafo", "dica") and isinstance(bloco.get("texto"), str):
            partes.append(("Dica: " if tipo == "dica" else "") + bloco["texto"].strip())
        elif tipo == "passos":
            partes.extend(f"{n}. {item.strip()}" for n, item in enumerate(_textos(bloco.get("itens")), 1))
        elif tipo == "lista":
            partes.extend(f"- {item.strip()}" for item in _textos(bloco.get("itens")))
    return cortar("\n".join(p for p in partes if p), MAX_TEXTO)


def _texto_dos_blocos(secao: dict) -> str:
    textos = []
    for bloco in secao.get("blocos") or []:
        if isinstance(bloco, dict):
            textos += _textos([bloco.get("texto")]) + _textos(bloco.get("itens"))
    return " ".join(textos)


def buscar(termo: str, limite: int = MAX_RESULTADOS, caminho: Path | str | None = None) -> list[dict]:
    """As seções que mais casam com o termo: [{topico (título do tópico), titulo, texto, atalho}]."""
    procuradas = raizes(termo)
    if not procuradas or limite < 1:
        return []
    achadas = []
    ordem = 0
    for topico in carregar(caminho).get("topicos") or []:
        if not isinstance(topico, dict):
            continue
        for secao in topico.get("secoes") or []:
            if not isinstance(secao, dict) or not isinstance(secao.get("titulo"), str):
                continue
            ordem += 1
            titulo = normalizar(secao["titulo"])
            palavras = normalizar(" ".join(_textos(secao.get("palavras"))))
            blocos = normalizar(_texto_dos_blocos(secao))
            pontos = sum(3 * _casa(r, titulo) + 3 * _casa(r, palavras) + _casa(r, blocos) for r in procuradas)
            if pontos:
                achadas.append((-pontos, ordem, topico, secao))
    achadas.sort(key=lambda x: (x[0], x[1]))
    return [{"topico": str(topico.get("titulo") or ""), "titulo": secao["titulo"], "texto": texto_da_secao(secao),
             "atalho": secao.get("atalho") if secao.get("atalho") in ATALHOS else None}
            for _, _, topico, secao in achadas[:limite]]
