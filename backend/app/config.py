from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

DemoGroup = Literal["clause-empregados", "clause-gestores", "clause-gestao-acervo"]


class DemoAccount(BaseModel):
    name: str = Field(min_length=1)
    groups: list[DemoGroup] = Field(min_length=1)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, env_ignore_empty=True, extra="ignore", hide_input_in_errors=True)
    postgres_db: str = "ipbot"
    postgres_user: str = "ipbot"
    postgres_password: SecretStr
    postgres_host: str = "db"
    postgres_port: int = 5432
    auth_secret: SecretStr = Field(min_length=32)
    auth_demo_enabled: bool = False
    auth_demo_sso_secret: SecretStr | None = Field(default=None, min_length=32)
    auth_demo_users: dict[str, DemoAccount] = Field(default_factory=dict)
    auth_cookie_secure: bool = True
    storage_path: Path = Path("/data/documents")
    collection_path: Path | None = None
    max_upload_bytes: int = 25 * 1024 * 1024
    worker_poll_seconds: float = 1.0
    bedrock_model_id: str | None = None
    bedrock_region: str = "us-east-1"
    bedrock_timeout_seconds: float = Field(default=5, ge=1, le=30)

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
