from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine

from app.config import get_settings


@lru_cache
def get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def get_migration_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
