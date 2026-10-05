"""Modelos ORM. O esquema real (incluindo RLS) é criado pelas migrações Alembic."""
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    Date,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import DateTime

TZ = DateTime(timezone=True)
AGORA = text("now()")
CONTA_ATUAL = text("app_conta()")


class Base(DeclarativeBase):
    pass


class Conta(Base):
    __tablename__ = "contas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nome: Mapped[str] = mapped_column(Text)
    plano: Mapped[str] = mapped_column(Text, server_default="profissional")
    situacao: Mapped[str] = mapped_column(Text, server_default="teste")
    teste_ate: Mapped[datetime | None] = mapped_column(TZ)
    sessao_minutos: Mapped[int] = mapped_column(Integer, server_default="60")
    termos_aceitos_em: Mapped[datetime | None] = mapped_column(TZ)
    termos_versao: Mapped[str | None] = mapped_column(Text)
    termos_ip: Mapped[str | None] = mapped_column(Text)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    # dados da empresa (Configurações › Empresa); o logo fica em `imagens`
    razao_social: Mapped[str | None] = mapped_column(Text)
    documento: Mapped[str | None] = mapped_column(Text)  # CPF (11 dígitos) ou CNPJ (14, alfanumérico em maiúsculas)
    telefone: Mapped[str | None] = mapped_column(Text)  # só dígitos, com 55
    email_contato: Mapped[str | None] = mapped_column(CITEXT)
    site: Mapped[str | None] = mapped_column(Text)
    cep: Mapped[str | None] = mapped_column(Text)
    logradouro: Mapped[str | None] = mapped_column(Text)
    numero: Mapped[str | None] = mapped_column(Text)
    complemento: Mapped[str | None] = mapped_column(Text)
    bairro: Mapped[str | None] = mapped_column(Text)
    cidade: Mapped[str | None] = mapped_column(Text)
    uf: Mapped[str | None] = mapped_column(Text)
    dados_atualizados_em: Mapped[datetime | None] = mapped_column(TZ)
    # etapa 4b: análise de comentários pela IA (chave da conta, ligada por padrão)
    ia_analise_respostas: Mapped[bool] = mapped_column(Boolean, server_default="true")
    # etapa 5a: cobrança (Asaas). `situacao` é decidida por assinatura.servico.recalcular
    asaas_cliente_id: Mapped[str | None] = mapped_column(Text)  # cliente no Asaas (reaproveitado)
    asaas_ambiente: Mapped[str | None] = mapped_column(Text)  # sandbox | producao (o do cliente acima)
    asaas_conferida_em: Mapped[date | None] = mapped_column(Date)  # última conferência diária (São Paulo)
    pago_ate: Mapped[date | None] = mapped_column(Date)  # último dia coberto por pagamento (inclusivo)
    atrasada_desde: Mapped[date | None] = mapped_column(Date)  # vencimento da fatura em atraso mais antiga
    # cópia do primeiro vencimento da assinatura ativa (null sem assinatura ativa): a regra de "liberada" sai só da
    # linha da conta, lida a cada requisição
    primeiro_vencimento: Mapped[date | None] = mapped_column(Date)
    # etapa 5d: como a IA escreve (Configurações › IA) e os passos sugeridos nas ações
    ia_modelo: Mapped[str] = mapped_column(Text, server_default="equilibrado")  # rapido | equilibrado | detalhado
    ia_estilo: Mapped[str] = mapped_column(Text, server_default="equilibrada")  # objetiva | equilibrada | criativa
    ia_passos_acoes: Mapped[bool] = mapped_column(Boolean, server_default="true")
    # etapa 5f: exclusão automática da conta encerrada (assinatura.regras.encerramento): o dia avisado aos
    # administradores e quando o aviso saiu (relógio do banco); os dois nulos ou os dois preenchidos
    exclusao_avisada_para: Mapped[date | None] = mapped_column(Date)
    exclusao_avisada_em: Mapped[datetime | None] = mapped_column(TZ)
    # etapa 5i: de onde veio o cadastro ({utm_source, utm_medium, utm_campaign}, só as presentes); nula = sem origem
    origem: Mapped[dict | None] = mapped_column(JSONB)


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contas.id"), server_default=CONTA_ATUAL)
    nome: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(CITEXT)
    senha_hash: Mapped[str] = mapped_column(Text)
    cargo: Mapped[str | None] = mapped_column(Text)
    telefone: Mapped[str | None] = mapped_column(Text)
    perfil: Mapped[str] = mapped_column(Text)
    situacao: Mapped[str] = mapped_column(Text, server_default="ativo")
    email_confirmado: Mapped[bool] = mapped_column(Boolean, server_default="false")
    ultimo_acesso: Mapped[datetime | None] = mapped_column(TZ)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    # etapa 4b: e-mails do Toqqi (Minha conta)
    recebe_resumo_semanal: Mapped[bool] = mapped_column(Boolean, server_default="true")
    recebe_alertas: Mapped[bool] = mapped_column(Boolean, server_default="true")


class Sessao(Base):
    __tablename__ = "sessoes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conta_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contas.id"), server_default=CONTA_ATUAL)
    usuario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuarios.id"))
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    ultimo_uso: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    expira_em: Mapped[datetime] = mapped_column(TZ)
    ip: Mapped[str | None] = mapped_column(Text)
    agente: Mapped[str | None] = mapped_column(Text)
    revogada_em: Mapped[datetime | None] = mapped_column(TZ)


