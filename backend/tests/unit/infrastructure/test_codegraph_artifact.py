"""JsonCodeGraphRepository 的往返、确定性、原子写入与路径安全测试。

对齐步骤 6 完成门槛：保存再读取不改变领域对象；中断写入不会留下被误认为完整的 Artifact。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.application.scans.models import ScanRequest, ScanStatus
from app.application.scans.service import ScanRepository
from app.domain.codegraph.ids import build_edge_id, build_node_id
from app.domain.codegraph.kinds import EdgeKind, NodeKind
from app.domain.codegraph.models import CodeEdge, CodeGraph, CodeNode, SourceSpan
from app.infrastructure.analyzers import PythonAstAnalyzer
from app.infrastructure.collectors import GitRepositoryCollector
from app.infrastructure.persistence import (
    ArtifactRepositoryError,
    JsonCodeGraphRepository,
    artifact_digest,
    render_artifact,
)

_CONTENT_HASH = "sha256:" + "a" * 64


def _module_node(repository_id: str, name: str) -> CodeNode:
    return CodeNode(
        id=build_node_id(repository_id, NodeKind.MODULE, name),
        kind=NodeKind.MODULE,
        qualified_name=name,
        language="python",
        source=SourceSpan(file_path="app/main.py", line_start=1, line_end=8),
        content_hash=_CONTENT_HASH,
    )


def _function_node(repository_id: str, name: str, line: int) -> CodeNode:
    return CodeNode(
        id=build_node_id(repository_id, NodeKind.FUNCTION, name),
        kind=NodeKind.FUNCTION,
        qualified_name=name,
        language="python",
        source=SourceSpan(file_path="app/main.py", line_start=line, line_end=line),
        content_hash=_CONTENT_HASH,
    )


def _graph(repository_id: str = "demo", revision: str = "abc123") -> CodeGraph:
    """最小合法图：一个 Module DEFINES 一个 Function。"""
    module = _module_node(repository_id, "app.main")
    function = _function_node(repository_id, "app.main.run", 3)
    return CodeGraph(
        repository_id=repository_id,
        revision=revision,
        parser_version="test/0.1",
        nodes=(module, function),
        edges=(
            CodeEdge(
                id=build_edge_id(EdgeKind.DEFINES, module.id, function.id),
                kind=EdgeKind.DEFINES,
                source_id=module.id,
                target_id=function.id,
            ),
        ),
    )


# ---------------------------------------------------------------- 序列化


def test_render_artifact_is_byte_stable() -> None:
    """同一领域对象两次渲染必须字节相同（确定性前提）。"""
    graph = _graph()
    first = render_artifact(graph)
    second = render_artifact(graph)
    assert first == second


def test_render_artifact_matches_canonical_serialization() -> None:
    """Artifact 内容 = 项目既有规范序列化口径（indent=2 + 结尾换行）。"""
    graph = _graph()
    assert render_artifact(graph) == (graph.model_dump_json(indent=2) + "\n").encode()


def test_artifact_digest_uses_domain_hash_format() -> None:
    """内容哈希格式与领域层 content_hash 一致：sha256:<64 位小写十六进制>。"""
    digest = artifact_digest(b"payload")
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64
    assert digest == artifact_digest(b"payload")


# ---------------------------------------------------------------- 往返


@pytest.mark.asyncio
async def test_save_then_get_preserves_domain_object(tmp_path: Path) -> None:
    """完成门槛：保存再读取不改变领域对象。"""
    repository = JsonCodeGraphRepository(tmp_path)
    graph = _graph()

    await repository.save(graph)
    loaded = await repository.get(graph.repository_id, graph.revision)

    assert loaded == graph
    assert loaded is not None
    assert render_artifact(loaded) == render_artifact(graph)


@pytest.mark.asyncio
async def test_get_returns_none_when_absent(tmp_path: Path) -> None:
    """不存在的 Artifact 返回 None，不抛错。"""
    repository = JsonCodeGraphRepository(tmp_path)
    assert await repository.get("demo", "missing") is None


@pytest.mark.asyncio
async def test_layout_is_repository_directory_plus_revision_file(tmp_path: Path) -> None:
    """路径布局 = <root>/<repository_id>/<revision>.json，外加 .sha256 sidecar。"""
    repository = JsonCodeGraphRepository(tmp_path)
    graph = _graph()

    await repository.save(graph)

    artifact = tmp_path / "demo" / "abc123.json"
    assert artifact.is_file()
    assert (tmp_path / "demo" / "abc123.json.sha256").is_file()
    assert repository.artifact_path("demo", "abc123") == artifact


@pytest.mark.asyncio
async def test_artifact_is_loadable_by_plain_json(tmp_path: Path) -> None:
    """产物是纯 CodeGraph JSON，可被既有 validate.py 一类工具直接读取。"""
    repository = JsonCodeGraphRepository(tmp_path)
    graph = _graph()

    await repository.save(graph)
    payload = json.loads((tmp_path / "demo" / "abc123.json").read_text(encoding="utf-8"))

    assert payload["repository_id"] == "demo"
    assert payload["revision"] == "abc123"
    assert len(payload["nodes"]) == 2


# ---------------------------------------------------------------- 完整性与原子性


@pytest.mark.asyncio
async def test_tampered_artifact_is_rejected(tmp_path: Path) -> None:
    """哈希 sidecar 不匹配时拒绝返回损坏的图。"""
    repository = JsonCodeGraphRepository(tmp_path)
    graph = _graph()
    await repository.save(graph)

    artifact = tmp_path / "demo" / "abc123.json"
    artifact.write_text(artifact.read_text(encoding="utf-8").replace("abc123", "tampered"), encoding="utf-8")

    with pytest.raises(ArtifactRepositoryError, match="哈希不匹配"):
        await repository.get(graph.repository_id, graph.revision)


@pytest.mark.asyncio
async def test_corrupted_artifact_without_sidecar_is_rejected(tmp_path: Path) -> None:
    """sidecar 缺失时跳过哈希校验，但内容无法解析仍必须拒绝。"""
    repository = JsonCodeGraphRepository(tmp_path)
    graph = _graph()
    await repository.save(graph)

    (tmp_path / "demo" / "abc123.json").write_text("{ not json", encoding="utf-8")
    (tmp_path / "demo" / "abc123.json.sha256").unlink()

    with pytest.raises(ArtifactRepositoryError, match="无法解析"):
        await repository.get(graph.repository_id, graph.revision)


@pytest.mark.asyncio
async def test_missing_sidecar_skips_verification_only(tmp_path: Path) -> None:
    """只拷贝 .json 而不带 sidecar 时仍可读取（校验被跳过，不是失败）。"""
    repository = JsonCodeGraphRepository(tmp_path)
    graph = _graph()
    await repository.save(graph)

    (tmp_path / "demo" / "abc123.json.sha256").unlink()

    assert await repository.get(graph.repository_id, graph.revision) == graph


@pytest.mark.asyncio
async def test_leftover_temp_file_is_not_mistaken_for_artifact(tmp_path: Path) -> None:
    """完成门槛：中断写入只留临时文件，不能被误认为完整 Artifact。"""
    repository = JsonCodeGraphRepository(tmp_path)
    artifact = repository.artifact_path("demo", "abc123")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    (artifact.parent / (artifact.name + ".tmp")).write_bytes(b'{"partial": true}')

    assert await repository.get("demo", "abc123") is None


@pytest.mark.asyncio
async def test_save_leaves_no_temp_file(tmp_path: Path) -> None:
    """正常写入完成后目录里不应残留临时文件。"""
    repository = JsonCodeGraphRepository(tmp_path)
    await repository.save(_graph())

    leftovers = [path.name for path in (tmp_path / "demo").iterdir() if path.name.endswith(".tmp")]
    assert leftovers == []


@pytest.mark.asyncio
async def test_save_overwrites_same_key_completely(tmp_path: Path) -> None:
    """同键重复写入按后写覆盖，且覆盖后内容与哈希一致（冲突策略见数据模型 §5.1）。"""
    repository = JsonCodeGraphRepository(tmp_path)
    await repository.save(_graph(revision="abc123"))
    replaced = _graph(revision="abc123")
    replaced = replaced.model_copy(update={"parser_version": "test/0.2"})

    await repository.save(replaced)
    loaded = await repository.get("demo", "abc123")

    assert loaded is not None
    assert loaded.parser_version == "test/0.2"


# ---------------------------------------------------------------- 路径安全


def test_repository_id_with_separator_is_rejected(tmp_path: Path) -> None:
    """ADR-010：repository_id 不得含 ":"。"""
    repository = JsonCodeGraphRepository(tmp_path)
    with pytest.raises(ArtifactRepositoryError, match="repository_id"):
        repository.artifact_path("bad:id", "abc123")


@pytest.mark.parametrize("bad_value", ["../escape", "a/b", "a\\b", "..", "."])
def test_path_traversal_is_rejected(tmp_path: Path, bad_value: str) -> None:
    """越界取值必须被拒绝，不能写出 artifact 根目录。"""
    repository = JsonCodeGraphRepository(tmp_path)
    with pytest.raises(ArtifactRepositoryError):
        repository.artifact_path("demo", bad_value)


@pytest.mark.asyncio
async def test_rejects_traversal_through_save(tmp_path: Path) -> None:
    """save 路径同样受保护（不能借 graph.revision 越界）。"""
    repository = JsonCodeGraphRepository(tmp_path)
    with pytest.raises(ArtifactRepositoryError):
        await repository.save(_graph(revision="../escape"))


# ---------------------------------------------------------------- 与端口的契合


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _git_init(repo: Path) -> None:
    """把目录变成真实 Git 仓库——Collector 对非 Git 目录是 fatal 失败。"""
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init", "--no-gpg-sign")


@pytest.mark.asyncio
async def test_plugs_into_scan_service(tmp_path: Path) -> None:
    """适配器可直接注入 ScanRepository，完成一次真实扫描与落盘。"""
    source_root = tmp_path / "source"
    (source_root / "app").mkdir(parents=True)
    (source_root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (source_root / "app" / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    _git_init(source_root)

    repository = JsonCodeGraphRepository(tmp_path / "artifacts")
    service = ScanRepository(GitRepositoryCollector(), PythonAstAnalyzer(), repository)

    result = await service.execute(ScanRequest(repository_id="demo", path=source_root))

    assert result.status is ScanStatus.COMPLETED
    assert result.revision is not None
    stored = await repository.get("demo", result.revision)
    assert stored == result.graph
