from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, make_url, pool

from pybase.core.config import get_settings
from pybase.infrastructure.database.base import Base
import pybase.infrastructure.database.models  # noqa: F401，确保迁移工具加载所有模型

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
if not settings.database.url:
    raise RuntimeError("数据库迁移需要配置 PYBASE_DATABASE__URL")

url = make_url(settings.database.url)
# 应用使用异步驱动；Alembic 使用与已安装同步驱动匹配的 URL。
sync_driver_names = {
    "postgresql+asyncpg": "postgresql+psycopg",
    "postgresql+psycopg_async": "postgresql+psycopg",
    "mysql+asyncmy": "mysql+pymysql",
    "mysql+aiomysql": "mysql+pymysql",
    "sqlite+aiosqlite": "sqlite",
}
if sync_driver_name := sync_driver_names.get(url.drivername):
    url = url.set(drivername=sync_driver_name)
config.set_main_option("sqlalchemy.url", str(url))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