class TokenUsoUnico(Base):
    __tablename__ = "tokens_uso_unico"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contas.id"), server_default=CONTA_ATUAL)
    usuario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuarios.id"))
    finalidade: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    expira_em: Mapped[datetime] = mapped_column(TZ)
    usado_em: Mapped[datetime | None] = mapped_column(TZ)


class PerfilPermissao(Base):
    __tablename__ = "perfil_permissoes"
    conta_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contas.id"), primary_key=True, server_default=CONTA_ATUAL)
    perfil: Mapped[str] = mapped_column(Text, primary_key=True)
    permissao: Mapped[str] = mapped_column(Text, primary_key=True)


class DominioLiberado(Base):
    __tablename__ = "dominios_liberados"
    conta_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contas.id"), server_default=CONTA_ATUAL)
    dominio: Mapped[str] = mapped_column(CITEXT, primary_key=True)


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("contas.id"), server_default=CONTA_ATUAL)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuarios.id"))
    evento: Mapped[str] = mapped_column(Text)
    gravidade: Mapped[str] = mapped_column(Text)
    detalhe: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    ip: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


# ---- etapa 2: cadastros, formulários e respostas ------------------------------

class _Auxiliar:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    nome: Mapped[str] = mapped_column(CITEXT)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Grupo(_Auxiliar, Base):
    __tablename__ = "grupos"


class Segmento(_Auxiliar, Base):
    __tablename__ = "segmentos"


class PerfilContato(_Auxiliar, Base):
    __tablename__ = "perfis_contato"


class Cargo(_Auxiliar, Base):
    __tablename__ = "cargos"


class Responsavel(Base):
    __tablename__ = "responsaveis"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    nome: Mapped[str] = mapped_column(Text)
    funcao: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(CITEXT)
    foto_url: Mapped[str | None] = mapped_column(Text)
    teams_webhook: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Empresa(Base):
    __tablename__ = "empresas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    nome: Mapped[str] = mapped_column(CITEXT)
    documento: Mapped[str | None] = mapped_column(Text)
    grupo_id: Mapped[int | None] = mapped_column(BigInteger)
    segmento_id: Mapped[int | None] = mapped_column(BigInteger)
    responsavel_id: Mapped[int | None] = mapped_column(BigInteger)
    valor_mensal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cliente_desde: Mapped[date | None] = mapped_column(Date)
    codigo_externo: Mapped[str | None] = mapped_column(Text)
    ativa: Mapped[bool] = mapped_column(Boolean, server_default="true")
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    # etapa 5i: desfecho. Perdida = `perdida_em` preenchida, com motivo e `ativa` false (o banco obriga); o histórico
    # (`EmpresaHistorico`) é gravado pelo gatilho `empresas_historico`
    renovacao_em: Mapped[date | None] = mapped_column(Date)  # renovação ou fim do contrato (passado permitido)
    perdida_em: Mapped[date | None] = mapped_column(Date)
    motivo_perda: Mapped[str | None] = mapped_column(Text)  # preco | concorrente | atendimento | produto | encerrou | outro
    motivo_detalhe: Mapped[str | None] = mapped_column(Text)  # até 300


