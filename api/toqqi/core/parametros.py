"""Parâmetros da plataforma (etapa 5g): preços e limites dos planos, IA, WhatsApp automático e teste, editáveis pela
equipe Toqqi em Plataforma › Parâmetros (serviço e rotas em `modulos.plataforma.parametros`).

Valor de cada chave = linha em `parametros` > variável de ambiente (só as que já existiam) > código. O banco guarda
só o que difere do padrão: salvar um valor igual ao padrão apaga a linha (a chave volta a seguir o padrão). Tabela
vazia = tudo como antes da 5g.

- `CAMPOS`: chave → `Campo` (grupo, tipo, limites e o padrão). Grupo = primeiro pedaço da chave (`GRUPOS`, nesta
  ordem); todas as chaves de um grupo vão juntas na tela e no PUT.
- `padrao(chave)`: o padrão de hoje, lido de `config()` a cada chamada (variável > código); `origem(chave)`: "banco"
  (há linha), "ambiente" (a variável que dá o padrão foi definida: `config().model_fields_set`) ou "codigo".
- `valor(chave)` e `grupo(nome)`: o valor efetivo, com as linhas do banco em cache (abaixo); `validar(grupo, valores)`:
  as regras do §2 (422 `dados_invalidos`, `campos` pela chave; chave que falta ou sobra → campo `valores`).
- Tipos: `dinheiro` (Decimal com 2 casas; no banco e nas rotas, texto "149.00"), `contatos` (inteiro ou None = sem
  limite), `inteiro`, `modelo` e `esforco` (texto), `plano` (uma das chaves de `PLANOS`) e `exclusao` (ligada | simular).

Cache das linhas (revisão da 5g): lidas pelo engine próprio dos parâmetros (`db.engine_parametros`: pool de 1 conexão,
3 s de espera; nunca o pool principal, de que quem chamou pode estar segurando uma conexão dentro de `em_conta`), numa
transação curta em modo sistema, e válidas por `CACHE_SEGUNDOS` (relógio monotônico). Uma leitura por vez: com o cache
vencido, uma thread lê e as outras seguem com os últimos valores enquanto isso; sem valor nenhum ainda, esperam a
leitura em andamento. Quem salva chama `invalidar()` depois do commit e vê na hora (a leitura que já estava em andamento
não conta como nova); os outros processos (outro worker, as tarefas pela linha de comando) veem em até 30 s. A API lê ao
subir (`aquecer`). Falha ao ler: valem os últimos valores (log de aviso) e a próxima tentativa só depois de
`ESPERA_FALHA` (5 s); sem nenhuma leitura boa, sobe `ParametrosIndisponiveis` (cair no padrão em silêncio cobraria o
preço errado), também durante a espera.

Linha fora do formato (só gravada à mão): chave desconhecida é ignorada e as outras valem o padrão (log de erro), menos o
preço, que nunca cai no padrão por isso: fica o último valor bom lido ou, sem leitura anterior, `valor` daquela chave
sobe `ParametroInvalido`. A tela mostra o padrão no lugar dela e o PUT do grupo apaga as linhas fora do formato do
grupo. O limite de contatos do banco (função `limite_contatos`, usada pelo gatilho) lê a tabela direto, sem cache, e
aceita as mesmas linhas que o Python (número inteiro de 1 a 1.000.000 ou null; o resto vale o padrão).
"""
import logging
import re
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from toqqi.core import db
from toqqi.core.config import config
from toqqi.core.errors import AppError
from toqqi.modelos import Parametro

log = logging.getLogger("toqqi.parametros")

CACHE_SEGUNDOS = 30
ESPERA_FALHA = 5  # depois de uma leitura que falhou, quanto esperar para tentar de novo (valem os últimos valores)
ESPERA_PRIMEIRA = 10  # sem valor nenhum, quanto esperar pela leitura que outra thread está fazendo
TEMPO_LEITURA_MS = 3000  # statement_timeout da leitura do cache
monotonico = time.monotonic  # os testes trocam (relógio falso)


