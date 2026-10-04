"""Regras da IA por resposta sem banco nem sessão (usadas também no formato da conta em /eu e no login)."""
from toqqi.core import ia, parametros
from toqqi.modelos import Conta, Resposta
from toqqi.modulos.assinatura.regras import liberada

ORIGENS = ("pesquisa", "manual")
MIN_LETRAS = 3
def chave_do_teto(conta: Conta) -> str:
    """O parâmetro do teto da conta: cortesia → `ia.teto.cortesia`; teste e teste expirado → `ia.teto.teste`; demais
    → pelo plano (desconhecido → o do teste)."""
    if conta.situacao == "cortesia":
        return "ia.teto.cortesia"
    if conta.situacao in ("teste", "teste_expirado") or conta.plano not in parametros.PLANOS:
        return "ia.teto.teste"
    return f"ia.teto.{conta.plano}"


def teto_mensal(conta: Conta) -> int:
    """Teto de segurança de análises por mês (etapa 5g: parâmetros `ia.teto.*`; padrões Essencial 1.000,
    Profissional 5.000, Empresa 20.000, Cortesia 5.000, conta em teste 1.000). Mudou: vale na próxima análise (abaixo
    do já usado no mês, os temas seguem por palavras-chave até o mês virar). A análise de cada resposta não gasta a
    cota de IA do plano."""
    return parametros.valor(chave_do_teto(conta))


def ia_ativa(conta: Conta) -> bool:
    """IA disponível na plataforma + chave da conta ligada + conta liberada (assinatura em dia)."""
    return ia.disponivel() and bool(conta.ia_analise_respostas) and liberada(conta)


def texto_qualifica(texto: str | None) -> bool:
    return ia.letras(texto) >= MIN_LETRAS


def passa_pela_ia(conta: Conta, r: Resposta) -> bool:
    """Origem pesquisa ou manual, texto do cliente com 3+ letras, conta com a IA ativa."""
    return r.origem in ORIGENS and texto_qualifica(r.comentario_cliente) and ia_ativa(conta)
