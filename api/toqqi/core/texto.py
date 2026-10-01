"""Normalização e interpretação de textos vindos de formulários e planilhas (padrões brasileiros)."""
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_NAO_DIGITO = re.compile(r"\D+")


def sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def normalizar_cabecalho(t: str) -> str:
    """ " E-mail do Cliente " → "e_mail_do_cliente"."""
    t = sem_acento(str(t).strip().lower())
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def so_digitos(v: str) -> str:
    return _NAO_DIGITO.sub("", v or "")


def normalizar_telefone(v: str) -> str:
    """Só dígitos, com DDI 55. Aceita 10–13 dígitos (10/11 ganham o 55). Levanta ValueError."""
    d = so_digitos(v)
    if len(d) in (10, 11):
        if d[0] == "0":
            raise ValueError("Informe o telefone com DDD, sem o zero da operadora.")
        d = "55" + d
    if not 12 <= len(d) <= 13:
        raise ValueError("Informe o telefone com DDD (10 a 13 dígitos).")
    return d


# Celular brasileiro sem o nono dígito (como o WhatsApp às vezes informa): 55 + DDD + 8 dígitos de 6 a 9.
RE_CELULAR_SEM_NOVE = r"^(55[0-9]{2})([6-9][0-9]{7})$"


def telefone_canonico(t: str) -> str:
    """Só dígitos; celular brasileiro de 12 dígitos ganha o nono dígito ("551187654321" → "5511987654321")."""
    return re.sub(RE_CELULAR_SEM_NOVE, r"\g<1>9\g<2>", so_digitos(t))


def _cpf_valido(d: str) -> bool:
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        dv = (soma * 10) % 11 % 10
        if dv != int(d[n]):
            return False
    return True


def _cnpj_valido(d: str) -> bool:
    if len(d) != 14 or d == d[0] * 14:
        return False
    for n in (12, 13):
        pesos = list(range(n - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(int(d[i]) * pesos[i] for i in range(n))
        dv = 11 - soma % 11
        dv = 0 if dv >= 10 else dv
        if dv != int(d[n]):
            return False
    return True


def normalizar_documento(v: str) -> str | None:
    """CPF ou CNPJ só com dígitos; vazio → None. Levanta ValueError se os dígitos verificadores não baterem."""
    d = so_digitos(v)
    if not d:
        return None
    if len(d) == 11 and _cpf_valido(d):
        return d
    if len(d) == 14 and _cnpj_valido(d):
        return d
    raise ValueError("CNPJ ou CPF inválido. Confira os números.")


def interpretar_valor(v) -> Decimal | None:
    """ "R$ 1.250,50" / "1250.5" / 1250.5 → Decimal("1250.50"). Vazio → None. Levanta ValueError."""
    if v is None:
        return None
    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
        valor = Decimal(str(v))
    else:
        t = str(v).strip().replace("R$", "").replace(" ", "").replace(" ", "")
        if not t:
            return None
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        elif t.count(".") > 1:
            t = t.replace(".", "")
        elif re.fullmatch(r"-?\d{1,3}\.\d{3}", t):  # "1.250" → mil duzentos e cinquenta
            t = t.replace(".", "")
        try:
            valor = Decimal(t)
        except InvalidOperation:
            raise ValueError("Valor inválido.")
    if not valor.is_finite() or valor < 0 or valor >= Decimal("10000000000"):
        raise ValueError("Valor inválido.")
    return valor.quantize(Decimal("0.01"))


def interpretar_data(v) -> date | None:
    """dd/mm/aaaa ou aaaa-mm-dd (ou data/datetime da planilha). Vazio → None. Levanta ValueError."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    t = str(v).strip()
    if not t:
        return None
    t = t.split(" ")[0].split("T")[0]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(t, fmt).date()
            if 1900 <= d.year <= 2100:
                return d
        except ValueError:
            pass
    raise ValueError("Data inválida (use dd/mm/aaaa ou aaaa-mm-dd).")


_VERDADEIRO = {"sim", "s", "true", "verdadeiro", "1", "ativo", "ativa", "x", "yes", "y"}
_FALSO = {"nao", "n", "false", "falso", "0", "inativo", "inativa", "no"}


def interpretar_booleano(v, padrao: bool | None = True) -> bool | None:
    if v is None:
        return padrao
    if isinstance(v, bool):
        return v
    t = sem_acento(str(v).strip().lower())
    if not t:
        return padrao
    if t in _VERDADEIRO:
        return True
    if t in _FALSO:
        return False
    raise ValueError("Use sim ou não.")
