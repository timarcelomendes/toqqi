"""Paginação padrão das listas: ?pagina=1&por_pagina=50 → {itens, total, pagina, por_pagina}."""
from dataclasses import dataclass
from typing import Annotated

from fastapi import Query

POR_PAGINA_MAX = 200


@dataclass
class Pagina:
    pagina: int
    por_pagina: int

    @property
    def offset(self) -> int:
        return (self.pagina - 1) * self.por_pagina

    def resultado(self, itens: list, total: int) -> dict:
        return {"itens": itens, "total": total, "pagina": self.pagina, "por_pagina": self.por_pagina}


def pagina(
    pagina: Annotated[int, Query(ge=1, le=100000)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=POR_PAGINA_MAX)] = 50,
) -> Pagina:
    return Pagina(pagina, por_pagina)
