"""确定性序列化：字节稳定性、往返一致与 golden fixture 回归。

规范 JSON 决策见 ADR-010：indent=2、字段声明顺序、Unicode 不转义、文件尾一个换行。
fixture 任何变化都必须有意为之；意外漂移会被本测试拦截。
"""

from pathlib import Path

from app.domain.codegraph import (
    CodeEdge,
    CodeGraph,
    CodeNode,
    EdgeKind,
    NodeKind,
    SourceSpan,
    build_edge_id,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "codegraph_v1.json"


def _canonical(graph: CodeGraph) -> str:
    """规范 JSON：indent=2、字段声明序、Unicode 不转义，文件尾一个换行。"""
    # 历史 v1 fixture 不补写 v2 默认字段；新产物固定输出完整 v2 形状。
    exclude_defaults = graph.schema_version == 1
    return graph.model_dump_json(indent=2, exclude_defaults=exclude_defaults) + "\n"


def _build_graph() -> CodeGraph:
    main_module = CodeNode(
        id="insightgraph:module:app.main",
        kind=NodeKind.MODULE,
        qualified_name="app.main",
        language="python",
        source=SourceSpan(file_path="app/main.py", line_start=1, line_end=40),
        content_hash="sha256:" + "aa" * 32,
    )
    service_class = CodeNode(
        id="insightgraph:class:app.main.Service",
        kind=NodeKind.CLASS,
        qualified_name="app.main.Service",
        language="python",
        source=SourceSpan(file_path="app/main.py", line_start=5, line_end=30),
        content_hash="sha256:" + "bb" * 32,
    )
    unicode_module = CodeNode(
        id="insightgraph:module:app.主逻辑",
        kind=NodeKind.MODULE,
        qualified_name="app.主逻辑",
        language="python",
        source=SourceSpan(file_path="app/主逻辑.py", line_start=1, line_end=12),
        content_hash="sha256:" + "cc" * 32,
    )
    run_first = CodeNode(
        id="insightgraph:function:app.主逻辑.run",
        kind=NodeKind.FUNCTION,
        qualified_name="app.主逻辑.run",
        language="python",
        source=SourceSpan(file_path="app/主逻辑.py", line_start=3, line_end=6),
        content_hash="sha256:" + "dd" * 32,
    )
    run_second = CodeNode(
        id="insightgraph:function:app.主逻辑.run#2",
        kind=NodeKind.FUNCTION,
        qualified_name="app.主逻辑.run",
        language="python",
        source=SourceSpan(file_path="app/主逻辑.py", line_start=9, line_end=12),
        content_hash="sha256:" + "ee" * 32,
    )
    repository_id = "insightgraph"
    edges = (
        CodeEdge(
            id=build_edge_id(EdgeKind.DEFINES, main_module.id, service_class.id),
            kind=EdgeKind.DEFINES,
            source_id=main_module.id,
            target_id=service_class.id,
        ),
        CodeEdge(
            id=build_edge_id(EdgeKind.DEFINES, unicode_module.id, run_first.id),
            kind=EdgeKind.DEFINES,
            source_id=unicode_module.id,
            target_id=run_first.id,
        ),
        CodeEdge(
            id=build_edge_id(EdgeKind.DEFINES, unicode_module.id, run_second.id),
            kind=EdgeKind.DEFINES,
            source_id=unicode_module.id,
            target_id=run_second.id,
        ),
        CodeEdge(
            id=build_edge_id(EdgeKind.IMPORTS, main_module.id, unicode_module.id),
            kind=EdgeKind.IMPORTS,
            source_id=main_module.id,
            target_id=unicode_module.id,
        ),
    )
    return CodeGraph(
        schema_version=1,
        repository_id=repository_id,
        revision="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        parser_version="python-ast/0.1",
        nodes=(main_module, service_class, unicode_module, run_first, run_second),
        edges=edges,
    )


def test_double_serialization_is_byte_identical() -> None:
    graph = _build_graph()

    assert _canonical(graph).encode("utf-8") == _canonical(graph).encode("utf-8")


def test_roundtrip_preserves_domain_objects() -> None:
    graph = _build_graph()

    restored = CodeGraph.model_validate_json(_canonical(graph))

    assert restored == graph


def test_golden_fixture_is_byte_stable() -> None:
    graph = _build_graph()

    assert _canonical(graph) == _FIXTURE.read_text(encoding="utf-8")
