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
    "config_envios": "Configurações de envio alteradas",
    "envio_manual": "Pesquisas enviadas manualmente",
    "descadastro": "Contato saiu da lista de pesquisas",
    "descadastro_desfeito": "Contato voltou a receber pesquisas",
    "conta_excluida": "Conta excluída pela equipe Toqqi",
    "chave_gerada": "Chave de integração gerada",
    "chave_revogada": "Chave de integração revogada",
    "webhook_desativado": "Webhook desativado após falhas seguidas",
    "whatsapp_conectado": "WhatsApp automático conectado",
    "whatsapp_desconectado": "WhatsApp automático desconectado",
    "resposta_editada": "Resposta alterada na análise",
    "resposta_excluida": "Resposta excluída",
    "importacao_respostas": "Planilha de respostas antigas importada",
    "acao_excluida": "Plano de ação excluído",
    "config_acoes": "Configurações dos planos de ação alteradas",
    "dados_empresa_alterados": "Dados da empresa alterados",
    "logo_alterado": "Logo da empresa alterado",
    "logo_removido": "Logo da empresa removido",
    "config_ia": "Análise de comentários com IA ligada ou desligada",
    "ia_analisar_recentes": "Comentários dos últimos 90 dias enviados para análise da IA",
}


def registrar(
    s: Session,
    evento: str,
    gravidade: str = "info",
    detalhe: dict | None = None,
    usuario_id: int | None = None,
    conta_id: int | None = None,
) -> None:
    """Grava um evento. Sem conta_id, usa a conta da transação (app_conta()); em modo sistema, sem conta
    alguma, o evento fica global (visível só pela plataforma)."""
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
