"""迁移的集成验证：对真实 PostgreSQL 执行迁移并核对访问模式清单。

默认命令会排除本用例（`-m "not integration"`）；需要真实数据库：

    cd backend && uv run pytest -m integration

核对口径来自 docs/architecture/数据模型.md §3.2 / §3.3：
表、列、CHECK 约束、索引、表注释都必须与清单一致。
"""

import asyncio
from pathlib import Path
from typing import TypedDict

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.foundation.config import get_settings

_BACKEND_ROOT = Path(__file__).resolve().parents[2]

# 访问模式清单里逐项推导出来的结构；改动需同步 docs/architecture/数据模型.md。
_EXPECTED_COLUMNS = {
    "scan": {
        "id",
        "repository_id",
        "revision",
        "status",
        "files_collected",
        "files_analyzed",
        "files_failed",
        "graph_schema_version",
        "parser_version",
        "created_at",
    },
    "scan_error": {"id", "scan_id", "stage", "code", "severity", "message", "file_path"},
}

_EXPECTED_CONSTRAINTS = {
    "ck_scan_status_closed_set",
    "ck_scan_stats_funnel",
    "ck_scan_revision_required_unless_failed",
    "ck_scan_graph_metadata_required_unless_failed",
    "ck_scan_error_stage_closed_set",
    "ck_scan_error_severity_closed_set",
    "ck_scan_error_code_closed_set",
    "fk_scan_error_scan_id_scan",
}

_EXPECTED_INDEXES = {
    "ix_scan_repository_id_created_at",
    "ix_scan_error_scan_id",
    "ix_scan_error_code",
}


class SchemaSnapshot(TypedDict):
    """从真实库读回的结构快照。"""

    tables: set[str]
    columns: dict[str, set[str]]
    constraints: set[str]
    indexes: set[str]
    comments: dict[str, str | None]
    version: str | None


def _alembic_config() -> Config:
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    return config


async def _collect_schema(url: str) -> SchemaSnapshot:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            tables = {
                row[0]
                for row in await connection.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                )
            }
            columns = {
                table: {
                    row[0]
                    for row in await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = :table"
                        ),
                        {"table": table},
                    )
                }
                for table in ("scan", "scan_error")
            }
            constraints = {
                row[0]
                for row in await connection.execute(
                    text("SELECT conname FROM pg_constraint WHERE connamespace = 'public'::regnamespace")
                )
            }
            indexes = {
                row[0]
                for row in await connection.execute(
                    text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
                )
            }
            comments = {
                row[0]: row[1]
                for row in await connection.execute(
                    text(
                        "SELECT relname, obj_description(oid, 'pg_class') FROM pg_class "
                        "WHERE relname IN ('scan', 'scan_error')"
                    )
                )
            }
            version = (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar()
    finally:
        await engine.dispose()

    return {
        "tables": tables,
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
        "comments": comments,
        "version": version,
    }


@pytest.mark.integration
def test_migrations_apply_and_match_access_patterns() -> None:
    """迁移可重复执行（幂等），且落库结构与访问模式清单一致。"""
    settings = get_settings()
    if not settings.database_url:
        pytest.skip("未配置 DATABASE_URL：跳过迁移集成测试（见 .env.example）")

    # 幂等：已到 head 时不产生任何变更，因此本用例可在任意时刻重复运行。
    command.upgrade(_alembic_config(), "head")

    snapshot = asyncio.run(_collect_schema(settings.database_url))

    assert snapshot["version"] is not None, "alembic_version 未写入：迁移未生效"
    assert snapshot["tables"] >= {"scan", "scan_error"}

    for table, expected in _EXPECTED_COLUMNS.items():
        assert snapshot["columns"][table] == expected, f"{table} 列集合与访问模式清单不一致"

    assert snapshot["constraints"] >= _EXPECTED_CONSTRAINTS, "约束缺失：闭合集合 / 漏斗 / 不变量必须落库"
    assert snapshot["indexes"] >= _EXPECTED_INDEXES, "索引缺失：每个索引都必须指向具体查询"

    # ADR-009 三层记录的第二层：表注释必须说明「为什么存在」。
    for table in ("scan", "scan_error"):
        assert snapshot["comments"].get(table), f"{table} 缺少表注释（ADR-009 要求表自描述）"
