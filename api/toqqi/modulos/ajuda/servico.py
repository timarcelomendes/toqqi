"""Ajuda (etapa 5b; jornadas em docs/ajuda-jornadas.md): um conteúdo só, `conteudo.json` (ao lado deste arquivo),
servido em GET /ajuda para a tela e consultado pelo assistente (`buscar`).

Formato: {versao, jornadas (opcional), topicos}. Tópicos: [{id, titulo, resumo, secoes: [{id, titulo, somente_admin,
atalho, palavras, blocos}]}], blocos `paragrafo` e `dica` (texto) e `passos` e `lista` (itens). Jornadas: [{id, grupo
(`ciclo` ou `alem`, as do ciclo antes), titulo, objetivo, somente_admin, onde (o caminho no menu, em pedaços), atalho,
como (os passos), resultado, veja (`topico#secao`), palavras}]. O arquivo é lido uma vez por processo (cache em
memória) e servido como está; `validar` (usada nos testes) confere ids em kebab-case e únicos (o id de tópico
`jornadas` é reservado), tipos de bloco, atalhos da lista do assistente, os limites e as referências das jornadas,
textos não vazios e nada de `<`, `http`, `www.` ou `**`. Arquivo ausente ou inválido: o erro vai para o log e a Ajuda
fica vazia até o arquivo ser lido com sucesso.

Busca: jornadas e seções juntas, sem acento e sem diferenciar maiúsculas; cada palavra do termo com 3+ letras (menos
as muito comuns, como "como" e "para") vale 3 pontos se aparece no título, 3 se aparece nas `palavras` e 1 se aparece
no texto (os blocos da seção; o objetivo, o onde, o como e o resultado da jornada). A palavra casa pelo começo das
palavras do texto, pela raiz ("importo" acha "importar"). No empate, as jornadas vêm antes das seções e, depois, vale
a ordem do arquivo.
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
JORNADAS = ("cadastrar-seus-clientes", "preparar-a-pesquisa", "ligar-os-envios", "enviar-a-pesquisa",
            "ler-as-respostas", "tratar-um-cliente-insatisfeito", "acompanhar-os-numeros", "descobrir-onde-agir",
            "crescer-com-quem-esta-feliz", "perguntar-ao-toqqiai", "trazer-a-equipe", "ligar-o-seu-sistema",
            "assinar-um-plano")
GRUPOS = ("ciclo", "alem")
BLOCOS = {"paragrafo": "texto", "dica": "texto", "passos": "itens", "lista": "itens"}
CAMPOS_RAIZ = {"versao", "topicos"}  # e `jornadas`, opcional
CAMPOS_TOPICO = {"id", "titulo", "resumo", "secoes"}
CAMPOS_SECAO = {"id", "titulo", "somente_admin", "atalho", "palavras", "blocos"}
CAMPOS_JORNADA = {"id", "grupo", "titulo", "objetivo", "somente_admin", "onde", "atalho", "como", "resultado", "veja",
                  "palavras"}
PROIBIDOS = ("<", "http", "www.", "**")
# jornadas: tamanhos (caracteres) e quantidades (de, até)
MAX_TITULO = 60
MAX_OBJETIVO = 160
MAX_RESULTADO = 320
MAX_PEDACO = 40
MAX_PASSO = 220
PEDACOS_ONDE = (1, 4)
PASSOS_COMO = (2, 6)
REFERENCIAS_VEJA = (1, 3)
SEPARADOR = "›"  # a tela põe entre os pedaços do `onde`
ID_RESERVADO = "jornadas"  # nenhum tópico usa: /ajuda/jornadas é a página das jornadas
TOPICO_JORNADAS = "Jornadas"  # o "topico" das jornadas na busca
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

    def texto(valor, onde: str, maximo: int | None = None) -> None:
        if not isinstance(valor, str) or not valor.strip():
            erros.append(f"{onde}: texto vazio")
            return
        baixo = valor.lower()
        erros.extend(f"{onde}: contém {p!r}" for p in PROIBIDOS if p in baixo)
        if maximo is not None and len(valor) > maximo:
            erros.append(f"{onde}: passa de {maximo} caracteres")

    def chaves(obj: dict, esperadas: set[str], onde: str) -> None:
        faltam, sobram = sorted(esperadas - set(obj)), sorted(set(obj) - esperadas)
        if faltam:
            erros.append(f"{onde}: faltam os campos {', '.join(faltam)}")
        if sobram:
            erros.append(f"{onde}: campos desconhecidos {', '.join(sobram)}")

    if not isinstance(dados, dict):
        return ["o conteúdo não é um objeto"]
    chaves(dados, CAMPOS_RAIZ | ({"jornadas"} & set(dados)), "raiz")
    versao = dados.get("versao")
    if not isinstance(versao, int) or isinstance(versao, bool) or versao < 1:
        erros.append("versao: precisa ser um inteiro a partir de 1")
    topicos = dados.get("topicos")
    if not isinstance(topicos, list) or not topicos:
        return erros + ["topicos: lista vazia"]
    ids_topicos: set[str] = set()
    referencias: set[str] = set()  # "topico#secao" de cada seção, para o `veja` das jornadas
    for i, topico in enumerate(topicos):
        if not isinstance(topico, dict):
            erros.append(f"topicos[{i}]: não é um objeto")
            continue
        tid = topico.get("id")
        onde = f"tópico {tid or i}"
        chaves(topico, CAMPOS_TOPICO, onde)
        if not isinstance(tid, str) or not _ID.fullmatch(tid):
            erros.append(f"{onde}: id fora do kebab-case")
        elif tid == ID_RESERVADO:
            erros.append(f"{onde}: id reservado para a página das jornadas")
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
            if isinstance(tid, str) and isinstance(sid, str):
                referencias.add(f"{tid}#{sid}")
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
    if "jornadas" in dados:
        _validar_jornadas(dados["jornadas"], referencias, erros, texto, chaves)
    return erros


def _validar_jornadas(jornadas, referencias: set[str], erros: list[str], texto, chaves) -> None:
    if not isinstance(jornadas, list) or not jornadas:
        erros.append("jornadas: lista vazia")
        return
    ids: set[str] = set()
    alem = False  # já veio uma jornada do grupo alem
    for i, jornada in enumerate(jornadas):
        if not isinstance(jornada, dict):
            erros.append(f"jornadas[{i}]: não é um objeto")
            continue
        jid = jornada.get("id")
        lugar = f"jornada {jid or i}"
        chaves(jornada, CAMPOS_JORNADA, lugar)
        if not isinstance(jid, str) or not _ID.fullmatch(jid):
            erros.append(f"{lugar}: id fora do kebab-case")
        elif jid in ids:
            erros.append(f"{lugar}: id repetido")
        else:
            ids.add(jid)
        grupo = jornada.get("grupo")
        if grupo not in GRUPOS:
            erros.append(f"{lugar}, grupo: precisa ser ciclo ou alem")
        elif grupo == "alem":
            alem = True
        elif alem:
            erros.append(f"{lugar}, grupo: as jornadas do ciclo vêm antes das de alem")
        texto(jornada.get("titulo"), f"{lugar}, titulo", MAX_TITULO)
        texto(jornada.get("objetivo"), f"{lugar}, objetivo", MAX_OBJETIVO)
        texto(jornada.get("resultado"), f"{lugar}, resultado", MAX_RESULTADO)
        if not isinstance(jornada.get("somente_admin"), bool):
            erros.append(f"{lugar}, somente_admin: precisa ser true ou false")
        if jornada.get("atalho") is not None and jornada.get("atalho") not in ATALHOS:
            erros.append(f"{lugar}, atalho: desconhecido ({jornada.get('atalho')})")
        for pedaco in _itens(jornada.get("onde"), PEDACOS_ONDE, f"{lugar}, onde", "pedaços", erros):
            texto(pedaco, f"{lugar}, onde", MAX_PEDACO)
            if isinstance(pedaco, str) and SEPARADOR in pedaco:
                erros.append(f"{lugar}, onde: sem “{SEPARADOR}” nos pedaços (a tela põe o separador)")
        for passo in _itens(jornada.get("como"), PASSOS_COMO, f"{lugar}, como", "passos", erros):
            texto(passo, f"{lugar}, como", MAX_PASSO)
        vistas: set[str] = set()
        for ref in _itens(jornada.get("veja"), REFERENCIAS_VEJA, f"{lugar}, veja", "referências", erros):
            if not isinstance(ref, str) or ref not in referencias:
                erros.append(f"{lugar}, veja: seção inexistente ({ref})")
            elif ref in vistas:
                erros.append(f"{lugar}, veja: referência repetida ({ref})")
            else:
                vistas.add(ref)
        palavras = jornada.get("palavras")
        if not isinstance(palavras, list):
            erros.append(f"{lugar}, palavras: precisa ser uma lista")
        else:
            for p in palavras:
                texto(p, f"{lugar}, palavras")


def _itens(valor, quantos: tuple[int, int], onde: str, nome: str, erros: list[str]) -> list:
    """Os itens de `valor` (nenhum, se não for uma lista), com erro se não forem de `quantos[0]` a `quantos[1]`."""
    if not isinstance(valor, list) or not quantos[0] <= len(valor) <= quantos[1]:
        erros.append(f"{onde}: precisa ter de {quantos[0]} a {quantos[1]} {nome}")
    return valor if isinstance(valor, list) else []


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


def _lista(valor) -> list:
    return valor if isinstance(valor, list) else []


def _textos(lista) -> list[str]:
    return [x for x in lista if isinstance(x, str)] if isinstance(lista, list) else []


def texto_da_secao(secao: dict) -> str:
    """Os blocos juntados (passos numerados, itens com "- ", dica com "Dica:"), até 1.500 caracteres."""
    partes = ["Só administrador."] if secao.get("somente_admin") is True else []
    for bloco in _lista(secao.get("blocos")):
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


def texto_da_jornada(jornada: dict) -> str:
    """ "Só administrador." (se for o caso), o objetivo, "Onde: A › B", "Como:" com os passos numerados e
    "Resultado: …", uma parte por linha, até 1.500 caracteres."""
    partes = ["Só administrador."] if jornada.get("somente_admin") is True else []
    partes += [t.strip() for t in _textos([jornada.get("objetivo")])]
    onde = [t.strip() for t in _textos(jornada.get("onde")) if t.strip()]
    if onde:
        partes.append("Onde: " + f" {SEPARADOR} ".join(onde))
    passos = [t.strip() for t in _textos(jornada.get("como")) if t.strip()]
    if passos:
        partes += ["Como:"] + [f"{n}. {passo}" for n, passo in enumerate(passos, 1)]
    partes += [f"Resultado: {t.strip()}" for t in _textos([jornada.get("resultado")]) if t.strip()]
    return cortar("\n".join(p for p in partes if p), MAX_TEXTO)


def _texto_dos_blocos(secao: dict) -> str:
    textos = []
    for bloco in _lista(secao.get("blocos")):
        if isinstance(bloco, dict):
            textos += _textos([bloco.get("texto")]) + _textos(bloco.get("itens"))
    return " ".join(textos)


def _texto_das_partes(jornada: dict) -> str:
    """O "texto" da jornada na busca: objetivo, onde, como e resultado."""
    return " ".join(_textos([jornada.get("objetivo")]) + _textos(jornada.get("onde")) + _textos(jornada.get("como"))
                    + _textos([jornada.get("resultado")]))


def buscar(termo: str, limite: int = MAX_RESULTADOS, caminho: Path | str | None = None) -> list[dict]:
    """As jornadas e as seções que mais casam com o termo: [{topico, titulo, texto, atalho}], com topico "Jornadas"
    nas jornadas e o título do tópico nas seções. No empate, as jornadas primeiro; depois, a ordem do arquivo."""
    procuradas = raizes(termo)
    if not procuradas or limite < 1:
        return []
    dados = carregar(caminho)
    # (topico, jornada ou seção, texto pesquisado, texto do resultado), na ordem do desempate
    candidatas = [(TOPICO_JORNADAS, jornada, _texto_das_partes(jornada), texto_da_jornada)
                  for jornada in _lista(dados.get("jornadas"))
                  if isinstance(jornada, dict) and isinstance(jornada.get("titulo"), str)]
    for topico in _lista(dados.get("topicos")):
        if isinstance(topico, dict):
            candidatas += [(str(topico.get("titulo") or ""), secao, _texto_dos_blocos(secao), texto_da_secao)
                           for secao in _lista(topico.get("secoes"))
                           if isinstance(secao, dict) and isinstance(secao.get("titulo"), str)]
    achadas = []
    for ordem, (_, item, corpo, _) in enumerate(candidatas):
        titulo = normalizar(item["titulo"])
        palavras = normalizar(" ".join(_textos(item.get("palavras"))))
        corpo = normalizar(corpo)
        pontos = sum(3 * _casa(r, titulo) + 3 * _casa(r, palavras) + _casa(r, corpo) for r in procuradas)
        if pontos:
            achadas.append((-pontos, ordem))
    achadas.sort()
    resultado = []
    for _, ordem in achadas[:limite]:
        topico, item, _, formatar = candidatas[ordem]
        resultado.append({"topico": topico, "titulo": item["titulo"], "texto": formatar(item),
                          "atalho": item.get("atalho") if item.get("atalho") in ATALHOS else None})
    return resultado
