"""本地真实 CodeGraphAI 二进制的手动集成验证；常驻 CI 默认排除。"""

import hashlib
import os
from pathlib import Path

import pytest

from app.application.scans.models import ScanRequest, SourceFile, SourceManifest
from app.infrastructure.analyzers import PythonAstAnalyzer
from app.infrastructure.code_intelligence.providers import CodeGraphAIProvider


def _fixture_manifest(root: Path) -> SourceManifest:
    files: list[SourceFile] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        normalized = path.read_bytes().replace(b"\r\n", b"\n")
        files.append(
            SourceFile(
                path=relative,
                content_hash=f"sha256:{hashlib.sha256(normalized).hexdigest()}",
            )
        )
    return SourceManifest(
        repository_id="golden-python-calls",
        revision="fixture-v1",
        files=tuple(files),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_engine_merge_is_golden_idempotent() -> None:
    executable_text = os.environ.get("CODEGRAPH_ENGINE_PATH", "")
    if not executable_text:
        pytest.skip("未设置 CODEGRAPH_ENGINE_PATH")
    executable = Path(executable_text)
    if not executable.is_file():
        pytest.skip(f"CodeGraphAI 二进制不存在: {executable}")
    repo_root = Path(__file__).resolve().parents[3]
    fixture_root = repo_root / "eval" / "codegraph" / "cases" / "golden-python-calls" / "repo"
    manifest = _fixture_manifest(fixture_root)
    request = ScanRequest(repository_id=manifest.repository_id, path=fixture_root)

    scanner = await PythonAstAnalyzer().analyze(request, manifest)
    enriched = await PythonAstAnalyzer(CodeGraphAIProvider(executable)).analyze(request, manifest)

    assert scanner.graph is not None
    assert enriched.graph is not None
    assert enriched.graph.nodes == scanner.graph.nodes
    assert enriched.graph.edges == scanner.graph.edges
    assert enriched.graph.entries == scanner.graph.entries
    assert enriched.graph.provenance
    assert enriched.graph.provenance[0].name == "codegraph-ai/CodeGraph"