class EmpresaHistorico(Base):
    """Etapa 5i: entrada, mudança de valor, perda e retorno de cada empresa, gravados pelo gatilho do banco (nunca pela
    aplicação: ela só passa `app.empresa_origem`, `app.usuario_id`, `app.hoje` e `app.contatos_desativados`)."""
    __tablename__ = "empresa_historico"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    empresa_id: Mapped[int] = mapped_column(BigInteger)
    tipo: Mapped[str] = mapped_column(Text)  # entrada | valor | perdida | reativada
    data: Mapped[date] = mapped_column(Date)  # o dia que vale para os cálculos
    valor_antes: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    valor_depois: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    motivo: Mapped[str | None] = mapped_column(Text)  # só (e sempre) na perdida
    motivo_detalhe: Mapped[str | None] = mapped_column(Text)
    contatos: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))  # só na perdida: os ids desativados
    origem: Mapped[str] = mapped_column(Text)  # tela | importacao | api | migracao | sistema
    usuario_id: Mapped[int | None] = mapped_column(BigInteger)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Contato(Base):
    __tablename__ = "contatos"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    codigo: Mapped[str] = mapped_column(Text)
    nome: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(CITEXT)
    telefone: Mapped[str | None] = mapped_column(Text)
    empresa_id: Mapped[int | None] = mapped_column(BigInteger)
    cargo_id: Mapped[int | None] = mapped_column(BigInteger)
    perfil_id: Mapped[int | None] = mapped_column(BigInteger)
    codigo_externo: Mapped[str | None] = mapped_column(Text)
    recebe_pesquisas: Mapped[bool] = mapped_column(Boolean, server_default="true")
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true")
    ultima_nota: Mapped[int | None] = mapped_column(SmallInteger)
    proximo_envio: Mapped[date | None] = mapped_column(Date)
    ultimo_envio: Mapped[datetime | None] = mapped_column(TZ)
    falhas: Mapped[int] = mapped_column(Integer, server_default="0")
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Formulario(Base):
    __tablename__ = "formularios"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    nome: Mapped[str] = mapped_column(Text)
    descricao: Mapped[str] = mapped_column(Text, server_default="")
    perguntas: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    tema: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true")
    publico: Mapped[bool] = mapped_column(Boolean, server_default="true")
    codigo_publico: Mapped[str] = mapped_column(Text)
    padrao_nps: Mapped[bool] = mapped_column(Boolean, server_default="false")
    padrao_csat: Mapped[bool] = mapped_column(Boolean, server_default="false")
    arquivado: Mapped[bool] = mapped_column(Boolean, server_default="false")
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    atualizado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Convite(Base):
    __tablename__ = "convites"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    token_hash: Mapped[str] = mapped_column(Text)
    formulario_id: Mapped[int] = mapped_column(BigInteger)
    contato_id: Mapped[int | None] = mapped_column(BigInteger)
    empresa_id: Mapped[int | None] = mapped_column(BigInteger)
    canal: Mapped[str] = mapped_column(Text)
    assunto: Mapped[str | None] = mapped_column(Text)
    referencia: Mapped[str | None] = mapped_column(Text)
    contexto: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    respondido_em: Mapped[datetime | None] = mapped_column(TZ)
    lembretes_enviados: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    ultimo_lembrete_em: Mapped[datetime | None] = mapped_column(TZ)
    token_semente: Mapped[str | None] = mapped_column(Text)
    evento: Mapped[str | None] = mapped_column(Text)
    # etapa 5c: tentativas de indicação aceitas pela página pública (as repetidas também; o limite é por convite)
    indicacoes_feitas: Mapped[int] = mapped_column(Integer, server_default="0")
    # conectores: de onde veio (ex.: "rd:<negociação>") e quando a resposta foi anotada lá
    origem_externa: Mapped[str | None] = mapped_column(Text)
    devolvida_em: Mapped[datetime | None] = mapped_column(TZ)


class Resposta(Base):
    __tablename__ = "respostas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    formulario_id: Mapped[int] = mapped_column(BigInteger)
    convite_id: Mapped[int | None] = mapped_column(BigInteger)
    contato_id: Mapped[int | None] = mapped_column(BigInteger)
    empresa_id: Mapped[int | None] = mapped_column(BigInteger)
    canal: Mapped[str] = mapped_column(Text)
    nota: Mapped[int | None] = mapped_column(SmallInteger)
    tipo_nota: Mapped[str | None] = mapped_column(Text)
    grupo: Mapped[str | None] = mapped_column(Text)
    comentario: Mapped[str] = mapped_column(Text, server_default="")
    respostas: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    contexto: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    referencia: Mapped[str | None] = mapped_column(Text)
    ip_hash: Mapped[str | None] = mapped_column(Text)
    arquivada: Mapped[bool] = mapped_column(Boolean, server_default="false")
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    # etapa 4a
    respondida_em: Mapped[datetime | None] = mapped_column(TZ)  # data informada (à mão, importação)
    data_resposta: Mapped[datetime] = mapped_column(TZ, Computed("coalesce(respondida_em, criada_em)", persisted=True))
    origem: Mapped[str] = mapped_column(Text, server_default="pesquisa")
    temas: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    temas_manuais: Mapped[bool] = mapped_column(Boolean, server_default="false")
    o_que_faltou: Mapped[str | None] = mapped_column(Text)
    o_que_combinamos: Mapped[str | None] = mapped_column(Text)
    analisada_em: Mapped[datetime | None] = mapped_column(TZ)
    analisada_por: Mapped[int | None] = mapped_column(BigInteger)
    registrada_por: Mapped[int | None] = mapped_column(BigInteger)
    arquivada_em: Mapped[datetime | None] = mapped_column(TZ)
    # só o que o cliente escreveu (painel, palavras, temas); `comentario` segue sendo o resumo da etapa 2
    comentario_cliente: Mapped[str] = mapped_column(Text, server_default="")
    # etapa 4b: análise pela IA (null = não passa pela IA)
    ia_situacao: Mapped[str | None] = mapped_column(Text)  # pendente | analisada | falhou | limite
    ia_temas: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))  # [{tema, sentimento}]
    ia_sentimento: Mapped[str | None] = mapped_column(Text)
    ia_resumo: Mapped[str | None] = mapped_column(Text)
    ia_modelo: Mapped[str | None] = mapped_column(Text)
    ia_em: Mapped[datetime | None] = mapped_column(TZ)
    ia_tentativas: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    ia_reservada_em: Mapped[datetime | None] = mapped_column(TZ)
    ia_texto_hash: Mapped[str | None] = mapped_column(Text)
    # colunas geradas (regra em classe_tema, migração 0007)
    temas_reclamacao: Mapped[list[str]] = mapped_column(
        ARRAY(Text), Computed("temas_reclamacao(temas, ia_temas, ia_situacao, grupo)", persisted=True))
    temas_elogio: Mapped[list[str]] = mapped_column(
        ARRAY(Text), Computed("temas_elogio(temas, ia_temas, ia_situacao, grupo)", persisted=True))


