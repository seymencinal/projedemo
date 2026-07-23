from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, model_validator
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
    database_user: str | None = Field(default=None, min_length=1, pattern=r".*\S.*")
    database_password: SecretStr | None = None
    database_echo: bool = False
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    database_pool_timeout: int = Field(default=30, ge=1)
    database_pool_recycle: int = Field(default=1800, ge=-1)
    upload_storage_root: Path = Path("storage/uploads")
    max_upload_size_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    max_csv_rows: int = Field(default=100000, ge=1)
    max_csv_columns: int = Field(default=200, ge=1)
    csv_import_batch_size: int = Field(default=500, ge=1, le=5000)

    @model_validator(mode="after")
    def validate_database_credentials(self) -> Self:
        if self.environment in {Environment.LOCAL, Environment.TEST}:
            if self.database_user is None:
                self.database_user = "postgres"
            if self.database_password is None:
                self.database_password = SecretStr("postgres")
            return self

        if self.database_user is None or self.database_password is None:
            raise ValueError("Database credentials must be configured outside local and test.")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
