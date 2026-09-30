"""Configuração lida de variáveis de ambiente (e de um arquivo .env, se existir)."""
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
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
    SUPERADMIN_EMAILS: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:5173"
    AUTO_MIGRATE: bool = True
    RATE_LIMIT_ENABLED: bool = True

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


@lru_cache
def config() -> Config:
    return Config()  # type: ignore[call-arg]
