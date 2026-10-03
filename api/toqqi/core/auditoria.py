"""Registro de eventos de auditoria da conta.

Etapa 5f: grupos dos eventos (`GRUPOS`, nesta ordem; cada evento de `ROTULOS` em exatamente um, por `grupo_de`), para
o filtro da tela de Auditoria e a exportação:
- `acesso` "Acesso e segurança": login_*, cadastro_conta, senha_*, sessao_encerrada, seguranca_alterada, termos_*;
- `equipe` "Equipe e permissões": usuario_criado/alterado/bloqueado, permissoes_alteradas;
- `configuracoes` "Configurações": config_*, dados_empresa_alterados, logo_*, formulario_padrao/arquivado,
  imagem_enviada, ia_analisar_recentes;
- `envios` "Envios e descadastros": envio_*, lembretes_automaticos, descadastro*;
- `dados` "Importações, edições e exportações": importacao*, resposta_editada, indicacao_registrada/atualizada,
  exportacao_*;
- `exclusoes` "Exclusões definitivas": todo *_excluido(a) menos os globais conta_excluida*, e zona_risco;
- `integracoes` "Integrações": chave_*, webhook_* (menos webhook_excluido), whatsapp_*;
- `assinatura` "Assinatura e conta": o resto (inclusive exclusao_avisada e os globais da plataforma).
"""
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
    "config_ia": "Configurações de IA alteradas",
    "ia_analisar_recentes": "Comentários dos últimos 90 dias enviados para análise da IA",
    "assinatura_criada": "Assinatura criada",
    "plano_alterado": "Plano da assinatura alterado",
    "dados_cobranca_alterados": "Dados de cobrança alterados",
    "assinatura_cancelada": "Assinatura cancelada",
    "pagamento_confirmado": "Pagamento confirmado",
    "pagamento_vencido": "Fatura vencida",
    "pagamento_estornado": "Pagamento estornado",
    "assinatura_adotada": "Assinatura encontrada no Asaas e ligada à conta",
    "assinatura_removida_no_asaas": "Assinatura duplicada removida no Asaas",
    "valor_realinhado": "Valor da assinatura corrigido no Asaas",
    "ambiente_asaas_trocado": "Cobrança de teste (sandbox) descartada",
    "termos_aceitos": "Aceitou os termos e a política de privacidade",
    "termos_revogados": "Retirou o aceite dos termos e da política de privacidade",
    "indicacao_registrada": "Indicação registrada à mão",
    "indicacao_atualizada": "Situação de uma indicação alterada",
    "indicacao_excluida": "Indicação excluída (pedido da pessoa indicada)",
    "config_crescimento": "Configurações de crescimento alteradas",
    "imagem_enviada": "Imagem enviada ao banco de imagens",
    "imagem_excluida": "Imagem excluída do banco de imagens",
    # etapa 5f
    "envio_automatico": "Pesquisas enviadas pelo envio automático",
    "lembretes_automaticos": "Lembretes enviados automaticamente",
    "chave_regerada": "Chave de integração gerada de novo (a anterior parou de valer)",
    "webhook_criado": "Webhook criado",
    "webhook_alterado": "Webhook alterado",
    "webhook_excluido": "Webhook excluído",
    "exportacao_conta": "Todos os dados da conta exportados",
    "exportacao_csv": "Lista exportada em CSV",
    "zona_risco": "Dados apagados pela zona de risco",
    "exclusao_avisada": "Aviso de exclusão da conta enviado",
    "conta_excluida_automatica": "Conta excluída automaticamente",
    "exclusao_automatica": "Rotina de exclusão de contas encerradas",
}

GRUPOS = {
    "acesso": "Acesso e segurança",
    "equipe": "Equipe e permissões",
    "configuracoes": "Configurações",
    "envios": "Envios e descadastros",
    "dados": "Importações, edições e exportações",
    "exclusoes": "Exclusões definitivas",
    "integracoes": "Integrações",
    "assinatura": "Assinatura e conta",
}


def _grupo(evento: str) -> str:
    """A regra do cabeçalho (a ordem dos testes importa: exclusões antes dos prefixos dos outros grupos)."""
    if evento.startswith("conta_excluida"):
        return "assinatura"  # globais da plataforma
    if evento.endswith(("_excluido", "_excluida")) or evento == "zona_risco":
        return "exclusoes"
    if evento.startswith(("login_", "senha_", "termos_")) or evento in (
            "cadastro_conta", "sessao_encerrada", "seguranca_alterada"):
        return "acesso"
    if evento in ("usuario_criado", "usuario_alterado", "usuario_bloqueado", "permissoes_alteradas"):
        return "equipe"
    if evento.startswith(("config_", "logo_")) or evento in (
            "dados_empresa_alterados", "formulario_padrao", "formulario_arquivado", "imagem_enviada",
            "ia_analisar_recentes"):
        return "configuracoes"
    if evento.startswith(("envio_", "descadastro")) or evento == "lembretes_automaticos":
        return "envios"
    if evento.startswith(("importacao", "exportacao_")) or evento in (
            "resposta_editada", "indicacao_registrada", "indicacao_atualizada"):
        return "dados"
    if evento.startswith(("chave_", "webhook_", "whatsapp_")):
        return "integracoes"
    return "assinatura"


GRUPO_DO_EVENTO = {evento: _grupo(evento) for evento in ROTULOS}


def grupo_de(evento: str) -> str:
    return GRUPO_DO_EVENTO.get(evento) or _grupo(evento)


def eventos_do_grupo(grupo: str) -> list[str]:
    return [e for e, g in GRUPO_DO_EVENTO.items() if g == grupo]


def grupos_json() -> list[dict]:
    return [{"chave": k, "rotulo": r} for k, r in GRUPOS.items()]


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
