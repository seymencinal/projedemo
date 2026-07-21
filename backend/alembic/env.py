import asyncio
import logging
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.db.base import Base
from app.models.company import Company
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User

config = context.config
logger = logging.getLogger(__name__)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

assert Company.__table__ is Base.metadata.tables["companies"]  # noqa: S101
assert Membership.__table__ is Base.metadata.tables["memberships"]  # noqa: S101
assert Organization.__table__ is Base.metadata.tables["organizations"]  # noqa: S101
assert User.__table__ is Base.metadata.tables["users"]  # noqa: S101

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine_configuration = config.get_section(
        config.config_ini_section,
        {},
    )
    database_url = engine_configuration["sqlalchemy.url"]
    logger.info(
        "Alembic async engine URL: %s",
        make_url(database_url).render_as_string(hide_password=True),
    )
    connectable = async_engine_from_config(
        engine_configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
