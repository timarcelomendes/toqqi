"""Regras da IA por resposta sem banco nem sessão (usadas também no formato da conta em /eu e no login)."""
from toqqi.core import ia
from toqqi.modelos import Conta, Resposta
from toqqi.modulos.assinatura.regras import liberada

ORIGENS = ("pesquisa", "manual")
MIN_LETRAS = 3
TETO_PLANO = {"essencial": 1000, "profissional": 5000, "empresa": 20000}
TETO_CORTESIA = 5000
TETO_TESTE = 1000


def teto_mensal(conta: Conta) -> int:
    """Teto de segurança de análises por mês: Essencial 1.000, Profissional 5.000, Empresa 20.000, Cortesia
    5.000, conta em teste 1.000. (A análise de cada resposta não gasta a cota de IA do plano.)"""
    if conta.situacao == "cortesia":
        return TETO_CORTESIA
    if conta.situacao in ("teste", "teste_expirado"):
        return TETO_TESTE
    return TETO_PLANO.get(conta.plano, TETO_TESTE)


def ia_ativa(conta: Conta) -> bool:
    """IA disponível na plataforma + chave da conta ligada + conta liberada (assinatura em dia)."""
    return ia.disponivel() and bool(conta.ia_analise_respostas) and liberada(conta)


def texto_qualifica(texto: str | None) -> bool:
    return ia.letras(texto) >= MIN_LETRAS


def passa_pela_ia(conta: Conta, r: Resposta) -> bool:
    """Origem pesquisa ou manual, texto do cliente com 3+ letras, conta com a IA ativa."""
    return r.origem in ORIGENS and texto_qualifica(r.comentario_cliente) and ia_ativa(conta)
