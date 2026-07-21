from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
    )

    app_name: str = Field(default="AI Market Intelligence API", min_length=1, pattern=r".*\S.*")
    app_version: str = "0.1.0"
    environment: Environment = Environment.LOCAL
    debug: bool = False
    api_v1_prefix: str = Field(default="/api/v1", min_length=1, pattern=r"^/.*")
    database_host: str = Field(default="localhost", min_length=1, pattern=r".*\S.*")
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = Field(default="market_intelligence", min_length=1, pattern=r".*\S.*")
    database_user: str = Field(default="postgres", min_length=1, pattern=r".*\S.*")
    database_password: SecretStr = SecretStr("postgres")
    database_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
