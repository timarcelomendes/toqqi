"""Ponto único "resposta registrada" (e, desde docs/api-editar-resposta.md, "resposta editada pelo cliente").

Toda resposta nova gravada por `gravar_resposta` passa por `ao_registrar_resposta`, dentro da mesma transação
que a gravou. Os ganchos (agradecimento e fila de envios, webhooks, ação automática + alerta) conferem
`resposta.origem`:
- `pesquisa` (páginas públicas): todos os efeitos;
- `manual` (registrada por alguém da conta): tudo, menos o agradecimento por e-mail;
- `importacao` (histórico): nenhum efeito. A importação grava em lote e não chama os ganchos; eles ignoram
  essa origem de qualquer forma.
"""
from collections.abc import Callable

from sqlalchemy.orm import Session

from toqqi.modelos import Resposta

Gancho = Callable[[Session, Resposta], None]
GANCHOS: list[Gancho] = []


def ao_registrar_resposta(sessao: Session, resposta: Resposta) -> None:
    for gancho in list(GANCHOS):
        gancho(sessao, resposta)


# ---- o cliente mudou a resposta (docs/api-editar-resposta.md) ---------------------------------------------------

GanchoEdicao = Callable[[Session, Resposta, dict], None]
GANCHOS_EDICAO: list[GanchoEdicao] = []


def ao_editar_resposta(sessao: Session, resposta: Resposta, antes: dict) -> None:
    """Chamado por `registro.editar_resposta`, na mesma transação, com os valores de `antes` (nota, grupo, tipo_nota,
    comentario_cliente). Os ganchos: IA (analisa de novo), plano de ação (marca a nota nova ou cria o plano que a nota
    nova pede), webhook `resposta.atualizada` e depoimento (volta a pendente quando o comentário mudou). Nenhum
    agradecimento sai de novo."""
    for gancho in list(GANCHOS_EDICAO):
        gancho(sessao, resposta, antes)
