"""CodeGraph 领域模型与端口。"""

from app.domain.codegraph.ids import (
    build_edge_id,
    build_node_id,
    node_id_matches,
    validate_repository_id,
)
from app.domain.codegraph.kinds import EdgeKind, NodeKind
from app.domain.codegraph.models import CodeEdge, CodeGraph, CodeNode, SourceSpan
from app.domain.codegraph.ports import CodeGraphRepository

__all__ = [
    "CodeEdge",
    "CodeGraph",
    "CodeGraphRepository",
    "CodeNode",
    "EdgeKind",
    "NodeKind",
    "SourceSpan",
    "build_edge_id",
    "build_node_id",
    "node_id_matches",
    "validate_repository_id",
]