class Importacao(Base):
    __tablename__ = "importacoes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=text("gen_random_uuid()"))
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    usuario_id: Mapped[int] = mapped_column(BigInteger)
    arquivo_nome: Mapped[str] = mapped_column(Text)
    dados: Mapped[list] = mapped_column(JSONB)
    colunas: Mapped[list] = mapped_column(JSONB)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    expira_em: Mapped[datetime] = mapped_column(TZ)
    tipo: Mapped[str] = mapped_column(Text, server_default="contatos")  # contatos | respostas


# ---- etapa 3a: envios ---------------------------------------------------------

class ConfigEnvios(Base):
    __tablename__ = "config_envios"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    envios_ativos: Mapped[bool] = mapped_column(Boolean, server_default="false")
    envio_automatico: Mapped[bool] = mapped_column(Boolean, server_default="false")
    formulario_id: Mapped[int | None] = mapped_column(BigInteger)
    intervalo_dias: Mapped[int] = mapped_column(Integer, server_default="90")
    descanso_dias: Mapped[int] = mapped_column(Integer, server_default="30")
    lembretes: Mapped[int] = mapped_column(Integer, server_default="3")
    dias_lembretes: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    janela_inicio: Mapped[time] = mapped_column(Time)
    janela_fim: Mapped[time] = mapped_column(Time)
    so_dias_uteis: Mapped[bool] = mapped_column(Boolean, server_default="true")
    responder_para: Mapped[str | None] = mapped_column(CITEXT)
    remetente_nome: Mapped[str | None] = mapped_column(Text)
    assunto_convite: Mapped[str] = mapped_column(Text)
    texto_convite: Mapped[str] = mapped_column(Text)
    assunto_lembrete: Mapped[str] = mapped_column(Text)
    texto_lembrete: Mapped[str] = mapped_column(Text)
    texto_whatsapp: Mapped[str] = mapped_column(Text)
    agradecimento_ativo: Mapped[bool] = mapped_column(Boolean, server_default="true")
    agradecimento: Mapped[dict] = mapped_column(JSONB)
    canal: Mapped[str] = mapped_column(Text, server_default="email")
    robo_rodou_em: Mapped[datetime | None] = mapped_column(TZ)
    lembretes_rodou_em: Mapped[date | None] = mapped_column(Date)
    atualizado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    # etapa 5e: visual dos e-mails de pesquisa (texto puro; nenhum HTML da conta entra no e-mail)
    email_cor: Mapped[str | None] = mapped_column(Text)  # #RRGGBB (maiúsculas); nula = a cor do formulário do envio
    email_mostrar_logo: Mapped[bool] = mapped_column(Boolean, server_default="true")
    email_imagem_topo_id: Mapped[int | None] = mapped_column(BigInteger)  # imagem 'banco' da conta (SET NULL)
    email_assinatura: Mapped[str | None] = mapped_column(Text)  # até 300
    email_rodape: Mapped[str | None] = mapped_column(Text)  # até 500
    # etapa 5i: ocultar "Pesquisa feita com Toqqi" (só vale onde o plano permite; a regra é calculada ao mostrar)
    ocultar_mencao_toqqi: Mapped[bool] = mapped_column(Boolean, server_default="false")


class Envio(Base):
    __tablename__ = "envios"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    contato_id: Mapped[int | None] = mapped_column(BigInteger)
    convite_id: Mapped[int | None] = mapped_column(BigInteger)
    resposta_id: Mapped[int | None] = mapped_column(BigInteger)
    acao_id: Mapped[int | None] = mapped_column(BigInteger)  # tipo 'retorno' (melhoria 4)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger)
    canal: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    origem: Mapped[str] = mapped_column(Text)
    situacao: Mapped[str] = mapped_column(Text, server_default="pendente")
    para: Mapped[str] = mapped_column(Text)
    erro: Mapped[str | None] = mapped_column(Text)
    lembrete: Mapped[int | None] = mapped_column(SmallInteger)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    tentativa_em: Mapped[datetime | None] = mapped_column(TZ)
    enviado_em: Mapped[datetime | None] = mapped_column(TZ)
    wamid: Mapped[str | None] = mapped_column(Text)
    cobranca: Mapped[str | None] = mapped_column(Text)


class Descadastro(Base):
    __tablename__ = "descadastros"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    email: Mapped[str | None] = mapped_column(CITEXT)
    telefone: Mapped[str | None] = mapped_column(Text)
    motivo: Mapped[str | None] = mapped_column(Text)
    origem: Mapped[str] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


# ---- etapa 3b: integrações e WhatsApp automático ------------------------------

class IntegracaoChave(Base):
    __tablename__ = "integracao_chaves"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    hash: Mapped[str] = mapped_column(Text)
    prefixo: Mapped[str] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    ultimo_uso: Mapped[datetime | None] = mapped_column(TZ)