class ParametrosIndisponiveis(RuntimeError):
    """Nenhuma leitura boa dos parâmetros neste processo e a última tentativa falhou (ou foi há menos de 5 s)."""


class ParametroInvalido(RuntimeError):
    """O preço gravado no banco está fora do formato e não há valor bom lido antes dele: não dá para cobrar."""

GRUPOS = {"planos": "Planos", "ia": "IA", "whatsapp": "WhatsApp automático", "teste": "Teste e cortesia"}
PLANOS = ("essencial", "profissional", "empresa")
NOMES_PLANOS = {"essencial": "Essencial", "profissional": "Profissional", "empresa": "Empresa"}
NIVEIS = ("rapido", "equilibrado", "detalhado")
ESFORCOS = ("", "none", "minimal", "low", "medium", "high", "xhigh")
MODOS_EXCLUSAO = ("ligada", "simular")
RE_MODELO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,99}")

PRECO_MIN = Decimal("5.00")
PRECO_MAX = Decimal("99999.99")
CENTAVOS = Decimal("0.01")

# padrões do código (antes em core.planos, ia.cota, ia.regras, whatsapp.franquia, acesso.servico e assinatura.servico)
PRECOS = {"essencial": Decimal("149.00"), "profissional": Decimal("349.00"), "empresa": Decimal("799.00")}
CONTATOS = {"essencial": 300, "profissional": 1500, "empresa": None}  # o mesmo da função limite_contatos (0002)
COTAS = {"essencial": 100, "profissional": 500, "empresa": 2000}
TETOS = {"essencial": 1000, "profissional": 5000, "empresa": 20000, "cortesia": 5000, "teste": 1000}
FRANQUIAS = {"essencial": 40, "profissional": 90, "empresa": 200, "cortesia": 200, "teste": 20}
DIAS_TESTE = 14
PLANO_DO_TESTE = "profissional"

MSG_INVALIDOS = "Confira os campos destacados."


@dataclass(frozen=True)
class Campo:
    chave: str
    tipo: str  # dinheiro | contatos | inteiro | modelo | esforco | plano | exclusao
    padrao: Callable[[], tuple[object, tuple[str, ...]]]  # (valor, variáveis lidas até achar o valor)
    minimo: int = 0
    maximo: int = 0

    @property
    def grupo(self) -> str:
        return self.chave.split(".", 1)[0]


def _codigo(v) -> Callable[[], tuple[object, tuple[str, ...]]]:
    return lambda: (v, ())


def _variavel(*nomes: str, vazio_vale: bool = False) -> Callable[[], tuple[object, tuple[str, ...]]]:
    """O primeiro valor não vazio entre as variáveis (a regra de `ia_texto.modelo_do_nivel` de antes); `vazio_vale`:
    a última vale mesmo vazia (esforço vazio = sem `reasoning`)."""
    def ler():
        cfg = config()
        for i, nome in enumerate(nomes):
            v = str(getattr(cfg, nome)).strip()
            if v or (vazio_vale and i == len(nomes) - 1):
                return v, nomes[: i + 1]
        return "", nomes
    return ler


def _cota_cortesia():
    return max(0, int(config().IA_COTA_CORTESIA)), ("IA_COTA_CORTESIA",)


def _exclusao():
    return ("ligada" if config().EXCLUSAO_AUTOMATICA == "ligada" else "simular"), ("EXCLUSAO_AUTOMATICA",)


def _analises(nivel: str):
    def ler():
        from toqqi.core import ia_texto  # ia_texto lê os parâmetros: import tardio
        return next(o.analises for o in ia_texto.MODELOS if o.valor == nivel), ()
    return ler


_MODELO = {"rapido": ("IA_MODELO_RAPIDO", "IA_ASSISTENTE_MODELO"),
           "equilibrado": ("IA_MODELO_EQUILIBRADO", "IA_ASSISTENTE_MODELO"),
           "detalhado": ("IA_MODELO_DETALHADO", "IA_ASSISTENTE_MODELO")}
