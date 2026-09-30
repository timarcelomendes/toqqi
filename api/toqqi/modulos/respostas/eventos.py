"""Ponto único "resposta registrada".

Toda resposta nova passa por `ao_registrar_resposta`, dentro da mesma transação que a gravou.
As etapas 3 e 4 penduram aqui os efeitos seguintes (plano de ação, alertas, agradecimento).
"""
from collections.abc import Callable

from sqlalchemy.orm import Session

from toqqi.modelos import Resposta

Gancho = Callable[[Session, Resposta], None]
GANCHOS: list[Gancho] = []


def ao_registrar_resposta(sessao: Session, resposta: Resposta) -> None:
    for gancho in list(GANCHOS):
        gancho(sessao, resposta)
