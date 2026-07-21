from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.app_name == "AI Market Intelligence API"
    assert settings.app_version == "0.1.0"
    assert settings.environment is Environment.LOCAL
    assert settings.debug is False
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_host == "localhost"
    assert settings.database_port == 5432
    assert settings.database_name == "market_intelligence"
    assert settings.database_user == "postgres"
    assert settings.database_password.get_secret_value() == "postgres"
    assert settings.database_echo is False


def test_settings_accept_explicit_values() -> None:
    settings = Settings(  # type: ignore[call-arg]
        app_name="Market API",
        app_version="1.2.3",
        environment=Environment.STAGING,
        debug=True,
        api_v1_prefix="/api/v2",
        database_host="db.internal",
        database_port=6432,
        database_name="market_test",
        database_user="market_user",
        database_password="strong-password",  # type: ignore[arg-type]  # noqa: S106
        database_echo=True,
        _env_file=None,
    )

    assert settings.app_name == "Market API"
    assert settings.app_version == "1.2.3"
    assert settings.environment is Environment.STAGING
    assert settings.debug is True
    assert settings.api_v1_prefix == "/api/v2"
    assert settings.database_host == "db.internal"
    assert settings.database_port == 6432
    assert settings.database_name == "market_test"
    assert settings.database_user == "market_user"
    assert settings.database_password.get_secret_value() == "strong-password"
    assert settings.database_echo is True


def test_settings_reads_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_NAME", "Environment Market API")
    monkeypatch.setenv("APP_VERSION", "2.0.0")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("API_V1_PREFIX", "/api/v3")
    monkeypatch.setenv("DATABASE_HOST", "postgres.internal")
    monkeypatch.setenv("DATABASE_PORT", "6433")
    monkeypatch.setenv("DATABASE_NAME", "environment_market")
    monkeypatch.setenv("DATABASE_USER", "environment_user")
    monkeypatch.setenv("DATABASE_PASSWORD", "environment-password")
    monkeypatch.setenv("DATABASE_ECHO", "true")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.app_name == "Environment Market API"
    assert settings.app_version == "2.0.0"
    assert settings.environment is Environment.PRODUCTION
    assert settings.debug is True
    assert settings.api_v1_prefix == "/api/v3"
    assert settings.database_host == "postgres.internal"
    assert settings.database_port == 6433
    assert settings.database_name == "environment_market"
    assert settings.database_user == "environment_user"
    assert settings.database_password.get_secret_value() == "environment-password"
    assert settings.database_echo is True


@pytest.mark.parametrize("app_name", ["", " ", "   "])
def test_settings_rejects_blank_app_name(app_name: str) -> None:
    with pytest.raises(ValidationError):
        Settings(app_name=app_name, _env_file=None)  # type: ignore[call-arg]


@pytest.mark.parametrize("api_v1_prefix", ["", "api/v1", "v1"])
def test_settings_rejects_invalid_api_prefix(api_v1_prefix: str) -> None:
    with pytest.raises(ValidationError):
        Settings(api_v1_prefix=api_v1_prefix, _env_file=None)  # type: ignore[call-arg]


def test_get_settings_returns_cached_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.delenv("API_V1_PREFIX", raising=False)
    monkeypatch.delenv("DATABASE_HOST", raising=False)
    monkeypatch.delenv("DATABASE_PORT", raising=False)
    monkeypatch.delenv("DATABASE_NAME", raising=False)
    monkeypatch.delenv("DATABASE_USER", raising=False)
    monkeypatch.delenv("DATABASE_PASSWORD", raising=False)
    monkeypatch.delenv("DATABASE_ECHO", raising=False)

    first = get_settings()
    second = get_settings()

    assert first is second


@pytest.mark.parametrize("database_port", [0, -1, 65536])
def test_settings_rejects_invalid_database_port(database_port: int) -> None:
    with pytest.raises(ValidationError):
        Settings(database_port=database_port, _env_file=None)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("database_host", ""),
        ("database_host", "   "),
        ("database_name", ""),
        ("database_name", "   "),
        ("database_user", ""),
        ("database_user", "   "),
    ],
)
def test_settings_rejects_blank_database_fields(
    field_name: str,
    field_value: str,
) -> None:
    with pytest.raises(ValidationError):
        Settings(  # type: ignore[call-arg]
            **{field_name: field_value},  # type: ignore[arg-type]
            _env_file=None,
        )


def test_database_password_is_masked() -> None:
    settings = Settings(  # type: ignore[call-arg]
        database_password="super-secret-password",  # type: ignore[arg-type]  # noqa: S106
        _env_file=None,
    )

    assert settings.database_password.get_secret_value() == "super-secret-password"
    assert "super-secret-password" not in repr(settings)
    assert "super-secret-password" not in str(settings.model_dump())
