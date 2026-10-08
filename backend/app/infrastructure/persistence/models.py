"""PostgreSQL 关系表的 SQLAlchemy 模型（步骤 6）。

设计口径（ADR-009）：

- 每张表、每个索引、每条约束都必须指向**具体查询或业务不变量**；指不上的不进第一版。
- 表与列的 `comment` 说明「为什么存在」——这是 ADR-009 三层记录中的第二层
  （第一层是 Alembic 迁移，第三层是 docs/architecture/数据模型.md）。
- 访问模式的完整推导见 docs/architecture/数据模型.md §3.2（`scan`）/ §3.3（`scan_error`）。

闭合集合的取值来自 ADR-011；**新增取值属于契约变更**，必须同步改本文件的 CHECK 与迁移。
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 约束与索引的命名约定：让 Alembic 生成的迁移稳定可读，也便于排障时按名字定位。
_NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

SCAN_STATUSES = ("completed", "partial", "failed")
SCAN_STAGES = ("collect", "analyze", "persist")
SCAN_ERROR_SEVERITIES = ("local", "fatal")
SCAN_ERROR_CODES = (
    "path_invalid",
    "git_error",
    "file_unreadable",
    "file_encoding",
    "file_disappeared",
    "symlink_rejected",
    "syntax_error",
    "storage_error",
)


def _enum_check(column: str, values: tuple[str, ...]) -> str:
    """把闭合集合展开成 CHECK 表达式；取值均为内部字面量，无注入面。"""
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


class Base(DeclarativeBase):
    """所有关系表的公共基类；Alembic 以 `Base.metadata` 作为迁移比对源。"""

    metadata = MetaData(naming_convention=_NAMING_CONVENTION)


class ScanRow(Base):
    """一次扫描的元数据记录（访问模式 S1 / S2 / S3）。

    **为什么存在**：每次扫描是一次分析事件，其结局必须可查、可追溯。本表同时是定位
    CodeGraph Artifact 的索引——`repository_id` + `revision` + 契约版本足以找到产物。
    Artifact 本体不落库（ADR-006），故本表只存元数据。
    """

    __tablename__ = "scan"
    __table_args__ = (
        CheckConstraint(_enum_check("status", SCAN_STATUSES), name="status_closed_set"),
        CheckConstraint(
            "files_analyzed + files_failed <= files_collected",
            name="stats_funnel",
        ),
        CheckConstraint(
            "status = 'failed' OR revision IS NOT NULL",
            name="revision_required_unless_failed",
        ),
        CheckConstraint(
            "status = 'failed' OR (graph_schema_version IS NOT NULL AND parser_version IS NOT NULL)",
            name="graph_metadata_required_unless_failed",
        ),
        Index("ix_scan_repository_id_created_at", "repository_id", "created_at"),
        {
            "comment": (
                "扫描元数据；S1 按 (repository_id, revision) 定位结局与产物契约版本，"
                "S2 按仓库列历史（倒序）。CodeGraph 本体是 JSON Artifact，不在此表。"
            )
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="扫描记录标识；领域模型尚无 scan id，由持久化层生成",
    )
    repository_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="S1/S2 定位键之一；调用方提供的不透明标识，ADR-010 要求不含 ':'",
    )
    revision: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="S1 定位键之一；failed 结局允许为空（采集阶段就失败时拿不到 revision）",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="S1/S2 结局；ADR-011 闭合集合 completed / partial / failed",
    )
    files_collected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="S1 漏斗计数之一；来自 ScanStats，只存无法从图推导的阶段计数",
    )
    files_analyzed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="S1 漏斗计数之一；与 files_collected 共同支撑失败率与解析质量趋势",
    )
    files_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="S1 漏斗计数之一；与 code 维度的聚合共同定位质量退化",
    )
    graph_schema_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="S1 读 Artifact 时判定契约版本（ADR-010 的 schema_version）",
    )
    parser_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="S1 判定产出者实现版本；与契约版本相互独立（ADR-010）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="S2 排序键；写入时刻由数据库生成，避免依赖应用时钟",
    )


class ScanErrorRow(Base):
    """扫描过程中的结构化错误（访问模式 E1 / E2）。

    **为什么存在**：`ScanResult.errors` 是变长列表，且需要按扫描、按错误码检索与聚合。
    按 ADR-009 第 2 条，**参与 WHERE / 聚合的数据不得放 JSONB**，因此独立成表。
    """

    __tablename__ = "scan_error"
    __table_args__ = (
        CheckConstraint(_enum_check("stage", SCAN_STAGES), name="stage_closed_set"),
        CheckConstraint(_enum_check("severity", SCAN_ERROR_SEVERITIES), name="severity_closed_set"),
        CheckConstraint(_enum_check("code", SCAN_ERROR_CODES), name="code_closed_set"),
        Index("ix_scan_error_scan_id", "scan_id"),
        Index("ix_scan_error_code", "code"),
        {
            "comment": (
                "扫描的结构化错误；E1 按 scan_id 取某次扫描的全部错误，"
                "E2 按 code 聚合定位质量退化（时间维度经 scan.created_at 关联）。"
            )
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="错误记录标识；领域模型无此 id，由持久化层生成",
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("scan.id", ondelete="CASCADE"),
        nullable=False,
        comment="E1 归属；随 scan 级联删除，错误不能脱离扫描独立存在",
    )
    stage: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="E1 阶段；ADR-011 闭合集合 collect / analyze / persist",
    )
    code: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="E2 稳定错误码（ADR-011 闭合集合）；新增码属于契约变更",
    )
    severity: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="E1 严重度；local = 局部失败仍可产出图，fatal = 整体失败",
    )
    message: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="E1 面向人的说明；机器判定一律用 code，不解析本列",
    )
    file_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="E1 归属文件（仓库根相对 POSIX 路径）；错误不一定归属具体文件",
    )
