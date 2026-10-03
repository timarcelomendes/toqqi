"""Configuração lida de variáveis de ambiente (e de um arquivo .env, se existir)."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Conexão usada pela aplicação: papel SEM superusuário e SEM BYPASSRLS (ex.: toqqi_app).
    DATABASE_URL: str = "postgresql+psycopg://toqqi_app:toqqi_app@localhost:5432/toqqi_dev"
    # Conexão usada para migrações (dono das tabelas). Se vazia, usa DATABASE_URL.
    MIGRATION_DATABASE_URL: str = ""
    JWT_SECRET: str
    FRONTEND_URL: str = "http://localhost:5173"
    API_PUBLIC_URL: str = "http://localhost:8000"
    EMAIL_PROVIDER: Literal["console", "memory", "zeptomail", "resend"] = "console"
    ZEPTOMAIL_TOKEN: str = ""
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Toqqi <nao-responda@toqqi.com>"
    # "producao" não aceita o provedor console como envio de pesquisas.
    AMBIENTE: Literal["desenvolvimento", "producao"] = "desenvolvimento"
    # Protege POST /interno/tarefas (rodar as tarefas à mão). Vazio = rota desligada (404).
    TAREFAS_TOKEN: str = ""
    SUPERADMIN_EMAILS: str = ""
    # Cifra segredos guardados no banco (token do WhatsApp, segredos dos webhooks). Fora de produção,
    # vazio = derivada do JWT_SECRET.
    SEGREDOS_KEY: str = ""
    # WhatsApp (API oficial da Meta, Cloud API)
    WHATSAPP_GRAPH_URL: str = "https://graph.facebook.com"
    WHATSAPP_GRAPH_VERSION: str = "v23.0"
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""
    # IA por resposta (OpenAI, Responses API). A chave é da plataforma: só no painel do Render (toqqi-api e
    # toqqi-tarefas). Sem chave, a análise por IA fica desligada e os temas seguem por palavras-chave.
    OPENAI_API_KEY: str = ""
    IA_PROVEDOR: Literal["openai", "memoria", "desligado"] = "openai"
    IA_MODELO: str = "gpt-5-mini"
    IA_ESFORCO: str = "minimal"  # vazio = não manda `reasoning`
    IA_BASE_URL: str = "https://api.openai.com"
    # Assistente (etapa 5b): mesma chave e mesmo provedor da IA por resposta; cada pergunta gasta 1 análise da cota
    # mensal do plano (Essencial 100, Profissional 500, Empresa 2.000; cortesia = IA_COTA_CORTESIA).
    IA_ASSISTENTE_MODELO: str = "gpt-5-mini"
    IA_ASSISTENTE_ESFORCO: str = "low"  # vazio = não manda `reasoning`
    IA_COTA_CORTESIA: int = Field(default=500, ge=0)
    # Níveis de modelo (etapa 5d, Configurações › IA): valem para o assistente, o resumo do painel, o parecer dos
    # relatórios e os passos das ações (a análise de cada resposta segue com IA_MODELO/IA_ESFORCO). Esforço vazio =
    # não manda `reasoning`; no equilibrado, vazio = o do assistente (IA_ASSISTENTE_MODELO/IA_ASSISTENTE_ESFORCO).
    IA_MODELO_RAPIDO: str = "gpt-5-nano"
    IA_ESFORCO_RAPIDO: str = "minimal"
    IA_MODELO_EQUILIBRADO: str = ""
    IA_ESFORCO_EQUILIBRADO: str = ""
    IA_MODELO_DETALHADO: str = "gpt-5"
    IA_ESFORCO_DETALHADO: str = "low"
    # Cobrança (Asaas). Só no painel do Render: ASAAS_API_KEY em toqqi-api e toqqi-tarefas; ASAAS_WEBHOOK_TOKEN só
    # em toqqi-api. O endereço segue a chave ($aact_prod_ → produção; o resto → sandbox); ASAAS_URL sobrepõe
    # (Asaas falso local, testes). Sem chave, a tela de assinatura avisa que a cobrança online não está disponível.
    ASAAS_API_KEY: str = ""
    ASAAS_WEBHOOK_TOKEN: str = ""
    ASAAS_URL: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:5173"
    AUTO_MIGRATE: bool = True
    RATE_LIMIT_ENABLED: bool = True
    # Etapa 5f: cabeçalho com o IP do cliente posto pelo proxy da frente (core.requisicao.IpDoCliente). Vazio = o
    # endereço da conexão (desenvolvimento e testes); no Render, atrás da Cloudflare: CF-Connecting-IP (a Cloudflare
    # sobrescreve o que o cliente mandar). X-Forwarded-For e X-Real-IP nunca são lidos.
    IP_CLIENTE_CABECALHO: str = ""
    # Etapa 5f: exclusão automática das contas encerradas (tarefa `limpeza`): `ligada` avisa e exclui (com os freios
    # de assinatura.exclusao); `simular` só conta e registra no log. Qualquer outro valor (ex.: "desligada") também só
    # simula, com um aviso no log a cada rodada: um valor errado não impede a API de subir nem liga a exclusão.
    EXCLUSAO_AUTOMATICA: str = "simular"
    # Papel restrito da aplicação. Com APP_DB_PASSWORD definido, a API cria/atualiza esse papel
    # na subida (usando a conexão de migração) e passa a se conectar com ele. Ideal para o Render,
    # onde só existe a URL do dono do banco.
    APP_DB_ROLE: str = "toqqi_app"
    APP_DB_PASSWORD: str = ""
    # Primeiro acesso da plataforma: cria a conta "Toqqi" com este admin, se ainda não existir.
    ADMIN_INICIAL_EMAIL: str = ""
    ADMIN_INICIAL_SENHA: str = ""
    ADMIN_INICIAL_NOME: str = "Administrador"
    ADMIN_INICIAL_EMPRESA: str = "Toqqi"

    @field_validator("DATABASE_URL", "MIGRATION_DATABASE_URL")
    @classmethod
    def _driver_psycopg(cls, v: str) -> str:
        # O Render entrega postgres://...; o SQLAlchemy precisa de postgresql+psycopg://
        for prefixo in ("postgres://", "postgresql://"):
            if v.startswith(prefixo):
                return "postgresql+psycopg://" + v[len(prefixo):]
        return v

    @field_validator("APP_DB_ROLE")
    @classmethod
    def _papel_valido(cls, v: str) -> str:
        import re
        if not re.fullmatch(r"[a-z_][a-z0-9_]{0,40}", v):
            raise ValueError("APP_DB_ROLE inválido")
        return v

    @field_validator("JWT_SECRET")
    @classmethod
    def _segredo_forte(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("JWT_SECRET precisa ter pelo menos 16 caracteres.")
        return v

    @property
    def superadmins(self) -> set[str]:
        return {e.strip().lower() for e in self.SUPERADMIN_EMAILS.split(",") if e.strip()}

    @property
    def origens(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def url_migracao(self) -> str:
        return self.MIGRATION_DATABASE_URL or self.DATABASE_URL

    @property
    def url_app(self) -> str:
        """URL da aplicação: com APP_DB_PASSWORD, a mesma base conectando como o papel restrito."""
        if not self.APP_DB_PASSWORD:
            return self.DATABASE_URL
        from sqlalchemy.engine import make_url
        return make_url(self.url_migracao).set(
            username=self.APP_DB_ROLE, password=self.APP_DB_PASSWORD).render_as_string(hide_password=False)


@lru_cache
def config() -> Config:
    return Config()  # type: ignore[call-arg]