class Webhook(Base):
    __tablename__ = "webhooks"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    url: Mapped[str] = mapped_column(Text)
    eventos: Mapped[list[str]] = mapped_column(ARRAY(Text))
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true")
    segredo_cifrado: Mapped[str] = mapped_column(Text)
    segredo_prefixo: Mapped[str] = mapped_column(Text)
    falhas_seguidas: Mapped[int] = mapped_column(Integer, server_default="0")
    ultima_entrega_em: Mapped[datetime | None] = mapped_column(TZ)
    ultimo_status_http: Mapped[int | None] = mapped_column(Integer)
    ultima_ok: Mapped[bool | None] = mapped_column(Boolean)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class WebhookEntrega(Base):
    __tablename__ = "webhook_entregas"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=text("gen_random_uuid()"))
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    webhook_id: Mapped[int] = mapped_column(BigInteger)
    evento: Mapped[str] = mapped_column(Text)
    corpo: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default="pendente")
    tentativas: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    proxima_tentativa: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    status_http: Mapped[int | None] = mapped_column(Integer)
    erro: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class WhatsappConta(Base):
    __tablename__ = "whatsapp_contas"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    phone_number_id: Mapped[str] = mapped_column(Text)
    waba_id: Mapped[str] = mapped_column(Text)
    token_cifrado: Mapped[str] = mapped_column(Text)
    modelo_nome: Mapped[str] = mapped_column(Text)
    modelo_idioma: Mapped[str] = mapped_column(Text)
    modelo_botao: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true")
    excedente_ativo: Mapped[bool] = mapped_column(Boolean, server_default="false")
    ultimo_erro: Mapped[str | None] = mapped_column(Text)
    numero_exibicao: Mapped[str | None] = mapped_column(Text)
    nome_verificado: Mapped[str | None] = mapped_column(Text)
    conectado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class WhatsappUso(Base):
    __tablename__ = "whatsapp_uso"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    mes: Mapped[str] = mapped_column(Text, primary_key=True)
    usadas: Mapped[int] = mapped_column(Integer, server_default="0")
    excedentes: Mapped[int] = mapped_column(Integer, server_default="0")
    avisou_80: Mapped[bool] = mapped_column(Boolean, server_default="false")
    avisou_100: Mapped[bool] = mapped_column(Boolean, server_default="false")


class EventoIdempotencia(Base):
    __tablename__ = "eventos_idempotencia"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    id_evento: Mapped[str] = mapped_column(Text, primary_key=True)
    resposta: Mapped[dict] = mapped_column(JSONB)
    expira: Mapped[datetime] = mapped_column(TZ)


# ---- etapa 4a: planos de ação -------------------------------------------------

class Acao(Base):
    __tablename__ = "acoes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    resposta_id: Mapped[int | None] = mapped_column(BigInteger)
    empresa_id: Mapped[int | None] = mapped_column(BigInteger)
    contato_id: Mapped[int | None] = mapped_column(BigInteger)
    responsavel_id: Mapped[int | None] = mapped_column(BigInteger)  # responsaveis (carteira), não usuário
    titulo: Mapped[str] = mapped_column(Text)
    descricao: Mapped[str] = mapped_column(Text, server_default="")
    resolucao: Mapped[str | None] = mapped_column(Text)
    prioridade: Mapped[str] = mapped_column(Text)
    prazo: Mapped[date | None] = mapped_column(Date)
    situacao: Mapped[str] = mapped_column(Text, server_default="a_fazer")
    origem: Mapped[str] = mapped_column(Text, server_default="manual")
    grupo: Mapped[str | None] = mapped_column(Text)
    tipo_nota: Mapped[str | None] = mapped_column(Text)
    nota: Mapped[int | None] = mapped_column(SmallInteger)
    criado_por: Mapped[int | None] = mapped_column(BigInteger)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    atualizada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    iniciada_em: Mapped[datetime | None] = mapped_column(TZ)
    concluida_em: Mapped[datetime | None] = mapped_column(TZ)
    concluida_por: Mapped[int | None] = mapped_column(BigInteger)
    # etapa 5d: passos sugeridos pela IA (null = a ação não passa pela IA)
    ia_passos: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))  # 1 a 3 textos, só com 'pronta'
    ia_passos_situacao: Mapped[str | None] = mapped_column(Text)  # pendente | pronta | falhou | limite
    ia_passos_em: Mapped[datetime | None] = mapped_column(TZ)
    ia_passos_tentativas: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    ia_passos_reservada_em: Mapped[datetime | None] = mapped_column(TZ)
    # melhoria 4: retorno ao cliente ("você falou, nós fizemos"), enviado uma vez depois de concluída
    retorno_texto: Mapped[str | None] = mapped_column(Text)
    retorno_em: Mapped[datetime | None] = mapped_column(TZ)


class ConfigAcoes(Base):
    __tablename__ = "config_acoes"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    prazo_detrator: Mapped[int] = mapped_column(Integer, server_default="2")
    prazo_neutro: Mapped[int] = mapped_column(Integer, server_default="5")
    prazo_promotor: Mapped[int] = mapped_column(Integer, server_default="7")
    acao_promotor: Mapped[bool] = mapped_column(Boolean, server_default="false")
    atualizado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Imagem(Base):
    """Logo da conta ou de um formulário, ou imagem do banco de imagens da conta (etapa 5e). `dados` só é lido quando
    pedido (deferred): os bytes não vêm junto nas buscas de URL."""
    __tablename__ = "imagens"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    uso: Mapped[str] = mapped_column(Text)  # logo_conta | logo_formulario | banco
    formulario_id: Mapped[int | None] = mapped_column(BigInteger)
    chave: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    dados: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    tamanho: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(Text)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    # etapa 5e (banco de imagens): nome do arquivo enviado (limpo) e dimensões lidas do cabeçalho (nulas se não deu)
    nome: Mapped[str | None] = mapped_column(Text)
    largura: Mapped[int | None] = mapped_column(Integer)
    altura: Mapped[int | None] = mapped_column(Integer)


