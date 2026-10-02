"""Limites das perguntas ao assistente, em memória do processo (cada processo da API conta os seus).

- Por minuto (`limite`): 8 por usuário, janela deslizante. Vale com RATE_LIMIT_ENABLED (desligado nos testes); `ligado`
  sobrepõe a configuração e `zerar()` limpa as contagens.
- Em andamento (`em_andamento`): a rota é síncrona e cada pergunta segura uma thread da API por até 60 s (o processo
  tem umas 40), então no máximo 2 perguntas em andamento por usuário e 6 no processo (semáforo, tentado sem esperar
  vaga). Vale sempre. Quem entra sai sempre (finally).
"""
import threading
import time
from collections import deque

from toqqi.core.config import config

MAX_POR_MINUTO = 8
JANELA = 60.0  # segundos
MAX_SIMULTANEAS = 6  # perguntas em andamento ao mesmo tempo, por processo
MAX_POR_USUARIO = 2  # perguntas em andamento ao mesmo tempo, por usuário


class LimitePorMinuto:
    def __init__(self, maximo: int = MAX_POR_MINUTO, janela: float = JANELA):
        self.maximo = maximo
        self.janela = janela
        self.ligado: bool | None = None  # None = segue RATE_LIMIT_ENABLED
        self.relogio = time.monotonic  # os testes trocam
        self._vezes: dict[object, deque] = {}
        self._trava = threading.Lock()

    def ativo(self) -> bool:
        return config().RATE_LIMIT_ENABLED if self.ligado is None else self.ligado

    def permitir(self, chave) -> bool:
        """Conta mais uma pergunta de `chave` se ainda cabe na janela; False se passou do limite."""
        if not self.ativo():
            return True
        agora = self.relogio()
        with self._trava:
            vezes = self._vezes.setdefault(chave, deque())
            while vezes and agora - vezes[0] >= self.janela:
                vezes.popleft()
            if len(vezes) >= self.maximo:
                return False
            vezes.append(agora)
            if len(self._vezes) > 5000:  # quem não pergunta há mais de um minuto sai da memória
                for k in [k for k, v in self._vezes.items() if not v or agora - v[-1] >= self.janela]:
                    del self._vezes[k]
            return True

    def zerar(self) -> None:
        with self._trava:
            self._vezes.clear()


class EmAndamento:
    """Vagas das perguntas em andamento: `por_usuario` de cada usuário e `simultaneas` no processo (semáforo)."""

    def __init__(self, simultaneas: int = MAX_SIMULTANEAS, por_usuario: int = MAX_POR_USUARIO):
        self.por_usuario = por_usuario
        self._vagas = threading.BoundedSemaphore(simultaneas)
        self._do_usuario: dict[object, int] = {}
        self._trava = threading.Lock()

    def entrar(self, chave) -> str | None:
        """Tenta, sem esperar, uma vaga de `chave` e uma do processo. None = entrou (quem chama SEMPRE chama `sair`
        depois, em finally); "usuario" = `chave` já tem `por_usuario` perguntas em andamento; "processo" = as vagas do
        processo estão ocupadas. Recusada, não ocupa nada."""
        with self._trava:
            n = self._do_usuario.get(chave, 0)
            if n >= self.por_usuario:
                return "usuario"
            if not self._vagas.acquire(blocking=False):
                return "processo"
            self._do_usuario[chave] = n + 1
            return None

    def sair(self, chave) -> None:
        """Devolve as vagas que `entrar` deu a `chave`."""
        with self._trava:
            n = self._do_usuario.pop(chave, 0) - 1
            if n > 0:
                self._do_usuario[chave] = n
            self._vagas.release()

    def ocupadas(self, chave=None) -> int:
        """Perguntas em andamento de `chave` (ou de todo o processo, sem `chave`)."""
        with self._trava:
            return self._do_usuario.get(chave, 0) if chave is not None else sum(self._do_usuario.values())


limite = LimitePorMinuto()
em_andamento = EmAndamento()
