"""扫描用例的输入、阶段间与结果契约。

错误与统计决策见 ADR-011：扫描结果用单一模型表达成功 / 局部失败 / 整体失败，
阶段局部失败通过 CollectOutcome / AnalyzeOutcome 显式传回编排器。
"""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.codegraph.models import CodeGraph

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class ScanRequest(BaseModel):
    """第一阶段仅接收本地仓库路径和 Python 语言。"""

    model_config = _FROZEN

    repository_id: str = Field(min_length=1)
    path: Path
    languages: tuple[str, ...] = ("python",)


class SourceFile(BaseModel):
    """Collector 产出的单个源文件事实；path 为仓库根相对 POSIX 路径。"""

    model_config = _FROZEN

    path: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class SourceManifest(BaseModel):
    """特定 Git revision 下的确定性文件清单。"""

    model_config = _FROZEN

    schema_version: int = Field(default=1, ge=1)
    repository_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    files: tuple[SourceFile, ...] = ()


class ScanStage(StrEnum):
    """扫描流水线阶段。"""

    COLLECT = "collect"
    ANALYZE = "analyze"
    PERSIST = "persist"


class ScanErrorSeverity(StrEnum):
    """local = 局部失败，图仍可产出；fatal = 整体失败。"""

    LOCAL = "local"
    FATAL = "fatal"


class ScanErrorCode(StrEnum):
    """稳定错误码（闭合集合）；新增码属于契约变更。"""

    PATH_INVALID = "path_invalid"
    GIT_ERROR = "git_error"
    FILE_UNREADABLE = "file_unreadable"
    FILE_ENCODING = "file_encoding"
    FILE_DISAPPEARED = "file_disappeared"
    SYMLINK_REJECTED = "symlink_rejected"
    SYNTAX_ERROR = "syntax_error"
    STORAGE_ERROR = "storage_error"


class ScanError(BaseModel):
    """结构化阶段错误；message 面向人，code 面向机器。"""

    model_config = _FROZEN

    stage: ScanStage
    code: ScanErrorCode
    severity: ScanErrorSeverity
    message: str = Field(min_length=1)
    file_path: str | None = None


class ScanStats(BaseModel):
    """只存无法从图推导的阶段漏斗计数；耗时等非确定值只进日志。"""

    model_config = _FROZEN

    files_collected: int = Field(default=0, ge=0)
    files_analyzed: int = Field(default=0, ge=0)
    files_failed: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_funnel(self) -> "ScanStats":
        if self.files_analyzed + self.files_failed > self.files_collected:
            raise ValueError("files_analyzed + files_failed 不能超过 files_collected")
        return self


class CollectOutcome(BaseModel):
    """采集阶段结果：局部失败携带清单，整体失败携带 fatal 错误。"""

    model_config = _FROZEN

    manifest: SourceManifest | None = None
    errors: tuple[ScanError, ...] = ()

    @model_validator(mode="after")
    def validate_stage_and_output(self) -> "CollectOutcome":
        if any(error.stage is not ScanStage.COLLECT for error in self.errors):
            raise ValueError("CollectOutcome 只能包含 collect 阶段错误")
        if self.manifest is None and not _contains_fatal(self.errors):
            raise ValueError("采集无 fatal 错误时必须产出 manifest")
        return self


class AnalyzeOutcome(BaseModel):
    """分析阶段结果：局部失败（语法错误等）不阻断整体产出。"""

    model_config = _FROZEN

    graph: CodeGraph | None = None
    errors: tuple[ScanError, ...] = ()

    @model_validator(mode="after")
    def validate_stage_and_output(self) -> "AnalyzeOutcome":
        if any(error.stage is not ScanStage.ANALYZE for error in self.errors):
            raise ValueError("AnalyzeOutcome 只能包含 analyze 阶段错误")
        if self.graph is None and not _contains_fatal(self.errors):
            raise ValueError("分析无 fatal 错误时必须产出 CodeGraph")
        return self


class ScanStatus(StrEnum):
    """扫描的整体结局。"""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ScanResult(BaseModel):
    """扫描的最终结果；三种状态的不变量由校验器强制（ADR-011）。"""

    model_config = _FROZEN

    repository_id: str = Field(min_length=1)
    revision: str | None = None
    status: ScanStatus
    graph: CodeGraph | None = None
    errors: tuple[ScanError, ...] = ()
    stats: ScanStats = Field(default_factory=ScanStats)

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "ScanResult":
        match self.status:
            case ScanStatus.COMPLETED:
                if self.graph is None or self.errors:
                    raise ValueError("completed 必须产出图且没有任何错误")
                if self.revision is None:
                    raise ValueError("completed 必须携带 revision")
            case ScanStatus.PARTIAL:
                if self.graph is None or not self.errors:
                    raise ValueError("partial 必须产出图且至少有一条局部错误")
                if _contains_fatal(self.errors):
                    raise ValueError("partial 不允许包含 fatal 错误")
                if self.revision is None:
                    raise ValueError("partial 必须携带 revision")
            case ScanStatus.FAILED:
                if self.graph is not None:
                    raise ValueError("failed 不携带图")
                if not _contains_fatal(self.errors):
                    raise ValueError("failed 必须至少有一条 fatal 错误")
        if self.graph is not None:
            if self.graph.repository_id != self.repository_id:
                raise ValueError("graph.repository_id 与 ScanResult 不一致")
            if self.graph.revision != self.revision:
                raise ValueError("graph.revision 与 ScanResult 不一致")
        return self


def _contains_fatal(errors: tuple[ScanError, ...]) -> bool:
    return any(error.severity is ScanErrorSeverity.FATAL for error in errors)
