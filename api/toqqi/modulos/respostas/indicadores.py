"""NPS, CSAT e percentuais. Arredondamento "meio para cima, longe do zero" (como o ARRED do Excel) sobre o
valor exato: 12,5 → 13 e −12,5 → −13 (Decimal com ROUND_HALF_UP)."""
from decimal import ROUND_HALF_UP, Decimal

FAIXAS = ((75, "excelente"), (50, "muito_bom"), (0, "pode_melhorar"))
ROTULOS_GRUPO = {"detrator": "Detrator", "neutro": "Neutro", "promotor": "Promotor",
                 "insatisfeito": "Insatisfeito", "satisfeito": "Satisfeito"}
ROTULOS_TIPO = {"nps": "NPS", "csat": "CSAT"}


def arredondar(valor: Decimal, casas: int = 0) -> Decimal:
    return valor.quantize(Decimal(1).scaleb(-casas), ROUND_HALF_UP)


def nps(promotores: int, detratores: int, total: int) -> int | None:
    """% promotores − % detratores, inteiro; None sem respostas."""
    if not total:
        return None
    return int(arredondar(Decimal(promotores - detratores) * 100 / Decimal(total)))


def faixa(valor: int | None) -> str | None:
    """≥ 75 excelente, ≥ 50 muito_bom, ≥ 0 pode_melhorar, < 0 critico."""
    if valor is None:
        return None
    return next((nome for minimo, nome in FAIXAS if valor >= minimo), "critico")


def percentual(parte: int, total: int, casas: int = 0) -> int | float | None:
    """parte/total em %, com `casas` decimais (0 → inteiro); None sem total."""
    if not total:
        return None
    v = arredondar(Decimal(parte) * 100 / Decimal(total), casas)
    return int(v) if casas == 0 else float(v)


def media(soma: int | Decimal, total: int, casas: int = 2) -> float | None:
    if not total:
        return None
    return float(arredondar(Decimal(soma) / Decimal(total), casas))


def bloco_nps(promotores: int, neutros: int, detratores: int) -> dict:
    total = promotores + neutros + detratores
    valor = nps(promotores, detratores, total)
    return {"valor": valor, "faixa": faixa(valor), "promotores": promotores, "neutros": neutros,
            "detratores": detratores, "total": total}
