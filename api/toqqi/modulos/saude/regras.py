"""Etapa 5i, saúde da conta (docs/api-etapa-5i.md §3.1): a nota de 0 a 100 de cada empresa ativa, com regras
transparentes e os "porquês". Este arquivo é puro (sem banco): recebe os números já contados (`Sinais`, de
`calculo.py`) e devolve a nota, a faixa e os textos. Sem IA e sem tarefa agendada: calculada na hora."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from toqqi.modulos.respostas.indicadores import arredondar, nps

JANELA = 180  # dias: a janela atual é [D − 179, D]; a anterior, os 180 dias antes dela
SAUDAVEL, ATENCAO = 70, 45
RENOVACAO_DIAS = 60
FAIXAS = ("saudavel", "atencao", "risco", "sem_dados")
ROTULOS_FAIXA = {"saudavel": "Saudável", "atencao": "Atenção", "risco": "Risco", "sem_dados": "Sem dados"}
MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


@dataclass
class Sinais:
    """Tudo o que a nota de uma empresa usa (contado por `calculo.py`)."""
    nps_j: tuple[int, int, int] = (0, 0, 0)  # (promotores, neutros, detratores) na janela atual
    nps_anterior: tuple[int, int, int] = (0, 0, 0)
    convidados: int = 0  # contatos ativos com convite que saiu na janela
    convidados_responderam: int = 0  # desses, os que responderam NPS na janela
    tem_decisor: bool = False
    decisor_j: tuple[str, int, date] | None = None  # (grupo, nota, dia) da NPS mais recente de um decisor na janela
    decisor_ultima: date | None = None  # a última NPS de um decisor, em qualquer data
    decisor_convidado: bool = False
    pendente_desde: date | None = None  # o convite mais antigo que saiu depois da última resposta da empresa
    atrasados: int = 0
    abertos_detrator: int = 0  # abertos de detrator ou insatisfeito, não atrasados
    respondeu_alguma_vez: bool = False
    primeiro_convite: date | None = None


def _pts(v: Decimal | float | int) -> int:
    return int(arredondar(Decimal(str(v))))


def _nps(t: tuple[int, int, int]) -> int | None:
    p, n, d = t
    return nps(p, d, p + n + d)


def _num(n: int) -> str:
    """−67 com o sinal de menos tipográfico."""
    return f"−{-n}" if n < 0 else str(n)


def _data(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _meses_desde(d: date, hoje: date) -> int:
    m = (hoje.year - d.year) * 12 + hoje.month - d.month
    return m - 1 if hoje.day < d.day else m


def faixa(nota: int | None) -> str:
    if nota is None:
        return "sem_dados"
    return "saudavel" if nota >= SAUDAVEL else "atencao" if nota >= ATENCAO else "risco"


def calcular(s: Sinais, hoje: date, renovacao_em: date | None = None) -> dict:
    """{faixa, nota, criterios, porques, renovacao, destaque}."""
    renovacao = None
    if renovacao_em and 0 <= (renovacao_em - hoje).days <= RENOVACAO_DIAS:
        renovacao = {"em": renovacao_em, "dias": (renovacao_em - hoje).days}
    sem_dados = not s.respondeu_alguma_vez and (s.primeiro_convite is None or (hoje - s.primeiro_convite).days <= 30)
    if sem_dados:
        return {"faixa": "sem_dados", "nota": None, "criterios": [], "porques": [], "renovacao": renovacao,
                "destaque": False}

    criterios = []

    def criterio(chave, rotulo, pontos, maximo, texto, tom):
        criterios.append({"criterio": chave, "rotulo": rotulo, "pontos": pontos, "maximo": maximo,
                          "texto": texto, "tom": tom})

    # Satisfação (40)
    n_j = sum(s.nps_j)
    nps_j = _nps(s.nps_j)
    if n_j:
        txt = f"NPS {_num(nps_j)} nos últimos 6 meses ({n_j} {'resposta' if n_j == 1 else 'respostas'})"
        criterio("satisfacao", "Satisfação", _pts(Decimal(40) * (nps_j + 100) / 200), 40, txt,
                 "positivo" if nps_j >= 50 else "neutro" if nps_j >= 0 else "negativo")
    else:
        criterio("satisfacao", "Satisfação", 20, 40, "Sem respostas de NPS nos últimos 6 meses", "neutro")

    # Tendência (10)
    nps_a = _nps(s.nps_anterior)
    if n_j >= 2 and sum(s.nps_anterior) >= 2:
        delta = nps_j - nps_a
        if delta >= 10:
            criterio("tendencia", "Tendência", 10, 10, f"NPS subiu {delta} pontos em relação aos 6 meses anteriores", "positivo")
        elif delta <= -10:
            criterio("tendencia", "Tendência", 0, 10, f"NPS caiu {-delta} pontos em relação aos 6 meses anteriores", "negativo")
        else:
            criterio("tendencia", "Tendência", 6, 10, "NPS estável em relação aos 6 meses anteriores", "neutro")
    else:
        criterio("tendencia", "Tendência", 6, 10, None, "neutro")

    # Cobertura (15)
    if s.convidados:
        pct = s.convidados_responderam / s.convidados
        txt = f"{s.convidados_responderam} de {s.convidados} contatos convidados responderam"
        criterio("cobertura", "Cobertura", _pts(Decimal(15) * s.convidados_responderam / s.convidados), 15, txt,
                 "positivo" if pct >= 0.67 else "neutro" if pct >= 0.34 else "negativo")
    else:
        criterio("cobertura", "Cobertura", 8, 15, "Nenhum contato convidado nos últimos 6 meses", "neutro")

    # Decisor (15)
    if not s.tem_decisor:
        criterio("decisor", "Decisor", 7, 15, "Nenhum contato com o perfil Decisor", "neutro")
    elif s.decisor_j:
        grupo, nota, dia = s.decisor_j
        pontos, tom = {"promotor": (15, "positivo"), "neutro": (9, "neutro")}.get(grupo, (0, "negativo"))
        criterio("decisor", "Decisor", pontos, 15, f"Decisor {grupo} (nota {nota} em {_data(dia)})", tom)
    else:
        if s.decisor_ultima:
            meses = _meses_desde(s.decisor_ultima, hoje)
            txt = f"Decisor não responde há {meses} {'mês' if meses == 1 else 'meses'}"
        elif s.decisor_convidado:
            txt = "Decisor nunca respondeu"
        else:
            txt = "Decisor ainda não foi convidado"
        criterio("decisor", "Decisor", 3, 15, txt, "negativo")

    # Silêncio (10)
    if s.pendente_desde is None:
        criterio("silencio", "Silêncio", 10, 10, None, "neutro")
    else:
        dias = (hoje - s.pendente_desde).days
        if dias <= 30:
            criterio("silencio", "Silêncio", 10, 10, "Convite recente aguardando resposta", "neutro")
        else:
            pontos = 6 if dias <= 90 else 3 if dias <= 180 else 0
            quando = f"há {dias} dias" if dias <= 60 else f"há {_meses_desde(s.pendente_desde, hoje)} meses"
            criterio("silencio", "Silêncio", pontos, 10, f"Convidada {quando} e sem resposta desde então", "negativo")

    # Planos (10)
    pontos = max(0, 10 - 5 * s.atrasados - 2 * s.abertos_detrator)
    if s.atrasados:
        txt, tom = f"{s.atrasados} {'plano de ação atrasado' if s.atrasados == 1 else 'planos de ação atrasados'}", "negativo"
    elif s.abertos_detrator:
        n = s.abertos_detrator
        txt, tom = f"{n} {'plano de ação aberto' if n == 1 else 'planos de ação abertos'} para detrator", "neutro"
    else:
        txt, tom = None, "neutro"
    criterio("planos", "Planos de ação", pontos, 10, txt, tom)

    nota = sum(c["pontos"] for c in criterios)
    fx = faixa(nota)
    negativos = sorted((c for c in criterios if c["tom"] == "negativo" and c["texto"] and c["maximo"] - c["pontos"] >= 3),
                       key=lambda c: c["pontos"] - c["maximo"])[:3]
    positivos = [c for c in criterios if c["tom"] == "positivo" and c["texto"]][:2]
    porques = [{"texto": c["texto"], "tom": c["tom"]} for c in negativos + positivos]
    return {"faixa": fx, "nota": nota, "criterios": criterios, "porques": porques, "renovacao": renovacao,
            "destaque": renovacao is not None and fx in ("atencao", "risco")}
