"""Dados da empresa (Configurações › Empresa) e logo da conta.

O nome é o de sempre (`contas.nome`): todo lugar que mostra o nome da empresa ({empresa} das pesquisas, assuntos,
rodapé dos e-mails, WhatsApp, remetente sem `remetente_nome`) lê a conta na hora, então o nome novo vale logo.
O logo fica em `imagens` (os bytes não entram em `contas`, lida a cada requisição).
"""
from sqlalchemy.orm import Session

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.modelos import Conta
from toqqi.modulos.imagens import servico as imagens

CAMPOS = ("nome", "razao_social", "documento", "telefone", "email_contato", "site", "cep", "logradouro", "numero",
          "complemento", "bairro", "cidade", "uf")


def _carimbar(s: Session, c: Conta) -> None:
    c.dados_atualizados_em = relogio.agora()
    s.flush()
    s.refresh(c, ["dados_atualizados_em"])  # relê do banco: a data sai em UTC, como no resto da API


def _json(s: Session, c: Conta) -> dict:
    return {**{campo: getattr(c, campo) or None for campo in CAMPOS},
            "logo_url": imagens.logo_da_conta(s, c.id), "atualizado_em": c.dados_atualizados_em}


def obter(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        return _json(s, s.get(Conta, ctx.conta_id))


def salvar(ctx: Contexto, dados) -> dict:
    """Grava todos os campos; a auditoria leva só os nomes dos campos que mudaram (sem os valores)."""
    with em_conta(ctx.conta_id) as s:
        c = s.get(Conta, ctx.conta_id, with_for_update=True)
        mudaram = [campo for campo in CAMPOS if (getattr(c, campo) or None) != getattr(dados, campo)]
        if mudaram:
            for campo in mudaram:
                setattr(c, campo, getattr(dados, campo))
            _carimbar(s, c)
            registrar(s, "dados_empresa_alterados", "info", {"campos": mudaram}, usuario_id=ctx.usuario_id)
        return _json(s, c)


def trocar_logo(ctx: Contexto, dados: bytes, tipo: str) -> dict:
    with em_conta(ctx.conta_id) as s:
        c = s.get(Conta, ctx.conta_id, with_for_update=True)  # uma troca por vez
        imagens.gravar(s, "logo_conta", dados, tipo, ctx.conta_id)
        _carimbar(s, c)
        registrar(s, "logo_alterado", "info", {"tipo": tipo, "tamanho": len(dados)}, usuario_id=ctx.usuario_id)
        return _json(s, c)


def remover_logo(ctx: Contexto) -> None:
    with em_conta(ctx.conta_id) as s:
        c = s.get(Conta, ctx.conta_id, with_for_update=True)
        if imagens.apagar_logo_conta(s, ctx.conta_id):
            _carimbar(s, c)
            registrar(s, "logo_removido", "info", usuario_id=ctx.usuario_id)
