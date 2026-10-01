"""Regras comuns dos relatórios: faixas de valor e de tempo como cliente, quadrantes da matriz NPS × valor,
mediana, formatos de CSV e o carregamento das empresas do filtro.

Faixas de valor (reais por mês): `ate_2k` < 2.000 ≤ `2k_10k` < 10.000 ≤ `10k_50k` < 50.000 ≤ `acima_50k`;
`sem_valor`. Tempo como cliente = meses completos de `cliente_desde` até hoje: `ate_3m` < 3 ≤ `3_6m` < 6 ≤
`6_12m` < 12 ≤ `mais_1a`; `sem_data`; data futura conta como `ate_3m`.
"""
import csv
import io
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from toqqi.core.filtros import FUSO
from toqqi.core.texto import sem_acento
from toqqi.modelos import Empresa, Grupo, Responsavel, Segmento
from toqqi.modulos.formularios.servico import _celula

FAIXAS_VALOR = (("ate_2k", "Menos de R$ 2 mil"), ("2k_10k", "R$ 2 mil a 10 mil"), ("10k_50k", "R$ 10 mil a 50 mil"),
                ("acima_50k", "R$ 50 mil ou mais"), ("sem_valor", "Sem valor"))
FAIXAS_TEMPO = (("ate_3m", "Até 3 meses"), ("3_6m", "3 a 6 meses"), ("6_12m", "6 a 12 meses"),
                ("mais_1a", "Mais de 1 ano"), ("sem_data", "Sem data de início"))
QUADRANTES = {"proteger": "Proteger já", "manter": "Manter de perto", "corrigir": "Corrigir", "crescer": "Pode crescer"}
ROTULOS_FAIXA_NPS = {"excelente": "Excelente", "muito_bom": "Muito bom", "pode_melhorar": "Pode melhorar",
                     "critico": "Crítico"}
ROTULOS_DIMENSAO = {"motorista": "Motorista", "rota": "Rota", "filial": "Filial", "transportadora": "Transportadora"}


def faixa_valor(valor: Decimal | None) -> str:
    if valor is None:
        return "sem_valor"
    if valor < 2000:
        return "ate_2k"
    if valor < 10000:
        return "2k_10k"
    if valor < 50000:
        return "10k_50k"
    return "acima_50k"


def meses_completos(desde: date, hoje: date) -> int:
    """Meses completos de `desde` até `hoje` (negativo se `desde` é futura), como o age() do PostgreSQL."""
    meses = (hoje.year - desde.year) * 12 + (hoje.month - desde.month)
    return meses - 1 if hoje.day < desde.day else meses


def faixa_tempo(desde: date | None, hoje: date) -> str:
    if desde is None:
        return "sem_data"
    meses = meses_completos(desde, hoje)
    if meses < 3:
        return "ate_3m"
    if meses < 6:
        return "3_6m"
    if meses < 12:
        return "6_12m"
    return "mais_1a"


def mediana(valores: list[Decimal]) -> Decimal | None:
    """Mediana (média dos dois do meio quando a quantidade é par)."""
    return Decimal(statistics.median(valores)) if valores else None


def quadrante(valor: Decimal, nps: int, mediana_valor: Decimal) -> str:
    alto = valor >= mediana_valor
    if nps < 0:
        return "proteger" if alto else "corrigir"
    return "manter" if alto else "crescer"


def chave_nome(nome: str | None) -> str:
    """Ordem alfabética sem diferenciar maiúsculas nem acentos."""
    return sem_acento(str(nome or "")).casefold()


# ---- empresas do filtro ---------------------------------------------------------

@dataclass
class FiltroEmpresas:
    grupo_id: int | None = None
    so_ativos: bool = True
    segmento_id: int | None = None      # 0 = sem segmento
    responsavel_id: int | None = None   # 0 = sem responsável
    faixa_valor: str | None = None
    tempo_cliente: str | None = None


@dataclass
class EmpresaRel:
    id: int
    nome: str
    ativa: bool
    grupo: dict | None
    segmento: dict | None
    responsavel: dict | None
    foto_url: str | None
    valor_mensal: Decimal | None
    cliente_desde: date | None
    faixa_valor: str
    faixa_tempo: str
    extra: dict = field(default_factory=dict)

    @property
    def responsavel_id(self) -> int | None:
        return self.responsavel["id"] if self.responsavel else None


def _ref(i, nome) -> dict | None:
    return {"id": i, "nome": nome} if i is not None else None


def carregar_empresas(s: Session, conta_id: int, f: FiltroEmpresas, hoje: date) -> list[EmpresaRel]:
    """Empresas do filtro (com grupo, segmento e responsável), já com as faixas de valor e de tempo."""
    g, sg, rp = aliased(Grupo), aliased(Segmento), aliased(Responsavel)
    conds = [Empresa.conta_id == conta_id]
    if f.so_ativos:
        conds.append(Empresa.ativa.is_(True))
    if f.grupo_id is not None:
        conds.append(Empresa.grupo_id == f.grupo_id)
    for coluna, valor in ((Empresa.segmento_id, f.segmento_id), (Empresa.responsavel_id, f.responsavel_id)):
        if valor is not None:
            conds.append(coluna.is_(None) if valor == 0 else coluna == valor)
    linhas = s.execute(
        select(Empresa.id, Empresa.nome, Empresa.ativa, Empresa.grupo_id, g.nome.label("grupo_nome"),
               Empresa.segmento_id, sg.nome.label("segmento_nome"), Empresa.responsavel_id,
               rp.nome.label("responsavel_nome"), rp.foto_url, Empresa.valor_mensal, Empresa.cliente_desde)
        .outerjoin(g, g.id == Empresa.grupo_id).outerjoin(sg, sg.id == Empresa.segmento_id)
        .outerjoin(rp, rp.id == Empresa.responsavel_id).where(*conds)).all()
    empresas = []
    for x in linhas:
        e = EmpresaRel(x.id, x.nome, x.ativa, _ref(x.grupo_id, x.grupo_nome), _ref(x.segmento_id, x.segmento_nome),
                       _ref(x.responsavel_id, x.responsavel_nome), x.foto_url, x.valor_mensal, x.cliente_desde,
                       faixa_valor(x.valor_mensal), faixa_tempo(x.cliente_desde, hoje))
        if (f.faixa_valor is None or e.faixa_valor == f.faixa_valor) and \
                (f.tempo_cliente is None or e.faixa_tempo == f.tempo_cliente):
            empresas.append(e)
    return empresas


# ---- CSV ------------------------------------------------------------------------

class Numero(str):
    """Número já formatado para o CSV (não passa pela proteção contra fórmula: "-11" é número, não fórmula)."""


def gerar_csv(cabecalho: list[str], linhas) -> str:
    """`;`, UTF-8 com BOM, quebra de linha CRLF; textos protegidos contra fórmula (números saem como estão)."""
    buf = io.StringIO()
    buf.write("\ufeff")
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(cabecalho)
    for linha in linhas:
        w.writerow([v if isinstance(v, Numero) else _celula(v) if isinstance(v, str) else ("" if v is None else v)
                    for v in linha])
    return buf.getvalue()


def num(v, casas: int = 2) -> str:
    """Número no formato brasileiro do Excel (vírgula decimal, sem separador de milhar); vazio para None."""
    if v is None:
        return ""
    if isinstance(v, int):
        return Numero(v)
    return Numero(f"{Decimal(v):.{casas}f}".replace(".", ","))


def data_br(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        v = v.astimezone(FUSO)
    return v.strftime("%d/%m/%Y")


def sim_nao(v: bool) -> str:
    return "Sim" if v else "Não"
