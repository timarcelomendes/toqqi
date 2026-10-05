"""Aviso de erros (etapa 5h, docs/api-etapa-5h.md §4): o registro das falhas da API, do site e das tarefas em `erros`.

Guardamos só o que diagnostica, **sem dados pessoais** (nada do corpo, da query string, dos cabeçalhos nem o IP):
`origem` (`api` | `site` | `tarefa`), `tipo` (a classe do erro), `mensagem` limpa, `local` (a rota com o modelo do
caminho, `GET /api/v1/acoes/{acao_id}`; a tela sem query nem hash; ou o nome da tarefa), `pilha` limpa, `versao` (o
commit curto do Render ou "local"; no site, a do build), a contagem, a primeira e a última vez, o último request id e a
conta (quando se sabe). 30 dias depois da última ocorrência, a tarefa `limpeza` apaga (`limpar_antigos`).

Limpeza dos textos (`limpar`): viram `…` o texto entre aspas ("…", '…', “…”, ‘…’, «…»), e-mails (`\\S+@\\S+`, também
com `%40`), UUIDs, tokens longos (20+ letras e números seguidos; com `-` ou `_` no meio, quando há algum dígito) e as
sequências de 4+ dígitos, também com pontos, traços, barras, espaços ou parênteses entre eles (CPF, CNPJ, telefone, CEP,
datas, IP) — menos o código do erro do banco ("SQLSTATE 23514", do resumo de `log_seguro`). Nos endereços (`http…`), a
query string e o hash saem. Espaços em sequência viram um. Erro do banco (na cadeia da exceção) guarda só o resumo sem
dados (`log_seguro.descrever_erro`: classe, SQLSTATE e os nomes da restrição, tabela e coluna), nunca a mensagem dele,
que traz valores das linhas.

Pilha:
- API e tarefas: montada dos quadros do traceback, a chamada mais recente primeiro, uma linha por quadro no formato
  `funcao (arquivo:linha)` — só os quadros do Toqqi (`toqqi/…`) e o mais interno de todos (onde a exceção nasceu, às
  vezes numa biblioteca). Só nomes de arquivo e de função: nunca a linha de código nem os valores das variáveis, por isso
  não passa pela limpeza (ela comeria os números de linha e os nomes longos de função).
- Site: o `error.stack` do navegador, linha a linha: o `:linha:coluna` do fim fica; a origem dos endereços, a query e o
  hash saem; o resto passa pela limpeza.

Impressão (decisão desta etapa): sha256 de origem, tipo, local e a primeira linha útil da pilha **sem o número da linha
nem a coluna** (e, no site, sem o hash do nome do arquivo do build). Linha útil = o primeiro quadro do nosso código
(`toqqi/…` na API; `/assets/…` ou `/src/…` no site); sem nenhum, o primeiro da pilha. Assim a mesma falha continua
sendo o mesmo erro depois de um deploy que mude as linhas do arquivo; duas falhas do mesmo tipo na mesma função e na mesma
rota viram um erro só (o registro mostra a mensagem e a pilha da última). No site, os nomes de função vêm minificados e
podem mudar a cada build: o mesmo erro pode aparecer como novo depois de um deploy do site.

Registro (`registrar`): upsert pela impressão (+1 em `ocorrencias`, `ultima_em` = agora, mensagem, pilha, versão e
request id da última; uma ocorrência nova reabre o resolvido) numa conexão própria, em modo sistema, do engine pequeno
`db.engine_erros` (a do pedido pode estar quebrada ou o pool principal esgotado). **Nunca lança**: a falha só vai ao
log, e depois dela o registro descansa 10 s (`ESPERA_FALHA`; com o banco fora, cada pedido com erro não espera a
conexão). No máximo 200 registros por minuto por processo (`LIMITE_POR_MINUTO`): o resto só conta no log (um aviso
quando o limite é atingido e o total que ficou de fora quando o minuto vira).
"""
import hashlib
import logging
import os
import re
import threading
import time
import traceback
from pathlib import Path

