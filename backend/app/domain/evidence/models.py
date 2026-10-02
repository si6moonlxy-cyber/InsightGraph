"""文档证据和代码证据共用的最小模型。"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EvidenceStatus(StrEnum):
    """结论可信状态；无证据时不得标记为 supported。"""

    SUPPORTED = "supported"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    UNSUPPORTED = "unsupported"


class SourceReference(BaseModel):
    """证据来源，可指向文档或代码范围。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    codegraph_node_id: str | None = None


class Evidence(BaseModel):
    """支撑结论的最小证据单元。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    status: EvidenceStatus
    excerpt_hash: str | None = None
    source: SourceReference
