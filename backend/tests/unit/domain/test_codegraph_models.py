"""CodeGraph IR 的基础不变量测试。"""

import pytest
from pydantic import ValidationError

from app.domain.codegraph import CodeEdge, CodeGraph, CodeNode, EdgeKind, NodeKind, SourceSpan


def test_codegraph_keeps_source_evidence() -> None:
    node = CodeNode(
        id="repo@abc:module:app.main",
        kind=NodeKind.MODULE,
        qualified_name="app.main",
        language="python",
        source=SourceSpan(file_path="app/main.py", line_start=1, line_end=20),
        content_hash="sha256:example",
    )
    edge = CodeEdge(
        id="defines:root:module",
        kind=EdgeKind.DEFINES,
        source_id="repo@abc:repository:root",
        target_id=node.id,
    )

    graph = CodeGraph(
        repository_id="repo",
        revision="abc",
        parser_version="python-ast/0.1",
        nodes=(node,),
        edges=(edge,),
    )

    assert graph.nodes[0].source.file_path == "app/main.py"
    assert graph.edges[0].kind is EdgeKind.DEFINES


def test_source_span_rejects_reversed_lines() -> None:
    with pytest.raises(ValidationError, match="line_end"):
        SourceSpan(file_path="app/main.py", line_start=20, line_end=1)