from sqlalchemy import text

from toqqi.core import log_seguro
from toqqi.core.db import engine_erros, modo_sistema

log = logging.getLogger("toqqi.erros")

ORIGENS = ("api", "site", "tarefa")
MAX_TIPO = 80
MAX_MENSAGEM = 300
MAX_LOCAL = 200
MAX_PILHA = 1000
MAX_VERSAO = 40
MAX_REQUEST_ID = 64
LIMITE_POR_MINUTO = 200
ESPERA_FALHA = 10.0  # segundos sem tentar registrar depois de uma falha do banco
DIAS_GUARDADOS = 30
OCULTO = "…"

RAIZ_TOQQI = Path(__file__).resolve().parents[1]  # api/toqqi
RAIZ_API = RAIZ_TOQQI.parent

# ---- limpeza dos textos -----------------------------------------------------------------------------------------

_URL = re.compile(r"https?://[^\s\"'<>()]+")
_ASPAS = re.compile(r"\"[^\"\n]*\"|'[^'\n]*'|“[^”\n]*”|‘[^’\n]*’|«[^»\n]*»")
_EMAIL = re.compile(r"\S+(?:@|%40)\S+")
_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_TOKEN_SIMPLES = re.compile(r"[A-Za-z0-9]{20,}")
_TOKEN_COM_SEPARADOR = re.compile(r"[A-Za-z0-9_-]{20,}")
# Começa no primeiro dígito da sequência; o código SQLSTATE do resumo dos erros do banco (`log_seguro.descrever_erro`:
# "SQLSTATE 23514") não é dado de ninguém e diz qual foi o erro, então fica.
_NUMERO = re.compile(r"(?<!SQLSTATE )(?<!\d)\d[\d.\-/() ]*\d")
_ESPACOS = re.compile(r"\s+")


def _sem_query(m: re.Match) -> str:
    return re.split(r"[?#]", m.group(0), maxsplit=1)[0]


def _token(m: re.Match) -> str:
    trecho = m.group(0)
    return OCULTO if any(c.isdigit() for c in trecho) else trecho


def _numero(m: re.Match) -> str:
    """4+ dígitos no trecho (que começa e termina num dígito; o "(" da ponta fica de fora: "(11) 9…" vira "(…")."""
    trecho = m.group(0)
    return OCULTO if sum(c.isdigit() for c in trecho) >= 4 else trecho


def _cortar(texto: str, maximo: int) -> str:
    return texto if len(texto) <= maximo else texto[: maximo - 1].rstrip() + OCULTO


def _limpar_trecho(texto: str) -> str:
    """As regras da limpeza, sem mexer nos espaços nem nas quebras de linha."""
    t = _URL.sub(_sem_query, texto)
    t = _EMAIL.sub(OCULTO, t)
    t = _ASPAS.sub(OCULTO, t)
    t = _UUID.sub(OCULTO, t)
    t = _TOKEN_SIMPLES.sub(OCULTO, t)
    t = _TOKEN_COM_SEPARADOR.sub(_token, t)
    return _NUMERO.sub(_numero, t)


def limpar(texto: object, maximo: int = MAX_MENSAGEM) -> str:
    """Texto de uma linha sem dados pessoais (regras no cabeçalho), com os espaços juntados e no máximo `maximo`."""
    if texto is None:
        return ""
    return _cortar(_ESPACOS.sub(" ", _limpar_trecho(str(texto))).strip(), maximo)


_FIM_LOCAL = re.compile(r"(:\d+(?::\d+)?\)?)$")
_ORIGEM = re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s()]+")
# Firefox e Safari: "funcao@https://site/assets/x.js" (sem o "@" separado, a regra dos e-mails comeria a linha)
_QUADRO_COM_ARROBA = re.compile(r"^(?P<funcao>[^@]*)@(?P<endereco>(?:[a-z][a-z0-9+.-]*://|/)\S*)$")
# O hash do build no nome dos arquivos do site ("ContatoView-B2x9kQ1z.js"): muda a cada deploy e, com dígitos, a regra
# dos tokens comeria o nome inteiro. Sai antes da limpeza ("ContatoView.js"); a versão do build vai em `versao`.
_HASH_DO_BUILD = re.compile(r"-[A-Za-z0-9_-]{8}(?=\.m?js\b)")