_ESFORCO = {"rapido": ("IA_ESFORCO_RAPIDO",), "equilibrado": ("IA_ESFORCO_EQUILIBRADO", "IA_ASSISTENTE_ESFORCO"),
            "detalhado": ("IA_ESFORCO_DETALHADO",)}


def _montar() -> dict[str, Campo]:
    campos: list[Campo] = []
    for p in PLANOS:
        campos += [Campo(f"planos.{p}.preco", "dinheiro", _codigo(PRECOS[p])),
                   Campo(f"planos.{p}.contatos", "contatos", _codigo(CONTATOS[p]), 1, 1_000_000)]
    campos += [Campo(f"ia.cota.{p}", "inteiro", _codigo(COTAS[p]), 0, 100_000) for p in PLANOS]
    campos.append(Campo("ia.cota.cortesia", "inteiro", _cota_cortesia, 0, 100_000))
    for n in NIVEIS:
        campos += [Campo(f"ia.modelo.{n}", "modelo", _variavel(*_MODELO[n])),
                   Campo(f"ia.esforco.{n}", "esforco", _variavel(*_ESFORCO[n], vazio_vale=True)),
                   Campo(f"ia.analises.{n}", "inteiro", _analises(n), 1, 10)]
    campos += [Campo(f"ia.teto.{p}", "inteiro", _codigo(TETOS[p]), 0, 1_000_000)
               for p in (*PLANOS, "cortesia", "teste")]
    campos += [Campo(f"whatsapp.franquia.{p}", "inteiro", _codigo(FRANQUIAS[p]), 0, 100_000)
               for p in (*PLANOS, "cortesia", "teste")]
    campos += [Campo("teste.dias", "inteiro", _codigo(DIAS_TESTE), 1, 90),
               Campo("teste.plano", "plano", _codigo(PLANO_DO_TESTE)),
               Campo("teste.exclusao_automatica", "exclusao", _exclusao)]
    return {c.chave: c for c in campos}


CAMPOS: dict[str, Campo] = _montar()


def chaves_do_grupo(nome: str) -> list[str]:
    return [c for c, campo in CAMPOS.items() if campo.grupo == nome]


# ---- padrões e formato ------------------------------------------------------------------------------------

def padrao(chave: str):
    """O padrão de hoje (variável > código), no tipo do Python."""
    return CAMPOS[chave].padrao()[0]


def _variavel_definida(chave: str) -> bool:
    definidas = config().model_fields_set
    return any(nome in definidas for nome in CAMPOS[chave].padrao()[1])


def para_json(chave: str, v):
    """Valor como vai ao banco e às rotas: dinheiro em texto com 2 casas ("149.00"); o resto como está."""
    if CAMPOS[chave].tipo == "dinheiro":
        return str(Decimal(v).quantize(CENTAVOS))
    return v


def do_json(chave: str, bruto):
    """Valor gravado no banco → tipo do Python (ValueError se não for do tipo da chave)."""
    return _converter(CAMPOS[chave], bruto)


def reais(v: Decimal) -> str:
    """Decimal("1234.5") → "R$ 1.234,50"."""
    texto = f"{Decimal(v).quantize(CENTAVOS):,.2f}"
    return "R$ " + texto.replace(",", "_").replace(".", ",").replace("_", ".")


def numero(n: int) -> str:
    """1500 → "1.500"."""
    return f"{n:,}".replace(",", ".")


def formatar(chave: str, v) -> str:
    """Para textos (Ajuda, mensagens): dinheiro "R$ 149,00", inteiro "1.500", null "sem limite", plano pelo nome."""
    tipo = CAMPOS[chave].tipo
    if v is None:
        return "sem limite"
    if tipo == "dinheiro":
        return reais(v)
    if tipo in ("contatos", "inteiro"):
        return numero(int(v))
    if tipo == "plano":
        return NOMES_PLANOS.get(v, str(v))
    return str(v)


