"""Planos (chave e nome, na ordem da tela). Preço e limite de contatos são parâmetros da plataforma (etapa 5g,
`core.parametros`: `planos.{plano}.preco` e `planos.{plano}.contatos`): `preco` e `planos_json` leem do cache (até 30 s
em outro processo); o limite de contatos de uma conta é perguntado ao banco (`select limite_contatos(...)`, a mesma
função do gatilho em contatos, que lê a tabela `parametros` na hora)."""
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from toqqi.core import parametros
from toqqi.core.errors import AppError
from toqqi.modelos import Conta, Contato

PLANOS = (("essencial", "Essencial"), ("profissional", "Profissional"), ("empresa", "Empresa"))
NOMES = {**dict(PLANOS), "personalizado": "Personalizado"}  # etapa 5k: o Personalizado não é um plano padrão
TRAVA_CONTATOS = 740221  # mesma trava consultiva do gatilho contatos_limite_plano (por conta)


def preco(plano: str) -> Decimal:
    """O preço atual do plano (vale para assinaturas novas e trocas de plano)."""
    return parametros.valor(f"planos.{plano}.preco")


def contatos_do_plano(plano: str) -> int | None:
    """O limite de contatos ativos do plano pelo cache (None = sem limite); para uma conta, `limite_da_conta`."""
    return parametros.valor(f"planos.{plano}.contatos")


def planos_json() -> list[dict]:
    """[{chave, nome, preco, contatos, ia_cota, ia_teto, whatsapp}] com os valores atuais (etapa 5k: a cota do ToqqiAI,
    o teto de comentários lidos pela IA e a franquia do WhatsApp, null = sem franquia, para a tela comparar os planos)."""
    v = parametros.valor
    return [{"chave": c, "nome": n, "preco": preco(c), "contatos": contatos_do_plano(c), "ia_cota": v(f"ia.cota.{c}"),
             "ia_teto": v(f"ia.teto.{c}"), "whatsapp": v(f"whatsapp.franquia.{c}")} for c, n in PLANOS]


def limite_contatos(s: Session, plano: str, situacao: str) -> int | None:
    """Contatos ativos permitidos (None = ilimitado; cortesia nunca tem limite), pela regra do gatilho do banco."""
    return s.scalar(select(func.limite_contatos(plano, situacao)))


def pode_ocultar_mencao(plano: str | None, situacao: str | None) -> bool:
    """Etapa 5i: só o plano Empresa (pagando ou com a fatura atrasada) e a cortesia podem tirar "Pesquisa feita com
    Toqqi"; teste, Essencial e Profissional sempre mostram (e voltam a mostrar ao descer de plano)."""
    return situacao == "cortesia" or (plano == "empresa" and situacao in ("ativa", "atrasada"))


def url_mencao(campanha: str) -> str:
    """Link da menção ao Toqqi: a raiz do site com a origem marcada (nunca ids de conta, contato ou convite)."""
    from toqqi.core.config import config
    return f"{config().FRONTEND_URL.rstrip('/')}/?utm_source=pesquisa&utm_medium=rodape&utm_campaign={campanha}"


_UTM = ("utm_source", "utm_medium", "utm_campaign")
_VALOR_UTM = re.compile(r"^[a-z0-9._-]{1,60}$")


def limpar_origem(bruta) -> dict | None:
    """Etapa 5i: só as 3 chaves utm; minúsculas, espaços e "+" viram "-"; descarta o que não casar com
    `^[a-z0-9._-]{1,60}$`, tiver "@" ou 6+ dígitos seguidos (e-mail ou telefone). Nada válido = None.
    (Mesma regra de `web/src/site/origem.ts`.)"""
    if not isinstance(bruta, dict):
        return None
    limpa = {}
    for chave in _UTM:
        valor = bruta.get(chave)
        if not isinstance(valor, str):
            continue
        valor = re.sub(r"[\s+]+", "-", valor.strip().lower())
        if "@" in valor or re.search(r"\d{6,}", valor) or not _VALOR_UTM.match(valor):
            continue
        limpa[chave] = valor
    return limpa or None


def numero(n: int) -> str:
    """1500 → "1.500"."""
    return f"{n:,}".replace(",", ".")


