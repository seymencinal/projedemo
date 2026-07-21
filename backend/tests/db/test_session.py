from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings
from app.db.session import (
    build_database_url,
    create_database_engine,
    create_session_factory,
)


def test_build_database_url() -> None:
    password = "secret-password"  # noqa: S105
    settings = Settings(  # type: ignore[call-arg]
        database_host="db.internal",
        database_port=6432,
        database_name="market_db",
        database_user="market_user",
        database_password=password,  # type: ignore[arg-type]
        _env_file=None,
    )

    url = build_database_url(settings)

    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg"
    assert url.username == "market_user"
    assert url.password == password
    assert url.host == "db.internal"
    assert url.port == 6432
    assert url.database == "market_db"


def test_build_database_url_handles_special_characters() -> None:
    password = "p@ss:word/with?special#characters"  # noqa: S105
    settings = Settings(  # type: ignore[call-arg]
        database_password=password,  # type: ignore[arg-type]
        _env_file=None,
    )

    url = build_database_url(settings)

    assert url.password == password
    assert password not in str(url)


def test_create_database_engine() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    engine = create_database_engine(settings)

    assert isinstance(engine, AsyncEngine)
    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.host == "localhost"
    assert engine.url.database == "market_intelligence"


def test_create_session_factory() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    session = session_factory()

    assert isinstance(session, AsyncSession)
    assert session.bind is engine
    assert session.sync_session.expire_on_commit is False
    assert session.autoflush is False


def test_engine_url_masks_database_password() -> None:
    password = "do-not-expose-this-password"  # noqa: S105
    settings = Settings(  # type: ignore[call-arg]
        database_password=password,  # type: ignore[arg-type]
        _env_file=None,
    )

    engine = create_database_engine(settings)

    assert password not in str(engine.url)
    assert password not in repr(engine.url)
