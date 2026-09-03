import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from app.models.base import Base
import app.models  # Important: imports User so Alembic can detect the table.
from app.models import User, Profile, Session, Message

target_metadata = Base.metadata

# Alembic Config object, which provides access to alembic.ini values.
config = context.config

# Load variables from the project's .env file.
load_dotenv()

database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise ValueError("DATABASE_URL is missing from the .env file.")

# Override the placeholder URL in alembic.ini with the real local URL.
# Replacing % prevents issues if a future password contains that character.
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# Configure Python logging from alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is the metadata containing all our SQLAlchemy models/tables.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without connecting directly to the database."""
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations while connected to the database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()