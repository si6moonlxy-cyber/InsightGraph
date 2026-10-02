"""CodeGraph 的稳定中间表示。"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.codegraph.ids import build_edge_id, node_id_matches, validate_repository_id
from app.domain.codegraph.kinds import EdgeKind, NodeKind


class SourceSpan(BaseModel):
    """可回溯到源文件的准确范围；file_path 为仓库根相对 POSIX 路径。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_line_order(self) -> "SourceSpan":
        if self.line_end < self.line_start:
            raise ValueError("line_end 不能小于 line_start")
        return self


class CodeNode(BaseModel):
    """稳定、确定性的 CodeGraph 节点；ID 规则见 ids.py 与 ADR-010。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    kind: NodeKind
    qualified_name: str = Field(min_length=1)
    language: str = Field(min_length=1)
    source: SourceSpan
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class CodeEdge(BaseModel):
    """两个代码节点之间的有向结构关系；同一 (kind, source, target) 只保留一条。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    kind: EdgeKind
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)


class CodeGraph(BaseModel):
    """单次、单版本扫描产生的确定性代码图。

    schema_version 是 Artifact 契约版本：仅在破坏性结构变更时 +1（ADR-010）；
    parser_version 描述产出它的解析器实现版本，两者相互独立。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=1, ge=1)
    repository_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    nodes: tuple[CodeNode, ...] = ()
    edges: tuple[CodeEdge, ...] = ()

    @model_validator(mode="after")
    def validate_identity_rules(self) -> "CodeGraph":
        validate_repository_id(self.repository_id)
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("CodeGraph 内节点 ID 重复")
        node_id_set = set(node_ids)
        for node in self.nodes:
            if not node_id_matches(node.id, self.repository_id, node.kind, node.qualified_name):
                raise ValueError(f"节点 ID 不符合构造规则: {node.id}")
        for edge in self.edges:
            if edge.id != build_edge_id(edge.kind, edge.source_id, edge.target_id):
                raise ValueError(f"边 ID 不符合构造规则: {edge.id}")
            if edge.source_id not in node_id_set or edge.target_id not in node_id_set:
                raise ValueError(f"边引用不存在的节点: {edge.id}")
        return self
