"""Alembic 迁移环境。

口径：

- **URL 单一真源**：连接串从 `app.foundation.config.Settings` 读取（与运行期同源），
  不写进 `alembic.ini`，避免两处配置漂移。未配置时 fail-fast，不静默连到别处。
- **迁移比对源**：`Base.metadata`（见 `app/infrastructure/persistence/models.py`）。
- `compare_type=True`：列类型变更也要能被 autogenerate 检出。
- 异步引擎：与应用同一个 asyncpg 驱动，不额外引入同步驱动。

revision id 约定 **≤ 32 字符**——`alembic_version.version_num` 默认是 VARCHAR(32)，
超长会在全新库初始化时报 "value too long"（详见 docker/postgres/init.sql 的留档）。
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.foundation.config import get_settings
from app.infrastructure.persistence.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """从应用配置取连接串；未配置时明确失败。"""
    url = get_settings().database_url
    if not url:
        raise RuntimeError("未配置 DATABASE_URL：请在 .env 中设置后重试（见 .env.example 的分阶段 fail-fast 清单）")
    return url


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连接数据库。"""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