# ---- etapa 4b: IA, picos e resumo semanal ----------------------------------------

class IaUsoMensal(Base):
    __tablename__ = "ia_uso_mensal"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    mes: Mapped[date] = mapped_column(Date, primary_key=True)  # dia 1 do mês (São Paulo)
    analises: Mapped[int] = mapped_column(Integer, server_default="0")
    tokens_entrada: Mapped[int] = mapped_column(BigInteger, server_default="0")
    tokens_saida: Mapped[int] = mapped_column(BigInteger, server_default="0")
    # etapa 5b: cota de IA do plano (hoje só o assistente gasta), separada do teto da análise por resposta acima
    cota_usada: Mapped[int] = mapped_column(Integer, server_default="0")
    cota_tokens_entrada: Mapped[int] = mapped_column(BigInteger, server_default="0")
    cota_tokens_saida: Mapped[int] = mapped_column(BigInteger, server_default="0")


class IaParecer(Base):
    """Etapa 5d: o último resumo do painel ou parecer dos relatórios gerado para um recorte (filtros canônicos)."""
    __tablename__ = "ia_pareceres"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    tipo: Mapped[str] = mapped_column(Text)  # painel | relatorios
    chave: Mapped[str] = mapped_column(Text)  # filtros canônicos: de=…|ate=…|grupo=…|ativos=1
    filtros: Mapped[dict] = mapped_column(JSONB)  # {de, ate, grupo_id, so_ativos}
    conteudo: Mapped[dict] = mapped_column(JSONB)
    modelo: Mapped[str] = mapped_column(Text)  # o nível: rapido | equilibrado | detalhado
    estilo: Mapped[str] = mapped_column(Text)
    gerado_por: Mapped[int | None] = mapped_column(BigInteger)
    gerado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class AlertaPico(Base):
    __tablename__ = "alertas_pico"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    tema: Mapped[str] = mapped_column(Text)
    reclamacoes: Mapped[int] = mapped_column(Integer)
    media_anterior: Mapped[Decimal] = mapped_column(Numeric(6, 1))
    detectado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    enviado_em: Mapped[datetime | None] = mapped_column(TZ)
    destinatarios: Mapped[int] = mapped_column(Integer, server_default="0")


class ResumoSemanal(Base):
    __tablename__ = "resumos_semanais"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    semana: Mapped[date] = mapped_column(Date)  # a segunda-feira da semana resumida
    enviado_em: Mapped[datetime | None] = mapped_column(TZ)
    destinatarios: Mapped[int] = mapped_column(Integer, server_default="0")


# ---- etapa 5a: assinatura e cobrança (Asaas) ----------------------------------------

class Assinatura(Base):
    __tablename__ = "assinaturas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    asaas_id: Mapped[str] = mapped_column(Text)
    ambiente: Mapped[str] = mapped_column(Text)  # sandbox | producao: o do Asaas em que ela existe
    plano: Mapped[str] = mapped_column(Text)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    situacao: Mapped[str] = mapped_column(Text, server_default="ativa")  # ativa | cancelada
    razao_social: Mapped[str] = mapped_column(Text)
    documento: Mapped[str] = mapped_column(Text)  # CPF (11 dígitos) ou CNPJ (14, alfanumérico em maiúsculas)
    email_cobranca: Mapped[str] = mapped_column(CITEXT)
    telefone: Mapped[str] = mapped_column(Text)  # só dígitos, com 55
    primeiro_vencimento: Mapped[date] = mapped_column(Date)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    criada_por: Mapped[int | None] = mapped_column(BigInteger)
    cancelada_em: Mapped[datetime | None] = mapped_column(TZ)
    cancelada_por: Mapped[int | None] = mapped_column(BigInteger)
    nao_encontrada_desde: Mapped[date | None] = mapped_column(Date)  # 1º dia seguido de 404 na conferência


class Cobranca(Base):
    __tablename__ = "cobrancas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    assinatura_id: Mapped[int | None] = mapped_column(BigInteger)
    asaas_id: Mapped[str] = mapped_column(Text)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    valor_liquido: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    vencimento: Mapped[date] = mapped_column(Date)
    situacao: Mapped[str] = mapped_column(Text)  # pendente | paga | vencida | estornada | removida
    situacao_asaas: Mapped[str | None] = mapped_column(Text)
    forma: Mapped[str | None] = mapped_column(Text)  # pix | boleto | cartao
    pago_em: Mapped[datetime | None] = mapped_column(TZ)
    link: Mapped[str | None] = mapped_column(Text)  # fatura do Asaas (Pix, boleto ou cartão)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    atualizada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class AsaasEvento(Base):
    """Avisos do webhook do Asaas (tabela da plataforma: só em modo sistema). Só ids e tipo, nunca o corpo."""
    __tablename__ = "asaas_eventos"
    id: Mapped[str] = mapped_column(Text, primary_key=True)  # id do evento ("evt_...")
    tipo: Mapped[str] = mapped_column(Text)
    conta_id: Mapped[int | None] = mapped_column(BigInteger)
    cobranca_asaas_id: Mapped[str | None] = mapped_column(Text)
    assinatura_asaas_id: Mapped[str | None] = mapped_column(Text)
    recebido_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    processado_em: Mapped[datetime | None] = mapped_column(TZ)
    ignorado: Mapped[bool] = mapped_column(Boolean, server_default="false")
    tentativas: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    erro: Mapped[str | None] = mapped_column(Text)