def erro_limite(limite: int) -> AppError:
    """402 da etapa 2 (mesmo texto do gatilho do banco); `campos.limite` leva o limite para a tela oferecer "Ver
    planos"."""
    return AppError(402, "limite_do_plano", f"Seu plano permite até {limite} contatos ativos.",
                    {"limite": str(limite)})


def limite_da_conta(s: Session, conta_id: int) -> int | None:
    """O limite de contatos ativos da conta (a regra do gatilho do banco; no Personalizado, o contratado)."""
    plano, situacao, contratado = s.execute(select(Conta.plano, Conta.situacao, Conta.contatos_personalizado)
                                            .where(Conta.id == conta_id)).one()
    if plano == "personalizado" and situacao != "cortesia":
        return contratado
    return limite_contatos(s, plano, situacao)


def contatos_ativos(s: Session) -> int:
    return s.scalar(select(func.count()).select_from(Contato).where(Contato.ativo.is_(True)))


def travar_contatos(s: Session, conta_id: int) -> None:
    """Espera as inclusões de contatos em andamento na conta (e segura as novas) até o fim da transação: a contagem
    feita depois não corre com o gatilho do limite."""
    s.execute(text("select pg_advisory_xact_lock(:t, :c)"), {"t": TRAVA_CONTATOS, "c": int(conta_id)})


# ---- etapa 5k: ciclo, forma de pagamento e Personalizado (docs/api-etapa-5k.md §2 e §3) ------------------------

CICLOS = ("mensal", "anual")
FORMAS = ("pix", "qualquer")  # qualquer = a fatura deixa escolher Pix, boleto ou cartão
PACOTES_IA = (100, 500, 2000, 5000)  # perguntas ao ToqqiAI por mês no Personalizado (100 incluídas)
CONTATOS_MIN, CONTATOS_MAX, PASSO_CONTATOS = 100, 100_000, 100
FAIXAS = ((15, "ate_1500"), (100, "ate_10000"), (None, "acima"))  # até quantas centenas vale o preço da faixa
CENTAVOS = Decimal("0.01")


@dataclass(frozen=True)
class Contrato:
    """O que a conta assina: plano, ciclo, forma e, no Personalizado, contatos e perguntas ao ToqqiAI por mês."""
    plano: str
    ciclo: str = "mensal"
    forma: str = "qualquer"
    contatos: int | None = None
    cota_ia: int | None = None


def descontos() -> dict:
    """{pix, anual} em % (parâmetros `planos.desconto.*`)."""
    return {"pix": parametros.valor("planos.desconto.pix"), "anual": parametros.valor("planos.desconto.anual")}


def descontos_json() -> dict:
    return descontos()


def _p(chave: str) -> Decimal:
    return parametros.valor(f"planos.personalizado.{chave}")


def personalizado_json() -> dict:
    """A tabela do Personalizado para as telas (a calculadora repete a conta de `preco_personalizado`)."""
    return {"base": _p("base"),
            "faixas": [{"ate": None if ate is None else ate * 100, "preco": _p(chave)} for ate, chave in FAIXAS],
            "ia": [{"cota": c, "preco": Decimal("0.00") if c == PACOTES_IA[0] else _p(f"ia_{c}")}
                   for c in PACOTES_IA],
            "contatos_min": CONTATOS_MIN, "contatos_max": CONTATOS_MAX, "passo": PASSO_CONTATOS}


def contatos_validos(n) -> bool:
    return (isinstance(n, int) and not isinstance(n, bool) and CONTATOS_MIN <= n <= CONTATOS_MAX
            and n % PASSO_CONTATOS == 0)


def preco_personalizado(contatos: int, cota_ia: int) -> Decimal:
    """Por mês: base + cada 100 contatos pelo preço da faixa em que cai + o pacote do ToqqiAI."""
    if not contatos_validos(contatos) or cota_ia not in PACOTES_IA:
        raise ValueError("Personalizado fora da tabela.")
    total = _p("base")
    centenas, antes = contatos // PASSO_CONTATOS, 0
    for ate, chave in FAIXAS:
        nesta = centenas - antes if ate is None else max(0, min(centenas, ate) - antes)
        total += nesta * _p(chave)
        if ate is None or centenas <= ate:
            break
        antes = ate
    if cota_ia != PACOTES_IA[0]:
        total += _p(f"ia_{cota_ia}")
    return total.quantize(CENTAVOS)


