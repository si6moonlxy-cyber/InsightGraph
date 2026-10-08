"""PythonAstAnalyzer 的节点 / 边 / 确定性与错误隔离测试。"""

import hashlib
from pathlib import Path

import pytest

from app.application.scans.models import (
    AnalyzeOutcome,
    ScanErrorCode,
    ScanErrorSeverity,
    ScanRequest,
    ScanStage,
    SourceFile,
    SourceManifest,
)
from app.domain.codegraph.kinds import CallResolution, EdgeKind, EntryKind, NodeKind
from app.domain.codegraph.models import CodeNode
from app.infrastructure.analyzers import PythonAstAnalyzer

_WIDGETS_SAMPLE = """\
def outer():
    def inner():
        pass
    return inner


class Widget:
    class Kind:
        pass

    def render(self):
        pass
"""


def _write_files(root: Path, files: dict[str, str | bytes]) -> None:
    for relative, content in files.items():
        file_path = root / relative
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            file_path.write_bytes(content)
        else:
            file_path.write_text(content, encoding="utf-8", newline="")


def _files_from(root: Path) -> tuple[SourceFile, ...]:
    entries: list[tuple[str, str]] = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        normalized = path.read_bytes().replace(b"\r\n", b"\n")
        entries.append((relative, f"sha256:{hashlib.sha256(normalized).hexdigest()}"))
    entries.sort(key=lambda item: item[0])
    return tuple(SourceFile(path=relative, content_hash=content_hash) for relative, content_hash in entries)


def _make(root: Path, files: dict[str, str | bytes]) -> SourceManifest:
    root.mkdir(parents=True, exist_ok=True)
    _write_files(root, files)
    return SourceManifest(repository_id="repo", revision="rev1", worktree_dirty=False, files=_files_from(root))


async def _analyze(root: Path, manifest: SourceManifest) -> AnalyzeOutcome:
    request = ScanRequest(repository_id=manifest.repository_id, path=root)
    return await PythonAstAnalyzer().analyze(request, manifest)


def _nodes_by_qualname(outcome: AnalyzeOutcome) -> dict[str, CodeNode]:
    assert outcome.graph is not None
    return {node.qualified_name: node for node in outcome.graph.nodes}


def _edge_triples(outcome: AnalyzeOutcome) -> set[tuple[str, str, str]]:
    """把边投影为（kind, 源限定名, 目标限定名），便于断言。"""
    assert outcome.graph is not None
    qualnames = {node.id: node.qualified_name for node in outcome.graph.nodes}
    return {(edge.kind.value, qualnames[edge.source_id], qualnames[edge.target_id]) for edge in outcome.graph.edges}