def _endereco(texto: str) -> str:
    """Endereço de um quadro: sem a origem, a query, o hash e o hash do build; o caminho passa pela limpeza (tokens,
    números)."""
    return _limpar_trecho(_HASH_DO_BUILD.sub("", _ORIGEM.sub("", re.split(r"[?#]", texto, maxsplit=1)[0])))


def limpar_pilha(texto: object, maximo: int = MAX_PILHA) -> str:
    """Pilha do site, linha a linha: o `:linha:coluna` do fim fica; a origem dos endereços, a query, o hash e o hash do
    build no nome dos arquivos saem; o resto passa pela limpeza. Linhas vazias saem; no máximo `maximo`."""
    if texto is None:
        return ""
    linhas = []
    for bruta in str(texto).splitlines():
        linha = bruta.strip()
        if not linha:
            continue
        m = _FIM_LOCAL.search(linha)
        fim = m.group(1) if m else ""
        corpo = linha[: len(linha) - len(fim)] if fim else linha
        quadro = _QUADRO_COM_ARROBA.match(corpo)
        if quadro:
            corpo = f"{_limpar_trecho(quadro['funcao'])}@{_endereco(quadro['endereco'])}"
        else:
            corpo = _limpar_trecho(_HASH_DO_BUILD.sub("", _ORIGEM.sub("", _URL.sub(_sem_query, corpo))))
        corpo = _ESPACOS.sub(" ", corpo).strip()
        if corpo or fim:
            linhas.append(corpo + fim)
    return _cortar("\n".join(linhas), maximo)


def limpar_local(texto: object) -> str:
    """O local (rota, tela ou tarefa): sem query nem hash, limpo, até 200."""
    bruto = re.split(r"[?#]", str(texto or ""), maxsplit=1)[0]
    return limpar(bruto, MAX_LOCAL)


# ---- pilha da API e impressão ------------------------------------------------------------------------------------

def _arquivo(caminho: str) -> str:
    """Caminho do quadro relativo à API (`toqqi/…`) ou ao site-packages (`sqlalchemy/…`); senão, só o nome."""
    p = Path(caminho)
    try:
        return p.resolve().relative_to(RAIZ_API).as_posix()
    except (ValueError, OSError):
        pass
    partes = p.parts
    for marca in ("site-packages", "dist-packages"):
        if marca in partes:
            return "/".join(partes[partes.index(marca) + 1:])
    return p.name


# Os middlewares do Toqqi, por onde passa todo pedido: aparecem em toda pilha da API e não dizem nada.
QUADROS_DE_TODO_PEDIDO = frozenset({"toqqi/main.py", "toqqi/core/limite_corpo.py", "toqqi/core/requisicao.py"})


def pilha_python(exc: BaseException, maximo: int = MAX_PILHA) -> str:
    """A pilha da exceção (regras no cabeçalho): a chamada mais recente primeiro, só os quadros do Toqqi (menos os dos
    middlewares, iguais em todo pedido) e o mais interno de todos, `funcao (arquivo:linha)` por linha."""
    quadros = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ is not None else []
    linhas = []
    for i, q in enumerate(reversed(quadros)):
        arquivo = _arquivo(q.filename)
        if i == 0 or (arquivo.startswith("toqqi/") and arquivo not in QUADROS_DE_TODO_PEDIDO):
            linhas.append(f"{q.name} ({arquivo}:{q.lineno})")
    return _cortar("\n".join(linhas), maximo)


_POSICAO = re.compile(r":\d+(?::\d+)?(?=\)?$)")