def preco_mensal(c: Contrato) -> Decimal:
    """O preço cheio por mês do contrato (sem desconto)."""
    return preco_personalizado(c.contatos, c.cota_ia) if c.plano == "personalizado" else preco(c.plano)


def valor_contrato(c: Contrato) -> Decimal:
    """O valor de cada fatura: mensal = preço; mensal com Pix = preço − pix%; anual = 12 × preço − anual% (o anual não
    soma o desconto do Pix). Centavos arredondados com meio para cima."""
    mensal = preco_mensal(c)
    d = descontos()
    if c.ciclo == "anual":
        bruto = mensal * 12 * (100 - d["anual"]) / 100
    elif c.forma == "pix":
        bruto = mensal * (100 - d["pix"]) / 100
    else:
        bruto = mensal
    return Decimal(bruto).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def nome_do_contrato(c: Contrato) -> str:
    """"Profissional", "Personalizado (2.000 contatos, 500 perguntas)"."""
    if c.plano == "personalizado":
        return f"Personalizado ({numero(c.contatos)} contatos, {numero(c.cota_ia)} perguntas)"
    return NOMES[c.plano]


def descricao(c: Contrato) -> str:
    """A descrição da assinatura no Asaas (também usada para reconhecer e adotar uma assinatura de lá)."""
    sufixo = " · anual" if c.ciclo == "anual" else " · Pix" if c.forma == "pix" else ""
    return f"Toqqi – plano {nome_do_contrato(c)}{sufixo}"


_RE_DESCRICAO = re.compile(r"Toqqi – plano (Essencial|Profissional|Empresa|Personalizado)"
                           r"(?: \(([0-9.]{1,7}) contatos, ([0-9.]{1,5}) perguntas\))?( · anual| · Pix)?")
_PELO_NOME = {n: c for c, n in NOMES.items()}


def contrato_da_descricao(texto) -> Contrato | None:
    """O contrato que a descrição do Asaas descreve (None se não é uma descrição do Toqqi)."""
    m = _RE_DESCRICAO.fullmatch(texto) if isinstance(texto, str) else None
    if m is None:
        return None
    plano = _PELO_NOME[m.group(1)]
    ciclo = "anual" if m.group(4) == " · anual" else "mensal"
    forma = "pix" if m.group(4) == " · Pix" else "qualquer"
    if plano == "personalizado":
        if m.group(2) is None:
            return None
        contatos, cota = int(m.group(2).replace(".", "")), int(m.group(3).replace(".", ""))
        if not contatos_validos(contatos) or cota not in PACOTES_IA:
            return None
        return Contrato(plano, ciclo, forma, contatos, cota)
    if m.group(2) is not None:
        return None
    return Contrato(plano, ciclo, forma)


def contrato_conferido(c: Contrato) -> Contrato:
    """Confere a combinação (ValueError(campo, mensagem)): Personalizado com contatos e cota da tabela; padrão sem eles;
    anual sempre com forma `qualquer`."""
    if c.plano not in NOMES:
        raise ValueError("plano", "Plano desconhecido.")
    if c.ciclo not in CICLOS or c.forma not in FORMAS:
        raise ValueError("ciclo" if c.ciclo not in CICLOS else "forma", "Ciclo ou forma de pagamento desconhecidos.")
    if c.ciclo == "anual" and c.forma != "qualquer":
        raise ValueError("forma", "No anual, a fatura aceita Pix, boleto ou cartão.")
    if c.plano == "personalizado":
        if not contatos_validos(c.contatos):
            raise ValueError("contatos", f"Escolha de {numero(CONTATOS_MIN)} a {numero(CONTATOS_MAX)} contatos, de 100 "
                                         "em 100.")
        if c.cota_ia not in PACOTES_IA:
            raise ValueError("cota_ia", "Escolha 100, 500, 2.000 ou 5.000 perguntas ao ToqqiAI.")
    elif c.contatos is not None or c.cota_ia is not None:
        raise ValueError("plano", "Contatos e perguntas só se escolhem no Personalizado.")
    return c
