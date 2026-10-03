"""CodeGraph IR 的基础不变量测试。"""

import pytest
from pydantic import ValidationError

from app.domain.codegraph import CodeEdge, CodeGraph, CodeNode, EdgeKind, NodeKind, SourceSpan

_SHA = "sha256:" + "0" * 64


def _node(node_id: str, kind: NodeKind, qualified_name: str) -> CodeNode:
    return CodeNode(
        id=node_id,
        kind=kind,
        qualified_name=qualified_name,
        language="python",
        source=SourceSpan(file_path="app/main.py", line_start=1, line_end=20),
        content_hash=_SHA,
    )


def _graph(
    nodes: tuple[CodeNode, ...] = (),
    edges: tuple[CodeEdge, ...] = (),
) -> CodeGraph:
    return CodeGraph(
        repository_id="repo",
        revision="abc",
        parser_version="python-ast/0.1",
        nodes=nodes,
        edges=edges,
    )


def test_codegraph_keeps_source_evidence_and_defaults() -> None:
    module = _node("repo:module:app.main", NodeKind.MODULE, "app.main")
    cls = _node("repo:class:app.main.Foo", NodeKind.CLASS, "app.main.Foo")
    edge = CodeEdge(
        id="defines:repo:module:app.main->repo:class:app.main.Foo",
        kind=EdgeKind.DEFINES,
        source_id=module.id,
        target_id=cls.id,
    )

    graph = _graph(nodes=(module, cls), edges=(edge,))

    assert graph.nodes[0].source.file_path == "app/main.py"
    assert graph.edges[0].kind is EdgeKind.DEFINES
    assert graph.schema_version == 1


def test_source_span_rejects_reversed_lines() -> None:
    with pytest.raises(ValidationError, match="line_end"):
        SourceSpan(file_path="app/main.py", line_start=20, line_end=1)


def test_unknown_fields_are_rejected() -> None:
    payload = {
        "id": "repo:module:app.main",
        "kind": "module",
        "qualified_name": "app.main",
        "language": "python",
        "source": {"file_path": "app/main.py", "line_start": 1, "line_end": 2},
        "content_hash": _SHA,
        "unexpected": "字段",
    }

    with pytest.raises(ValidationError, match="Extra inputs"):
        CodeNode.model_validate(payload)


def test_content_hash_requires_sha256_format() -> None:
    with pytest.raises(ValidationError):
        CodeNode(
            id="repo:module:app.main",
            kind=NodeKind.MODULE,
            qualified_name="app.main",
            language="python",
            source=SourceSpan(file_path="app/main.py", line_start=1, line_end=2),
            content_hash="sha256:example",
        )


def test_node_id_must_follow_construction_rule() -> None:
    with pytest.raises(ValidationError, match="节点 ID"):
        _graph(nodes=(_node("repo:repository:root", NodeKind.MODULE, "app.main"),))


def test_duplicate_node_ids_are_rejected() -> None:
    module = _node("repo:module:app.main", NodeKind.MODULE, "app.main")

    with pytest.raises(ValidationError, match="重复"):
        _graph(nodes=(module, module))


def test_duplicate_edges_are_rejected() -> None:
    module = _node("repo:module:app.main", NodeKind.MODULE, "app.main")
    cls = _node("repo:class:app.main.Foo", NodeKind.CLASS, "app.main.Foo")
    edge = CodeEdge(
        id="defines:repo:module:app.main->repo:class:app.main.Foo",
        kind=EdgeKind.DEFINES,
        source_id=module.id,
        target_id=cls.id,
    )

    with pytest.raises(ValidationError, match="边 ID 重复"):
        _graph(nodes=(module, cls), edges=(edge, edge))


def test_edge_id_must_follow_construction_rule() -> None:
    module = _node("repo:module:app.main", NodeKind.MODULE, "app.main")
    cls = _node("repo:class:app.main.Foo", NodeKind.CLASS, "app.main.Foo")
    broken_edge = CodeEdge(id="wrong-id", kind=EdgeKind.DEFINES, source_id=module.id, target_id=cls.id)

    with pytest.raises(ValidationError, match="边 ID"):
        _graph(nodes=(module, cls), edges=(broken_edge,))


def test_edge_must_reference_existing_nodes() -> None:
    module = _node("repo:module:app.main", NodeKind.MODULE, "app.main")
    dangling_edge = CodeEdge(
        id="imports:repo:module:app.main->repo:module:app.util",
        kind=EdgeKind.IMPORTS,
        source_id=module.id,
        target_id="repo:module:app.util",
    )

    with pytest.raises(ValidationError, match="不存在"):
        _graph(nodes=(module,), edges=(dangling_edge,))


def test_repository_id_rejects_separator() -> None:
    with pytest.raises(ValidationError, match=":"):
        CodeGraph(repository_id="bad:repo", revision="abc", parser_version="python-ast/0.1")
