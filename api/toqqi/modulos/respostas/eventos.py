"""Ponto único "resposta registrada".

Toda resposta nova gravada por `gravar_resposta` passa por `ao_registrar_resposta`, dentro da mesma transação
que a gravou. Os ganchos (agradecimento e fila de envios, webhooks, ação automática + alerta) conferem
`resposta.origem`:
- `pesquisa` (páginas públicas): todos os efeitos;
- `manual` (registrada por alguém da conta): tudo, menos o agradecimento por e-mail;
- `importacao` (histórico): nenhum efeito. A importação grava em lote e não chama os ganchos; eles ignoram
  essa origem de qualquer forma.
"""
from collections.abc import Callable

from sqlalchemy.orm import Session

from toqqi.modelos import Resposta

Gancho = Callable[[Session, Resposta], None]
GANCHOS: list[Gancho] = []


def ao_registrar_resposta(sessao: Session, resposta: Resposta) -> None:
    for gancho in list(GANCHOS):
        gancho(sessao, resposta)
