"""CodeGraph 的稳定中间表示。"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.codegraph.ids import build_edge_id, node_id_matches, validate_repository_id
from app.domain.codegraph.kinds import CallResolution, EdgeKind, EntryKind, NodeKind


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
    source_span: SourceSpan | None = None
    resolution: CallResolution | None = None
    is_truncated: bool = False

    @model_validator(mode="after")
    def validate_call_fields(self) -> "CodeEdge":
        if self.kind is EdgeKind.CALLS:
            if self.source_span is None or self.resolution not in (
                CallResolution.RESOLVED,
                CallResolution.AMBIGUOUS,
            ):
                raise ValueError("CALLS 边必须携带 source_span 与 resolved/ambiguous resolution")
            if self.is_truncated and self.resolution is not CallResolution.AMBIGUOUS:
                raise ValueError("is_truncated 只能用于 ambiguous CALLS 边")
        elif self.source_span is not None or self.resolution is not None or self.is_truncated:
            raise ValueError("非 CALLS 边不得携带调用解析字段")
        return self


class EntryPoint(BaseModel):
    """图级代码入口；与结构边分离。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: EntryKind
    module_id: str = Field(min_length=1)
    span: SourceSpan
    symbol: str | None = None
    target_node_id: str | None = None


class ProviderRecord(BaseModel):
    """本次图产物使用的外部分析提供方记录。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    asset_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    tools_used: tuple[str, ...] = ()


class CodeGraph(BaseModel):
    """单次、单版本扫描产生的确定性代码图。

    schema_version 是 Artifact 契约版本：仅在破坏性结构变更时 +1（ADR-010）；
    parser_version 描述产出它的解析器实现版本，两者相互独立。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=2, ge=1)
    repository_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    nodes: tuple[CodeNode, ...] = ()
    edges: tuple[CodeEdge, ...] = ()
    entries: tuple[EntryPoint, ...] = ()
    provenance: tuple[ProviderRecord, ...] = ()

    @model_validator(mode="after")
    def validate_identity_rules(self) -> "CodeGraph":
        validate_repository_id(self.repository_id)
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("CodeGraph 内节点 ID 重复")
        node_id_set = set(node_ids)
        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("CodeGraph 内边 ID 重复（同一关系只保留一条）")
        for node in self.nodes:
            if not node_id_matches(node.id, self.repository_id, node.kind, node.qualified_name):
                raise ValueError(f"节点 ID 不符合构造规则: {node.id}")
        for edge in self.edges:
            if edge.id != build_edge_id(edge.kind, edge.source_id, edge.target_id):
                raise ValueError(f"边 ID 不符合构造规则: {edge.id}")
            if edge.source_id not in node_id_set or edge.target_id not in node_id_set:
                raise ValueError(f"边引用不存在的节点: {edge.id}")
        nodes_by_id = {node.id: node for node in self.nodes}
        for edge in self.edges:
            if (
                edge.kind is EdgeKind.CALLS
                and edge.source_span is not None
                and nodes_by_id[edge.source_id].source.file_path != edge.source_span.file_path
            ):
                raise ValueError(f"CALLS source_span 必须与调用源位于同一文件: {edge.id}")
        entry_keys: list[tuple[str, int, int, str]] = []
        for entry in self.entries:
            module = nodes_by_id.get(entry.module_id)
            if module is None or module.kind is not NodeKind.MODULE:
                raise ValueError(f"入口 module_id 必须引用模块节点: {entry.module_id}")
            if module.source.file_path != entry.span.file_path:
                raise ValueError(f"入口 span 必须与模块位于同一文件: {entry.module_id}")
            if entry.target_node_id is not None:
                target = nodes_by_id.get(entry.target_node_id)
                if target is None or target.kind is not NodeKind.FUNCTION:
                    raise ValueError(f"入口 target_node_id 必须引用函数节点: {entry.target_node_id}")
                if target.source.file_path != entry.span.file_path:
                    raise ValueError(f"入口目标必须与入口位于同一文件: {entry.target_node_id}")
            entry_keys.append((entry.module_id, entry.span.line_start, entry.span.line_end, entry.kind.value))
        if entry_keys != sorted(entry_keys) or len(entry_keys) != len(set(entry_keys)):
            raise ValueError("entries 必须按固定键升序且唯一")
        provider_names = [provider.name for provider in self.provenance]
        if provider_names != sorted(provider_names) or len(provider_names) != len(set(provider_names)):
            raise ValueError("provenance 必须按 name 升序且唯一")
        return self