class AsaasRemocao(Base):
    """Assinatura que precisa ser removida no Asaas e ainda não foi (a tarefa `assinaturas` tenta de novo)."""
    __tablename__ = "asaas_remocoes"
    asaas_id: Mapped[str] = mapped_column(Text, primary_key=True)
    ambiente: Mapped[str] = mapped_column(Text)
    conta_id: Mapped[int | None] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    motivo: Mapped[str] = mapped_column(Text)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    tentativas: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    erro: Mapped[str | None] = mapped_column(Text)
    removida_em: Mapped[datetime | None] = mapped_column(TZ)


# ---- aceite dos termos e da política de privacidade (LGPD) -------------------------

class AceiteTermos(Base):
    """Aceite de uma versão dos Termos de uso e da Política de privacidade (prova: quem, quando, IP, navegador)."""
    __tablename__ = "aceites_termos"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger)  # nulo quando o membro foi removido em Equipe
    usuario_email: Mapped[str] = mapped_column(CITEXT)  # cópia do momento do aceite (a prova não depende do usuário)
    usuario_nome: Mapped[str] = mapped_column(Text)
    versao: Mapped[int] = mapped_column(Integer)
    aceito_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    ip: Mapped[str | None] = mapped_column(Text)
    agente: Mapped[str | None] = mapped_column(Text)  # User-Agent, até 400 caracteres
    origem: Mapped[str] = mapped_column(Text)  # cadastro | tela
    # retirada do aceite: a linha fica como prova; aceitar de novo cria uma linha nova (único parcial em vigor)
    revogado_em: Mapped[datetime | None] = mapped_column(TZ)
    revogado_ip: Mapped[str | None] = mapped_column(Text)
    revogado_agente: Mapped[str | None] = mapped_column(Text)  # User-Agent, até 400 caracteres
# ---- etapa 5c: crescimento (indicações e oportunidades) -------------------------------

class ConfigCrescimento(Base):
    __tablename__ = "config_crescimento"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    indicacoes_ativas: Mapped[bool] = mapped_column(Boolean, server_default="false")
    titulo_convite: Mapped[str] = mapped_column(Text)
    texto_convite: Mapped[str] = mapped_column(Text)
    recompensa: Mapped[str | None] = mapped_column(Text)
    texto_oferta: Mapped[str] = mapped_column(Text)
    atualizado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Indicacao(Base):
    """Pessoa indicada por um promotor (origem 'pesquisa', pelo convite) ou registrada à mão ('manual')."""
    __tablename__ = "indicacoes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    origem: Mapped[str] = mapped_column(Text)  # pesquisa | manual
    convite_id: Mapped[int | None] = mapped_column(BigInteger)
    resposta_id: Mapped[int | None] = mapped_column(BigInteger)
    indicador_contato_id: Mapped[int | None] = mapped_column(BigInteger)
    indicador_empresa_id: Mapped[int | None] = mapped_column(BigInteger)
    pode_identificar: Mapped[bool] = mapped_column(Boolean, server_default="true")
    nome: Mapped[str] = mapped_column(Text)
    empresa: Mapped[str | None] = mapped_column(Text)
    telefone: Mapped[str | None] = mapped_column(Text)  # só dígitos, com 55
    email: Mapped[str | None] = mapped_column(CITEXT)
    observacao: Mapped[str | None] = mapped_column(Text)
    situacao: Mapped[str] = mapped_column(Text, server_default="nova")  # nova | em_contato | cliente | nao_avancou
    responsavel_id: Mapped[int | None] = mapped_column(BigInteger)  # responsaveis (carteira), não usuário
    valor_mensal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # só 'cliente'
    motivo: Mapped[str | None] = mapped_column(Text)  # só 'nao_avancou'
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    atualizada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    criada_por: Mapped[int | None] = mapped_column(BigInteger)
    atualizada_por: Mapped[int | None] = mapped_column(BigInteger)


class Oferta(Base):
    """Oferta feita a um cliente feliz (WhatsApp do representante com o texto pronto, ou e-mail), com o resultado."""
    __tablename__ = "ofertas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    empresa_id: Mapped[int] = mapped_column(BigInteger)
    contato_id: Mapped[int | None] = mapped_column(BigInteger)
    lista: Mapped[str] = mapped_column(Text)  # pode_crescer | promotores
    canal: Mapped[str] = mapped_column(Text, server_default="whatsapp")  # whatsapp | email
    texto: Mapped[str] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    resultado: Mapped[str | None] = mapped_column(Text)  # aceitou | recusou | sem_resposta
    valor: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # só 'aceitou'
    resultado_em: Mapped[datetime | None] = mapped_column(TZ)


