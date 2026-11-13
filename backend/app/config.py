from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")
    postgres_db: str = "ipbot"
    postgres_user: str = "ipbot"
    postgres_password: SecretStr
    postgres_host: str = "db"
    postgres_port: int = 5432
    auth_secret: SecretStr = Field(min_length=32)
    auth_demo_enabled: bool = False
    auth_demo_users: dict[str, dict[str, str]] = {}
    storage_path: Path = Path("/data/documents")
    max_upload_bytes: int = 25 * 1024 * 1024
    worker_poll_seconds: float = 1.0

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
