"""Registro de eventos de auditoria da conta."""
from sqlalchemy import insert
from sqlalchemy.orm import Session

from toqqi.core.requisicao import ip_cliente
from toqqi.modelos import Auditoria

GRAVIDADES = ("info", "sucesso", "atencao", "erro")

ROTULOS = {
    "login_ok": "Entrou no sistema",
    "login_falhou": "Tentativa de entrada com senha errada",
    "cadastro_conta": "Conta criada",
    "usuario_criado": "Usuário adicionado",
    "usuario_alterado": "Usuário alterado",
    "usuario_bloqueado": "Usuário bloqueado",
    "usuario_excluido": "Usuário excluído",
    "permissoes_alteradas": "Permissões dos perfis alteradas",
    "seguranca_alterada": "Configurações de segurança alteradas",
    "senha_redefinida": "Senha redefinida pelo link de e-mail",
    "senha_alterada": "Senha alterada",
    "sessao_encerrada": "Sessão encerrada",
    "conta_criada_plataforma": "Conta criada pela equipe Toqqi",
    "teste_estendido": "Período de teste estendido",
    "cortesia": "Conta marcada como cortesia",
    "cadastro_excluido": "Item de cadastro excluído",
    "responsavel_excluido": "Responsável excluído",
    "empresa_excluida": "Empresa excluída",
    "contato_excluido": "Contato excluído",
    "importacao": "Planilha de contatos importada",
    "formulario_excluido": "Formulário excluído",
    "formulario_arquivado": "Formulário arquivado",
    "formulario_padrao": "Formulário padrão alterado",
}


def registrar(
    s: Session,
    evento: str,
    gravidade: str = "info",
    detalhe: dict | None = None,
    usuario_id: int | None = None,
    conta_id: int | None = None,
) -> None:
    """Grava um evento. Sem conta_id, usa a conta da transação (app_conta())."""
    assert evento in ROTULOS, f"evento desconhecido: {evento}"
    assert gravidade in GRAVIDADES
    valores = {
        "evento": evento,
        "gravidade": gravidade,
        "detalhe": detalhe or {},
        "usuario_id": usuario_id,
        "ip": ip_cliente.get(),
    }
    if conta_id is not None:
        valores["conta_id"] = conta_id
    s.execute(insert(Auditoria).values(**valores))
