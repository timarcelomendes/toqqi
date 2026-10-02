"""Limite de tamanho do corpo por rota (middleware ASGI), para as rotas públicas que só recebem pouco texto.

O corpo é contado à medida que chega, sem juntar tudo na memória: passou do limite (pelos pedaços recebidos ou pelo
Content-Length declarado), a leitura do corpo dentro da rota levanta HTTPException 413 e o tratador de sempre
(`core.errors`) responde `pedido_grande_demais` no formato padrão de erro, com os cabeçalhos de CORS."""
import re
from collections.abc import Iterable

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class LimiteDeCorpo:
    """`rotas`: (método, caminho como expressão regular, máximo em bytes); o caminho precisa casar inteiro."""

    def __init__(self, app: ASGIApp, rotas: Iterable[tuple[str, str, int]]):
        self.app = app
        self.rotas = [(metodo.upper(), re.compile(caminho), maximo) for metodo, caminho, maximo in rotas]

    def _maximo(self, scope: Scope) -> int | None:
        for metodo, caminho, maximo in self.rotas:
            if scope["method"] == metodo and caminho.fullmatch(scope["path"]):
                return maximo
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        maximo = self._maximo(scope) if scope["type"] == "http" else None
        if maximo is None:
            await self.app(scope, receive, send)
            return
        declarado = dict(scope["headers"]).get(b"content-length", b"")
        lidos = 0

        async def receber() -> Message:
            nonlocal lidos
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                lidos += len(mensagem.get("body", b""))
                if lidos > maximo or (declarado.isdigit() and int(declarado) > maximo):
                    raise HTTPException(413)
            return mensagem

        await self.app(scope, receber, send)