# ---- etapa 5e: registro de e-mails enviados ------------------------------------------------

class EmailEnviado(Base):
    """E-mail que saiu (ou tentou sair) em nome de uma conta: pesquisas e e-mails do sistema. Nada do corpo; guardado
    por 90 dias (tarefa `limpeza`)."""
    __tablename__ = "emails_enviados"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    tipo: Mapped[str] = mapped_column(Text)  # core.email.TIPOS
    destinatario: Mapped[str] = mapped_column(CITEXT)
    assunto: Mapped[str] = mapped_column(Text)  # como saiu, cortado em 300
    situacao: Mapped[str] = mapped_column(Text)  # enviado | falhou
    erro: Mapped[str | None] = mapped_column(Text)  # texto simples de core.email.traduzir_falha, só com 'falhou'
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


# ---- etapa 5f: registros de acesso (Marco Civil da Internet, art. 15) ------------------------

class RegistroAcesso(Base):
    """Data, hora e IP de cada acesso (entradas e tentativas, cadastro, pedido de acesso, senha trocada pelo link e
    envios públicos de resposta e indicação), guardados por 6 meses (tarefa `limpeza`). Sem FK: sobrevive à exclusão
    do usuário e da conta. RLS: a aplicação só grava (em conta, com a própria conta); ler e apagar, só em modo sistema
    (core.acessos)."""
    __tablename__ = "registros_acesso"
    __table_args__ = {"implicit_returning": False}  # INSERT sem RETURNING: em conta, o RLS não deixa ler a linha
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    evento: Mapped[str] = mapped_column(Text)  # core.acessos.EVENTOS
    conta_id: Mapped[int | None] = mapped_column(BigInteger)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger)
    item_id: Mapped[int | None] = mapped_column(BigInteger)  # a resposta ou a indicação
    ip: Mapped[str | None] = mapped_column(Text)


# ---- etapa 5g: parâmetros da plataforma -----------------------------------------------------

class Parametro(Base):
    """Valor que difere do padrão (core.parametros). Sem conta: RLS só em modo sistema, salvo a leitura dos limites de
    contatos (`planos.%.contatos`), que o gatilho do limite faz no contexto da conta. Só a chave e o valor: quem alterou
    e quando ficam em `parametros_historico` (a conta não lê)."""
    __tablename__ = "parametros"
    chave: Mapped[str] = mapped_column(Text, primary_key=True)
    valor: Mapped[object] = mapped_column(JSONB(none_as_null=False))  # texto "149.00", inteiro, null ou texto


class ParametroHistorico(Base):
    """Cada alteração salva em Plataforma › Parâmetros (imutável: o papel da aplicação só lê e insere)."""
    __tablename__ = "parametros_historico"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    grupo: Mapped[str] = mapped_column(Text)  # planos | ia | whatsapp | teste
    por: Mapped[str] = mapped_column(Text)  # e-mail de quem salvou
    mudancas: Mapped[list] = mapped_column(JSONB)  # [{chave, de, para}], valores efetivos


# ---- etapa 5h: aviso de erros ---------------------------------------------------------------

class Erro(Base):
    """Uma falha diferente (pela `impressao`) da API, do site ou de uma tarefa, com a contagem de ocorrências
    (`core.erros`). Só o que diagnostica, sem dados pessoais; guardada por 30 dias depois da última ocorrência (tarefa
    `limpeza`). Sem conta na RLS: só o modo sistema lê e grava; `conta_id` sem FK. `resolvido_em` nulo = aberto."""
    __tablename__ = "erros"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    impressao: Mapped[str] = mapped_column(Text)  # sha256 (64 hex) de origem + tipo + local + linha útil da pilha
    origem: Mapped[str] = mapped_column(Text)  # api | site | tarefa
    tipo: Mapped[str] = mapped_column(Text)
    mensagem: Mapped[str] = mapped_column(Text, server_default="")
    local: Mapped[str] = mapped_column(Text, server_default="")
    pilha: Mapped[str] = mapped_column(Text, server_default="")
    versao: Mapped[str] = mapped_column(Text)
    ocorrencias: Mapped[int] = mapped_column(Integer, server_default="1")
    primeira_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    ultima_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    ultimo_request_id: Mapped[str | None] = mapped_column(Text)
    conta_id: Mapped[int | None] = mapped_column(BigInteger)
    resolvido_em: Mapped[datetime | None] = mapped_column(TZ)


# ---- etapa 5j: conectores (RD Station CRM) ----------------------------------------------------

class Conector(Base):
    """Ligação da conta com um sistema dela (`provedor`): o token cifrado, o hash do segredo do endereço que recebe os
    avisos do provedor, as opções e o resultado da última sincronização (`modulos/conectores`)."""
    __tablename__ = "conectores"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    provedor: Mapped[str] = mapped_column(Text)  # rdstation_crm
    token_cifrado: Mapped[str] = mapped_column(Text)
    segredo_hash: Mapped[str] = mapped_column(Text)
    webhook_externo: Mapped[str | None] = mapped_column(Text)  # id do webhook cadastrado no provedor
    opcoes: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    sincronizado_em: Mapped[datetime | None] = mapped_column(TZ)
    resumo: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    erro: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    atualizado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