# ---- validação ------------------------------------------------------------------------------------------

def _inteiro(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _msg_inteiro(campo: Campo) -> str:
    return f"Use um número inteiro de {numero(campo.minimo)} a {numero(campo.maximo)}."


def _converter(campo: Campo, v):
    """Confere e normaliza um valor (de quem salva ou do banco). ValueError com a mensagem do campo."""
    if campo.tipo == "dinheiro":
        formato = "Use um valor em reais com ponto e até 2 casas decimais, ex.: 149.90."
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            raise ValueError(formato)
        texto = v.strip() if isinstance(v, str) else repr(v)
        if re.fullmatch(r"\d{1,9}\.\d{3,}", texto):
            raise ValueError("Use no máximo 2 casas decimais.")
        if not re.fullmatch(r"\d{1,9}(\.\d{1,2})?", texto):
            raise ValueError(formato)
        try:
            d = Decimal(texto).quantize(CENTAVOS)
        except InvalidOperation:
            raise ValueError(formato) from None
        if not PRECO_MIN <= d <= PRECO_MAX:
            raise ValueError("Use um valor entre R$ 5,00 e R$ 99.999,99.")
        return d
    if campo.tipo == "contatos":
        if v is None:
            return None
        if not _inteiro(v) or not campo.minimo <= v <= campo.maximo:
            raise ValueError("Use um número inteiro de 1 a 1.000.000, ou marque “Sem limite”.")
        return v
    if campo.tipo == "inteiro":
        if not _inteiro(v) or not campo.minimo <= v <= campo.maximo:
            raise ValueError(_msg_inteiro(campo))
        return v
    if campo.tipo == "modelo":
        texto = v.strip() if isinstance(v, str) else None
        if not texto or not RE_MODELO.fullmatch(texto):
            raise ValueError("Informe o nome do modelo (até 100 caracteres: letras, números, ponto, hífen, "
                             "dois-pontos ou sublinhado).")
        return texto
    if campo.tipo == "esforco":
        texto = v.strip() if isinstance(v, str) else None
        if texto not in ESFORCOS:
            raise ValueError("Escolha um esforço da lista (ou “Sem raciocínio”).")
        return texto
    if campo.tipo == "plano":
        if v not in PLANOS:
            raise ValueError("Escolha um dos planos: Essencial, Profissional ou Empresa.")
        return v
    if v not in MODOS_EXCLUSAO:  # exclusao
        raise ValueError("Escolha “ligada” ou “simular”.")
    return v


def _maior(a, b) -> bool:
    """Limite de contatos `a` > `b` (None = sem limite, o maior)."""
    if a is None:
        return b is not None
    return b is not None and a > b


def _regras_dos_planos(limpos: dict, campos: dict[str, str]) -> None:
    """Preços crescentes (Essencial < Profissional < Empresa) e limites de contatos que não diminuem nessa ordem."""
    for menor, maior in zip(PLANOS, PLANOS[1:]):
        a, b = f"planos.{menor}.preco", f"planos.{maior}.preco"
        if a in limpos and b in limpos and limpos[b] <= limpos[a]:
            campos.setdefault(b, f"O preço do {NOMES_PLANOS[maior]} precisa ser maior que o do {NOMES_PLANOS[menor]}.")
        a, b = f"planos.{menor}.contatos", f"planos.{maior}.contatos"
        if a in limpos and b in limpos and _maior(limpos[a], limpos[b]):
            campos.setdefault(b, f"O limite do {NOMES_PLANOS[maior]} não pode ser menor que o do "
                                 f"{NOMES_PLANOS[menor]}.")


NOMES_NIVEIS = {"rapido": "Rápido", "equilibrado": "Equilibrado", "detalhado": "Mais detalhado"}


def _regras_dos_niveis(limpos: dict, campos: dict[str, str]) -> None:
    """Análises por uso que não diminuem do Rápido ao Mais detalhado (a sugestão de quando a cota não dá para o nível
    procura o mais barato que cabe)."""
    for menor, maior in zip(NIVEIS, NIVEIS[1:]):
        a, b = f"ia.analises.{menor}", f"ia.analises.{maior}"
        if a in limpos and b in limpos and limpos[b] < limpos[a]:
            campos.setdefault(b, f"O {NOMES_NIVEIS[maior]} não pode gastar menos análises que o "
                                 f"{NOMES_NIVEIS[menor]}.")


def validar(nome: str, valores) -> dict:
    """Todos os valores do grupo, conferidos e normalizados (tipo do Python), na ordem de `CAMPOS`. 422
    `dados_invalidos` com `campos` pela chave; chave que falta ou de fora do grupo → campo `valores`."""
    chaves = chaves_do_grupo(nome)
    if not isinstance(valores, dict):
        raise AppError(422, "dados_invalidos", MSG_INVALIDOS, {"valores": "Envie os valores do grupo."})
    faltam = [c for c in chaves if c not in valores]
    sobram = [c for c in valores if c not in chaves]
    if faltam or sobram:
        partes = ([f"Faltam: {', '.join(faltam)}."] if faltam else []) + (
            [f"Não são deste grupo: {', '.join(sorted(map(str, sobram)))}."] if sobram else [])
        raise AppError(422, "dados_invalidos", MSG_INVALIDOS, {"valores": " ".join(partes)})
    limpos: dict = {}
    campos: dict[str, str] = {}
    for c in chaves:
        try:
            limpos[c] = _converter(CAMPOS[c], valores[c])
        except ValueError as e:
            campos[c] = str(e)
    if nome == "planos":
        _regras_dos_planos(limpos, campos)
    if nome == "ia":
        _regras_dos_niveis(limpos, campos)
    if campos:
        raise AppError(422, "dados_invalidos", MSG_INVALIDOS, campos)
    return limpos


# ---- linhas do banco ----------------------------------------------------------------------------------------

def _separar(brutas: Iterable[tuple[str, object]]) -> tuple[dict[str, object], list[str]]:
    """(valores no tipo do Python das linhas válidas, chaves das linhas fora do formato ou desconhecidas)."""
    validas: dict[str, object] = {}
    invalidas: list[str] = []
    for chave, bruto in brutas:
        if chave not in CAMPOS:
            invalidas.append(chave)
            continue
        try:
            validas[chave] = do_json(chave, bruto)
        except ValueError:
            invalidas.append(chave)
    return validas, invalidas


def ler_banco(s: Session) -> dict[str, Parametro]:
    """As linhas de `parametros`, na transação dada (tela, prévia e PUT: sempre o banco, sem cache)."""
    return {p.chave: p for p in s.scalars(select(Parametro))}


def linhas_validas(linhas: dict[str, Parametro]) -> dict[str, object]:
    """As linhas válidas lidas na transação (tela, prévia e PUT); as fora do formato ficam de fora, com log de erro (a
    tela mostra o padrão no lugar delas e o PUT do grupo as apaga)."""
    validas, invalidas = _separar((c, p.valor) for c, p in linhas.items())
    for chave in invalidas:
        log.error("Parâmetros: a linha %r do banco está fora do formato (ou a chave não existe no código); a tela "
                  "mostra o padrão e salvar o grupo a apaga.", chave)
    return validas


def invalidas_do_grupo(nome: str, linhas: dict[str, Parametro]) -> list[str]:
    """As chaves do grupo com linha fora do formato, ou que o código não conhece (o PUT do grupo apaga)."""
    _, invalidas = _separar((c, p.valor) for c, p in linhas.items())
    return sorted(c for c in invalidas if c.split(".", 1)[0] == nome)


# ---- cache --------------------------------------------------------------------------------------------------

_cond = threading.Condition()  # protege o estado abaixo e acorda quem espera a primeira leitura
_linhas: dict[str, object] | None = None  # chave → valor (as válidas e, no preço fora do formato, o último bom)
_quebradas: frozenset[str] = frozenset()  # preços fora do formato sem valor bom lido antes: `valor` sobe
_lidas_em: float | None = None  # quando a leitura que está valendo começou (None = vencida)
_lendo = False  # uma thread está lendo (as outras não leem junto)
_falhou_em: float | None = None  # a última leitura falhou: só tenta de novo depois de ESPERA_FALHA
_erro: BaseException | None = None  # o erro dessa leitura (sobe junto quando não há valor nenhum)
_geracao = 0  # `invalidar` soma 1: a leitura que já estava em andamento não vale como nova
_epoca = 0  # `limpar` soma 1: a leitura em andamento é descartada


def _ler_do_banco() -> list[tuple[str, object]]:
    """As linhas de `parametros` pelo engine próprio (nunca o pool principal), em modo sistema e com tempo curto."""
    with Session(db.engine_parametros()) as s, s.begin():
        s.execute(text("select set_config('app.sistema', 'on', true), set_config('statement_timeout', :t, true)"),
                  {"t": str(TEMPO_LEITURA_MS)})
        return [(c, v) for c, v in s.execute(select(Parametro.chave, Parametro.valor))]


def _montar_cache(brutas, anteriores: dict | None, quebradas_antes: frozenset[str]) -> tuple[dict, frozenset[str]]:
    """O que fica no cache depois de uma leitura. Linha fora do formato: a chave desconhecida é ignorada e a outra vale
    o padrão (log de erro), menos o preço, que nunca cai no padrão por isso: fica o valor da leitura anterior (o da
    linha, ou o padrão se ela não tinha linha) ou, sem leitura anterior, a chave fica quebrada (`valor` sobe)."""
    linhas, invalidas = _separar(brutas)
    quebradas: set[str] = set()
    for chave in invalidas:
        campo = CAMPOS.get(chave)
        if campo is None:
            log.error("Parâmetros: a chave %r do banco não existe no código; ignorada.", chave)
        elif campo.tipo != "dinheiro":
            log.error("Parâmetros: o valor da chave %s no banco está fora do formato; vale o padrão.", chave)
        elif anteriores is None or chave in quebradas_antes:
            quebradas.add(chave)
            log.error("Parâmetros: o preço %s no banco está fora do formato e não há valor bom lido antes; quem "
                      "precisar dele recebe erro até corrigir em Plataforma › Parâmetros.", chave)
        else:
            if chave in anteriores:
                linhas[chave] = anteriores[chave]
            log.error("Parâmetros: o preço %s no banco está fora do formato; fica o último valor bom lido (corrija em "
                      "Plataforma › Parâmetros).", chave)
    return linhas, frozenset(quebradas)


def _do_cache() -> tuple[dict[str, object], frozenset[str]]:
    """(linhas, preços quebrados) do cache, lendo o banco quando venceu (uma thread por vez; ver o começo)."""
    global _linhas, _quebradas, _lidas_em, _lendo, _falhou_em, _erro
    with _cond:
        while True:
            agora = monotonico()
            if _linhas is not None and _lidas_em is not None and 0 <= agora - _lidas_em < CACHE_SEGUNDOS:
                return _linhas, _quebradas
            esperando = _falhou_em is not None and 0 <= agora - _falhou_em < ESPERA_FALHA
            if _linhas is not None and (_lendo or esperando):
                return _linhas, _quebradas  # vencido: os últimos valores enquanto outra lê (ou até a espera passar)
            if esperando:
                raise ParametrosIndisponiveis("Parâmetros: a leitura do banco falhou há menos de "
                                              f"{ESPERA_FALHA} s e não há leitura anterior.") from _erro
            if not _lendo:
                break
            if not _cond.wait(ESPERA_PRIMEIRA) and _lendo:
                raise ParametrosIndisponiveis("Parâmetros: a primeira leitura do banco não terminou a tempo.")
        _lendo = True
        geracao, epoca, anteriores, quebradas_antes = _geracao, _epoca, _linhas, _quebradas
    try:
        brutas = _ler_do_banco()
        linhas, quebradas = _montar_cache(brutas, anteriores, quebradas_antes)
    except BaseException as erro:  # qualquer saída solta a leitura (senão as outras threads esperariam para sempre)
        with _cond:
            if epoca == _epoca:
                _lendo = False
                _falhou_em, _erro = monotonico(), erro
            _cond.notify_all()
            if not isinstance(erro, Exception):
                raise
            if _linhas is None or epoca != _epoca:
                log.warning("Parâmetros: não foi possível ler o banco (%s) e não há leitura anterior.",
                            type(erro).__name__)
                raise ParametrosIndisponiveis("Parâmetros: não foi possível ler o banco e não há leitura "
                                              "anterior.") from erro
            log.warning("Parâmetros: não foi possível ler o banco (%s); valem os da última leitura (nova tentativa "
                        "em %s s).", type(erro).__name__, ESPERA_FALHA)
            return _linhas, _quebradas
    with _cond:
        if epoca == _epoca:
            _linhas, _quebradas, _lendo, _falhou_em, _erro = linhas, quebradas, False, None, None
            _lidas_em = agora if geracao == _geracao else None  # invalidada no meio: a próxima lê de novo
        _cond.notify_all()
    return linhas, quebradas


def aquecer() -> None:
    """Lê os parâmetros ao subir a API (a primeira rota não espera o banco por eles). Falhou: só o log de aviso (as
    rotas tentam de novo, depois da espera de 5 s)."""
    try:
        _do_cache()
    except Exception as erro:  # noqa: BLE001 - a API sobe mesmo assim
        log.warning("Parâmetros: não foi possível ler ao subir a API (%s); as rotas tentam de novo.",
                    type(erro).__name__)


def invalidar() -> None:
    """A próxima leitura vai ao banco, sem a espera de depois de uma falha (quem salvou chama depois do commit). A
    leitura que já estava em andamento não vale como nova."""
    global _lidas_em, _geracao, _falhou_em
    with _cond:
        _lidas_em = _falhou_em = None
        _geracao += 1


def limpar() -> None:
    """Esquece tudo, também a última leitura e a leitura em andamento (testes)."""
    global _linhas, _quebradas, _lidas_em, _lendo, _falhou_em, _erro, _geracao, _epoca
    with _cond:
        _linhas = _lidas_em = _falhou_em = _erro = None
        _quebradas, _lendo = frozenset(), False
        _geracao += 1
        _epoca += 1
        _cond.notify_all()


def efetivo(chave: str, linhas: dict[str, object]):
    """O valor da chave com as linhas dadas (as do cache ou as lidas na transação)."""
    return linhas[chave] if chave in linhas else padrao(chave)


def _do_cache_conferido(chave: str, linhas: dict[str, object], quebradas: frozenset[str]):
    if chave in quebradas:
        raise ParametroInvalido(f"Parâmetros: o preço {chave} no banco está fora do formato e não há valor bom lido "
                                "antes; corrija em Plataforma › Parâmetros.")
    return efetivo(chave, linhas)


def valor(chave: str):
    """O valor efetivo da chave (banco, pelo cache > variável > código)."""
    if chave not in CAMPOS:
        raise KeyError(chave)
    return _do_cache_conferido(chave, *_do_cache())


def grupo(nome: str) -> dict:
    linhas, quebradas = _do_cache()
    return {c: _do_cache_conferido(c, linhas, quebradas) for c in chaves_do_grupo(nome)}


def origem(chave: str, linhas: dict | None = None) -> str:
    """ "banco" (há linha), "ambiente" (a variável do padrão foi definida) ou "codigo"."""
    if chave in (linhas if linhas is not None else _do_cache()[0]):
        return "banco"
    return "ambiente" if _variavel_definida(chave) else "codigo"
