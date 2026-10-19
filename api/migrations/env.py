import os
from logging.config import fileConfig

from alembic import context
from dotenv import dotenv_values
from sqlalchemy import create_engine, pool

from app.core.config import REPO_ROOT
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def migration_url() -> str:
    """Migrations run as the schema owner (smayaa_owner), never as the runtime app role."""
    url = os.environ.get("MIGRATION_DATABASE_URL") or dotenv_values(
        REPO_ROOT / ".env", encoding="utf-8-sig"
    ).get("MIGRATION_DATABASE_URL")
    if not url:
        raise RuntimeError("MIGRATION_DATABASE_URL is not set (environment or .env)")
    return url


def run_migrations_offline() -> None:
    context.configure(url=migration_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(migration_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
