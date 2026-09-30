"""GraphRAG 最小领域契约，与 CodeGraph 节点保持语义隔离。"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.evidence.models import EvidenceStatus


class KnowledgeNodeKind(StrEnum):
    """研究证据图中的知识节点类型。"""

    TECHNOLOGY = "technology"
    CONCEPT = "concept"
    CAPABILITY = "capability"


class KnowledgeNode(BaseModel):
    """GraphRAG 知识节点，不得复用 CodeGraph 的代码节点类型。"""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    kind: KnowledgeNodeKind
    name: str = Field(min_length=1)


class Claim(BaseModel):
    """关于项目的结论及其证据引用。"""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    status: EvidenceStatus
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def supported_claim_requires_evidence(self) -> "Claim":
        if self.status is EvidenceStatus.SUPPORTED and not self.evidence_ids:
            raise ValueError("supported Claim 必须至少引用一条 Evidence")
        return self