def linha_util(origem: str, pilha: str) -> str:
    """A primeira linha do nosso código na pilha (sem nenhuma, a primeira), sem `:linha:coluna`, sem a origem e sem o
    hash do build."""
    linhas = [x.strip() for x in (pilha or "").splitlines() if x.strip()]
    if origem == "site":
        nossas = [x for x in linhas if "/assets/" in x or "/src/" in x]
    else:
        nossas = [x for x in linhas if "(toqqi/" in x]
    escolhida = (nossas or linhas or [""])[0]
    escolhida = _POSICAO.sub("", _ORIGEM.sub("", escolhida))
    return _HASH_DO_BUILD.sub("", escolhida).strip()


def impressao(origem: str, tipo: str, local: str, pilha: str) -> str:
    base = "\n".join((origem, tipo, local, linha_util(origem, pilha)))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def versao_api() -> str:
    """O commit do Render (`RENDER_GIT_COMMIT`), curto; fora do Render, "local"."""
    commit = re.sub(r"[^0-9A-Za-z]", "", os.environ.get("RENDER_GIT_COMMIT", ""))
    return commit[:7] or "local"


def _versao(v: object, origem: str) -> str:
    """A versão informada (só letras, números, ponto, traço e sublinhado; até 40); sem ela, a da API (no site,
    "desconhecida": a versão do site não é a da API)."""
    limpa = re.sub(r"[^0-9A-Za-z._-]", "", str(v or ""))[:MAX_VERSAO]
    return limpa or ("desconhecida" if origem == "site" else versao_api())


# ---- registro ---------------------------------------------------------------------------------------------------

_UPSERT = text("""
    INSERT INTO erros (impressao, origem, tipo, mensagem, local, pilha, versao, ultimo_request_id, conta_id)
    VALUES (:impressao, :origem, :tipo, :mensagem, :local, :pilha, :versao, :request_id, :conta_id)
    ON CONFLICT (impressao) DO UPDATE SET
        ocorrencias = LEAST(erros.ocorrencias + 1, 2147483647),
        ultima_em = now(),
        mensagem = excluded.mensagem,
        pilha = excluded.pilha,
        versao = excluded.versao,
        ultimo_request_id = excluded.ultimo_request_id,
        conta_id = coalesce(excluded.conta_id, erros.conta_id),
        resolvido_em = NULL
""")


def _monotonico() -> float:
    """O relógio do limite e do descanso (os testes trocam)."""
    return time.monotonic()