@pytest.mark.asyncio
async def test_module_nodes_and_init_mapping(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _make(root, {"app/__init__.py": '"""pkg."""\n', "app/main.py": "x = 1\n", "app/empty.py": ""})

    outcome = await _analyze(root, manifest)

    graph = outcome.graph
    assert graph is not None
    modules = {node.qualified_name: node for node in graph.nodes if node.kind is NodeKind.MODULE}
    assert set(modules) == {"app", "app.main", "app.empty"}
    assert modules["app"].source.file_path == "app/__init__.py"
    assert (modules["app.main"].source.line_start, modules["app.main"].source.line_end) == (1, 1)
    assert modules["app.main"].content_hash == "sha256:" + hashlib.sha256(b"x = 1\n").hexdigest()
    empty = modules["app.empty"]
    assert (empty.source.line_start, empty.source.line_end) == (1, 1)
    assert empty.content_hash == "sha256:" + hashlib.sha256(b"").hexdigest()


@pytest.mark.asyncio
async def test_qualname_semantics(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _make(root, {"app/widgets.py": _WIDGETS_SAMPLE})

    outcome = await _analyze(root, manifest)

    qualnames = set(_nodes_by_qualname(outcome))
    assert {
        "app.widgets.outer",
        "app.widgets.outer.<locals>.inner",
        "app.widgets.Widget",
        "app.widgets.Widget.Kind",
        "app.widgets.Widget.render",
    } <= qualnames


@pytest.mark.asyncio
async def test_decorated_span_and_content_hash(tmp_path: Path) -> None:
    source = "import functools\n\n\ndef deco(f):\n    return f\n\n\n@deco\n@deco\ndef target():\n    return 1\n"
    root = tmp_path / "repo"
    manifest = _make(root, {"app/m.py": source})

    outcome = await _analyze(root, manifest)

    nodes = _nodes_by_qualname(outcome)
    target = nodes["app.m.target"]
    assert target.source.line_start == 8  # 最早装饰器行
    assert target.source.line_end == 11
    span_text = "@deco\n@deco\ndef target():\n    return 1\n"
    assert target.content_hash == "sha256:" + hashlib.sha256(span_text.encode("utf-8")).hexdigest()
    assert nodes["app.m.deco"].source.line_start == 4


@pytest.mark.asyncio
async def test_defines_edges(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _make(root, {"app/widgets.py": _WIDGETS_SAMPLE})

    outcome = await _analyze(root, manifest)

    assert _edge_triples(outcome) == {
        ("defines", "app.widgets", "app.widgets.outer"),
        ("defines", "app.widgets", "app.widgets.Widget"),
        ("defines", "app.widgets.outer", "app.widgets.outer.<locals>.inner"),
        ("defines", "app.widgets.Widget", "app.widgets.Widget.Kind"),
        ("defines", "app.widgets.Widget", "app.widgets.Widget.render"),
    }


@pytest.mark.asyncio
async def test_conditional_definitions_get_ordinal_ids(tmp_path: Path) -> None:
    source = "if True:\n    def repeat():\n        return 1\n\n\ndef repeat():\n    return 2\n"
    root = tmp_path / "repo"
    manifest = _make(root, {"app/m.py": source})

    outcome = await _analyze(root, manifest)

    assert outcome.graph is not None
    by_id = {node.id: node for node in outcome.graph.nodes}
    assert "repo:function:app.m.repeat" in by_id
    assert "repo:function:app.m.repeat#2" in by_id
    assert by_id["repo:function:app.m.repeat"].source.line_start == 2
    assert by_id["repo:function:app.m.repeat#2"].source.line_start == 6


@pytest.mark.asyncio
async def test_import_exact_submodule_and_stdlib(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _make(
        root,
        {
            "app/__init__.py": "",
            "app/service.py": "def work():\n    return 1\n",
            "app/main.py": "import os\nfrom app import service\nfrom app.service import work\n",
        },
    )

    outcome = await _analyze(root, manifest)

    assert _edge_triples(outcome) == {
        ("defines", "app.service", "app.service.work"),
        ("imports", "app.main", "app"),
        ("imports", "app.main", "app.service"),
    }


@pytest.mark.asyncio
async def test_suffix_resolution_unique_and_ambiguous(tmp_path: Path) -> None:
    unique_root = tmp_path / "unique"
    unique_manifest = _make(
        unique_root,
        {
            "lib/__init__.py": "",
            "lib/pkg/__init__.py": "",
            "lib/pkg/mod.py": "def thing():\n    return 1\n",
            "app/__init__.py": "",
            "app/use.py": "from pkg.mod import thing\n",
        },
    )
    unique_outcome = await _analyze(unique_root, unique_manifest)
    assert ("imports", "app.use", "lib.pkg.mod") in _edge_triples(unique_outcome)

    ambiguous_root = tmp_path / "ambiguous"
    ambiguous_manifest = _make(
        ambiguous_root,
        {
            "lib/__init__.py": "",
            "lib/pkg/__init__.py": "",
            "lib/pkg/mod.py": "",
            "other/__init__.py": "",
            "other/pkg/__init__.py": "",
            "other/pkg/mod.py": "",
            "app/__init__.py": "",
            "app/use.py": "from pkg.mod import thing\n",
        },
    )
    ambiguous_outcome = await _analyze(ambiguous_root, ambiguous_manifest)
    assert not [edge for edge in _edge_triples(ambiguous_outcome) if edge[0] == "imports"]


@pytest.mark.asyncio
async def test_relative_imports(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _make(
        root,
        {
            "app/__init__.py": "",
            "app/utils/__init__.py": "from . import text_utils\n",
            "app/utils/text_utils.py": "def clean(value):\n    return value.strip()\n",
            "app/utils/helpers.py": "from .text_utils import clean\n",
            "app/deep/__init__.py": "",
            "app/deep/leaf.py": "from .. import utils\n",
        },
    )

    outcome = await _analyze(root, manifest)

    assert _edge_triples(outcome) == {
        ("defines", "app.utils.text_utils", "app.utils.text_utils.clean"),
        ("imports", "app.utils", "app.utils.text_utils"),
        ("imports", "app.utils.helpers", "app.utils.text_utils"),
        ("imports", "app.deep.leaf", "app"),
        ("imports", "app.deep.leaf", "app.utils"),
    }


@pytest.mark.asyncio
async def test_syntax_error_is_isolated(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _make(root, {"app/good.py": "def ok():\n    return 1\n", "app/bad.py": "def broken(:\n"})

    outcome = await _analyze(root, manifest)

    assert outcome.graph is not None
    qualnames = set(_nodes_by_qualname(outcome))
    assert "app.good.ok" in qualnames
    assert "app.bad" not in qualnames
    assert [(error.code, error.file_path, error.stage) for error in outcome.errors] == [
        (ScanErrorCode.SYNTAX_ERROR, "app/bad.py", ScanStage.ANALYZE)
    ]


@pytest.mark.asyncio
async def test_missing_and_encoding_errors(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _make(root, {"app/ok.py": "x = 1\n", "app/bad_encoding.py": b"\xff\xfe\x00"})
    (root / "app" / "ok.py").unlink()

    outcome = await _analyze(root, manifest)

    assert outcome.graph is not None
    assert {(error.code, error.file_path) for error in outcome.errors} == {
        (ScanErrorCode.FILE_DISAPPEARED, "app/ok.py"),
        (ScanErrorCode.FILE_ENCODING, "app/bad_encoding.py"),
    }


@pytest.mark.asyncio
async def test_non_python_manifest_entries_are_skipped(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _make(root, {"app/ok.py": "x = 1\n"})
    extra = SourceFile(path="app/notes.md", content_hash="sha256:" + "ab" * 32)
    manifest = SourceManifest(
        repository_id=manifest.repository_id,
        revision=manifest.revision,
        files=manifest.files + (extra,),
    )

    outcome = await _analyze(root, manifest)

    assert outcome.errors == ()
    assert set(_nodes_by_qualname(outcome)) == {"app.ok"}


@pytest.mark.asyncio
async def test_double_run_is_byte_identical_and_sorted(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _make(
        root,
        {
            "app/__init__.py": "",
            "app/service.py": "def work():\n    return 1\n",
            "app/main.py": "from app.service import work\n",
        },
    )

    first = await _analyze(root, manifest)
    second = await _analyze(root, manifest)

    assert first.graph is not None
    assert second.graph is not None
    assert first.graph.model_dump_json(indent=2) == second.graph.model_dump_json(indent=2)
    node_ids = [node.id for node in first.graph.nodes]
    edge_ids = [edge.id for edge in first.graph.edges]
    assert node_ids == sorted(node_ids)
    assert edge_ids == sorted(edge_ids)


@pytest.mark.asyncio
async def test_calls_entries_and_funnel_are_emitted(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _make(
        root,
        {
            "app/main.py": (
                "def target():\n    return 1\n\n"
                "def run(callback):\n    target()\n    callback()\n\n"
                "if __name__ == '__main__':\n    run(target)\n"
            )
        },
    )

    outcome = await _analyze(root, manifest)

    assert outcome.graph is not None
    calls = [edge for edge in outcome.graph.edges if edge.kind is EdgeKind.CALLS]
    assert {(edge.source_id, edge.target_id, edge.resolution) for edge in calls} == {
        ("repo:function:app.main.run", "repo:function:app.main.target", CallResolution.RESOLVED),
        ("repo:module:app.main", "repo:function:app.main.run", CallResolution.RESOLVED),
    }
    assert outcome.call_funnel is not None
    assert outcome.call_funnel.calls_dynamic == 1
    assert outcome.graph.entries[0].kind is EntryKind.MAIN_GUARD
    assert outcome.graph.entries[0].target_node_id == "repo:function:app.main.run"


@pytest.mark.asyncio
async def test_ambiguous_calls_are_bounded_and_reported(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    definitions = "\n".join(f"def choose():\n    return {index}\n" for index in range(6))
    manifest = _make(root, {"app/m.py": definitions + "\ndef use():\n    return choose()\n"})

    outcome = await _analyze(root, manifest)

    assert outcome.graph is not None
    calls = [edge for edge in outcome.graph.edges if edge.kind is EdgeKind.CALLS]
    assert len(calls) == 5
    assert all(edge.resolution is CallResolution.AMBIGUOUS for edge in calls)
    assert all(edge.is_truncated for edge in calls)
    assert outcome.call_funnel is not None
    assert outcome.call_funnel.oversized_ambiguous_calls == 1


@pytest.mark.asyncio
async def test_duplicate_calls_keep_earliest_representative_span(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _make(
        root,
        {"app/m.py": "def target():\n    return 1\n\ndef use():\n    target()\n    target()\n"},
    )

    outcome = await _analyze(root, manifest)

    assert outcome.graph is not None
    calls = [edge for edge in outcome.graph.edges if edge.kind is EdgeKind.CALLS]
    assert len(calls) == 1
    assert calls[0].source_span is not None
    assert calls[0].source_span.line_start == 5


@pytest.mark.asyncio
async def test_missing_root_is_fatal(tmp_path: Path) -> None:
    manifest = SourceManifest(repository_id="repo", revision="rev1")

    outcome = await _analyze(tmp_path / "missing", manifest)

    assert outcome.graph is None
    assert outcome.errors[0].code is ScanErrorCode.PATH_INVALID
    assert outcome.errors[0].severity is ScanErrorSeverity.FATAL
