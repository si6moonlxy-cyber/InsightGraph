"""CodeGraphAI 调用关系原始 DTO 与宽容解析。"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.infrastructure.code_intelligence.raw_models.symbol import RawSymbol


class RawCallEdge(BaseModel):
    """引擎边；仅 calls 白名单会进入后续映射。"""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    from_id: str = Field(alias="from")
    to_id: str = Field(alias="to")
    type: str

    @field_validator("from_id", "to_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return str(value)


class RawCallGraph(BaseModel):
    """单个符号的 depth=1 原始调用子图。"""

    model_config = ConfigDict(extra="ignore")

    nodes: tuple[RawSymbol, ...] = ()
    edges: tuple[RawCallEdge, ...] = ()
    root: str
    root_node: RawSymbol | None = None

    @field_validator("root", mode="before")
    @classmethod
    def normalize_root(cls, value: object) -> str:
        return str(value)

    @classmethod
    def parse_lossy(cls, payload: Mapping[str, object]) -> tuple["RawCallGraph", int]:
        """逐条跳过外部 schema 中的坏记录，返回有效图与坏记录数。"""
        invalid = 0
        nodes: list[RawSymbol] = []
        raw_nodes = payload.get("nodes")
        if isinstance(raw_nodes, list):
            for item in raw_nodes:
                try:
                    nodes.append(RawSymbol.model_validate(item))
                except ValidationError:
                    invalid += 1
        edges: list[RawCallEdge] = []
        raw_edges = payload.get("edges")
        if isinstance(raw_edges, list):
            for item in raw_edges:
                try:
                    edges.append(RawCallEdge.model_validate(item))
                except ValidationError:
                    invalid += 1
        root_node = None
        if payload.get("root_node") is not None:
            try:
                root_node = RawSymbol.model_validate(payload["root_node"])
            except ValidationError:
                invalid += 1
        root = payload.get("root")
        if root is None:
            if edges:
                raise ValueError("含调用边的响应缺少 root")
            # 引擎偶发只返回 diagnostic + 空集合；按“缺字段跳过”纪律视为空图。
            root = ""
            invalid += 1
        graph = cls(nodes=tuple(nodes), edges=tuple(edges), root=root, root_node=root_node)
        return graph, invalid