class _Controle:
    """Limite por minuto e descanso depois de uma falha (por processo; várias threads registram ao mesmo tempo)."""

    def __init__(self):
        self.trava = threading.Lock()
        self.limpar()

    def limpar(self) -> None:
        self.minuto = -1
        self.registrados = 0
        self.fora = 0
        self.descanso_ate = 0.0

    def pode(self) -> bool:
        agora = _monotonico()
        minuto = int(agora // 60)
        with self.trava:
            if minuto != self.minuto:
                if self.fora:
                    log.warning("Aviso de erros: %d erro(s) do último minuto não foram registrados (passaram do "
                                "limite de %d por minuto ou o banco não respondeu); só contam aqui no log.",
                                self.fora, LIMITE_POR_MINUTO)
                self.minuto, self.registrados, self.fora = minuto, 0, 0
            if agora < self.descanso_ate:
                self.fora += 1
                return False
            if self.registrados >= LIMITE_POR_MINUTO:
                self.fora += 1
                if self.fora == 1:
                    log.warning("Aviso de erros: limite de %d registros por minuto atingido; os próximos deste minuto "
                                "só contam no log.", LIMITE_POR_MINUTO)
                return False
            self.registrados += 1
            return True

    def falhou(self) -> None:
        with self.trava:
            self.descanso_ate = _monotonico() + ESPERA_FALHA


_controle = _Controle()


def limpar_estado() -> None:
    """Zera o limite por minuto e o descanso (testes)."""
    _controle.limpar()


def registrar(origem: str, tipo: str, mensagem: object = "", local: object = "", pilha: object = "",
              versao: object = None, conta_id: int | None = None, request_id: str | None = None) -> bool:
    """Registra (ou soma) a ocorrência. Os textos são limpos aqui (a pilha da API e das tarefas, montada por
    `pilha_python`, já vem sem dados). Devolve se registrou; **nunca lança** (a falha só vai ao log)."""
    try:
        if origem not in ORIGENS:
            raise ValueError(f"origem de erro desconhecida: {origem}")
        tipo_limpo = limpar(tipo, MAX_TIPO) or "Error"
        local_limpo = limpar_local(local)
        pilha_limpa = limpar_pilha(pilha) if origem == "site" else _cortar(str(pilha or ""), MAX_PILHA)
        params = {
            "impressao": impressao(origem, tipo_limpo, local_limpo, pilha_limpa),
            "origem": origem, "tipo": tipo_limpo, "mensagem": limpar(mensagem, MAX_MENSAGEM),
            "local": local_limpo, "pilha": pilha_limpa, "versao": _versao(versao, origem),
            "request_id": (str(request_id)[:MAX_REQUEST_ID] or None) if request_id else None,
            "conta_id": int(conta_id) if conta_id is not None else None,
        }
    except Exception as e:  # noqa: BLE001 - o registro nunca derruba o pedido nem a tarefa
        log.warning("Aviso de erros: não foi possível registrar um erro (%s: %s).", type(e).__name__, limpar(e, 120))
        return False
    if not _controle.pode():
        return False
    try:
        with engine_erros().begin() as c:
            c.execute(text("select set_config('app.sistema', 'on', true)"))
            c.execute(text("SET LOCAL statement_timeout = '2s'"))
            c.execute(_UPSERT, params)
        return True
    except Exception as e:  # noqa: BLE001 - idem; e o banco descansa um pouco (o próximo erro não espera a conexão)
        _controle.falhou()
        log.warning("Aviso de erros: não foi possível registrar um erro (%s: %s).", type(e).__name__,
                    log_seguro.descrever_erro(e) if log_seguro.do_banco(e) else limpar(e, 120))
        return False


def _cadeia(exc: BaseException):
    vistos: set[int] = set()
    e: BaseException | None = exc
    while e is not None and id(e) not in vistos:
        vistos.add(id(e))
        yield e
        e = e.__cause__ or (None if e.__suppress_context__ else e.__context__)


def mensagem_da_excecao(exc: BaseException) -> str:
    """A mensagem a guardar: com um erro do banco na cadeia, o resumo sem dados dele (`log_seguro.descrever_erro`:
    classe, SQLSTATE e nomes); senão o texto da exceção (limpo depois, em `registrar`). O `KeyError` põe a chave entre
    aspas no texto (e a limpeza esconderia tudo): vale o texto da chave, limpo do mesmo jeito."""
    banco = next((e for e in _cadeia(exc) if log_seguro.do_banco(e)), None)
    if banco is not None:
        return log_seguro.descrever_erro(banco)
    if isinstance(exc, KeyError) and len(exc.args) == 1 and isinstance(exc.args[0], str):
        return exc.args[0]
    return str(exc)


def registrar_excecao(exc: BaseException, origem: str, local: str, conta_id: int | None = None,
                      request_id: str | None = None) -> bool:
    """`registrar` com o tipo, a mensagem e a pilha tirados da exceção (API e tarefas). Nunca lança."""
    try:
        tipo, mensagem, pilha = type(exc).__name__, mensagem_da_excecao(exc), pilha_python(exc)
    except Exception:  # noqa: BLE001 - até montar os textos pode falhar (str() de uma exceção estranha)
        tipo, mensagem, pilha = type(exc).__name__, "", ""
    return registrar(origem, tipo, mensagem, local, pilha, versao_api(), conta_id, request_id)


def limpar_antigos(dias: int = DIAS_GUARDADOS) -> int:
    """Tarefa `limpeza`: apaga os erros com a última ocorrência há mais de `dias` dias. Devolve quantos apagou."""
    with modo_sistema() as s:
        return s.execute(text("DELETE FROM erros WHERE ultima_em < now() - make_interval(days => :d)"),
                         {"d": dias}).rowcount
