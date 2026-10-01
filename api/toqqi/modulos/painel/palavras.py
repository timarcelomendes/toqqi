"""Palavras mais citadas nos comentários (bloco do painel). Função pura.

Palavras com 3 ou mais letras, fora de uma lista de palavras comuns do português; cada palavra conta uma vez
por resposta; a palavra aparece na forma mais frequente (com acento, no empate).
"""
import re
from collections import Counter, defaultdict
from collections.abc import Iterable

from toqqi.core.texto import sem_acento

# Palavras comuns (sem acento, minúsculas) que não dizem nada sozinhas.
COMUNS = frozenset("""
a ao aos aquela aquelas aquele aqueles aquilo as assim ate bem cada com como contra da das de dela delas dele
deles depois desde dessa desse desta deste do dos e ela elas ele eles em entao entre era eram essa essas esse
esses esta estao estar estas estava estavam este estes estou eu faz fazem fazer feita feito foi foram fui ha
isso isto ja la lhe lhes mais mas me mesma mesmo meu meus minha minhas muita muitas muito muitos na nas nem
nessa nesse nesta neste no nos nossa nossas nosso nossos num numa o os ou para pela pelas pelo pelos per pois
por porque porem pra pro qual quais qualquer quando quanto que quem se sem sendo ser sera seria seu seus si
sido sim so sob sobre sua suas tal tambem tanto te tem temos tenho ter teve tinha tinham toda todas todo todos
tu tua tuas tudo um uma umas uns vai vao voce voces vos ainda agora aqui ali onde apenas sempre nunca outra
outras outro outros nao sao sejam seja tao estamos estive esteve tive tiveram fica ficou acho achei vez vezes
nada algo alguem algum alguma alguns algumas coisa coisas gente deu dar pode podem poderia poderiam deve devem
deveria vou vamos ficar
""".split())

_PALAVRA = re.compile(r"[^\W\d_]+")
MAX_PALAVRAS = 12


def _forma(formas: Counter) -> str:
    """A grafia mais usada; no empate, a com acento; depois a primeira em ordem alfabética."""
    return min(formas.items(), key=lambda kv: (-kv[1], kv[0] == sem_acento(kv[0]), kv[0]))[0]


def contar(textos: Iterable[str], limite: int = MAX_PALAVRAS) -> list[dict]:
    respostas: Counter = Counter()
    formas: dict[str, Counter] = defaultdict(Counter)
    for texto in textos:
        vistas = set()
        for palavra in _PALAVRA.findall((texto or "").lower()):
            chave = sem_acento(palavra)
            if len(chave) < 3 or chave in COMUNS:
                continue
            formas[chave][palavra] += 1
            vistas.add(chave)
        respostas.update(vistas)
    mais = sorted(respostas.items(), key=lambda kv: (-kv[1], kv[0]))[:limite]
    return [{"palavra": _forma(formas[chave]), "total": total} for chave, total in mais]
