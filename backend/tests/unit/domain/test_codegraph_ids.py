"""CodeGraph 稳定 ID 构造规则的纯函数测试。"""

import pytest

from app.domain.codegraph import EdgeKind, NodeKind, build_edge_id, build_node_id, node_id_matches


def test_node_id_is_readable_and_revision_free() -> None:
    assert build_node_id("insightgraph", NodeKind.MODULE, "app.main") == "insightgraph:module:app.main"


def test_duplicate_definitions_get_line_ordered_suffix() -> None:
    first = build_node_id("repo", NodeKind.FUNCTION, "app.main.foo")
    second = build_node_id("repo", NodeKind.FUNCTION, "app.main.foo", duplicate_index=2)
    third = build_node_id("repo", NodeKind.FUNCTION, "app.main.foo", duplicate_index=3)

    assert first == "repo:function:app.main.foo"
    assert second == f"{first}#2"
    assert third == f"{first}#3"


def test_duplicate_index_below_two_is_invalid() -> None:
    with pytest.raises(ValueError, match="duplicate_index"):
        build_node_id("repo", NodeKind.FUNCTION, "app.main.foo", duplicate_index=1)


def test_repository_id_rejects_separator_and_empty() -> None:
    with pytest.raises(ValueError, match=":"):
        build_node_id("bad:repo", NodeKind.MODULE, "app.main")
    with pytest.raises(ValueError, match="不能为空"):
        build_node_id("", NodeKind.MODULE, "app.main")


def test_empty_qualified_name_is_invalid() -> None:
    with pytest.raises(ValueError, match="qualified_name"):
        build_node_id("repo", NodeKind.MODULE, "")


def test_edge_id_format() -> None:
    edge_id = build_edge_id(EdgeKind.DEFINES, "repo:module:app.main", "repo:class:app.main.Foo")

    assert edge_id == "defines:repo:module:app.main->repo:class:app.main.Foo"


def test_edge_id_rejects_empty_endpoint() -> None:
    with pytest.raises(ValueError, match="不能为空"):
        build_edge_id(EdgeKind.IMPORTS, "repo:module:app.main", "")


def test_node_id_matches_accepts_bare_and_suffixed() -> None:
    assert node_id_matches("repo:function:app.main.foo", "repo", NodeKind.FUNCTION, "app.main.foo")
    assert node_id_matches("repo:function:app.main.foo#2", "repo", NodeKind.FUNCTION, "app.main.foo")


def test_node_id_matches_rejects_violations() -> None:
    assert not node_id_matches("repo:function:app.main.foo#1", "repo", NodeKind.FUNCTION, "app.main.foo")
    assert not node_id_matches("repo:class:app.main.foo", "repo", NodeKind.FUNCTION, "app.main.foo")
    assert not node_id_matches("other:function:app.main.foo", "repo", NodeKind.FUNCTION, "app.main.foo")
    assert not node_id_matches("repo:function:app.main.bar", "repo", NodeKind.FUNCTION, "app.main.foo")
