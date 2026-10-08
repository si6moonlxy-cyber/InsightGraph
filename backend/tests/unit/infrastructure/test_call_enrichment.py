"""M2 Provider + Adapter + merge/provenance + 降级路径测试。"""

import hashlib
from pathlib import Path

import pytest

from app.application.scans.models import AnalyzeOutcome, ScanRequest, SourceFile, SourceManifest
from app.domain.codegraph.kinds import EdgeKind
from app.infrastructure.analyzers import PythonAstAnalyzer
from app.infrastructure.code_intelligence.models import ProviderStatus
from app.infrastructure.code_intelligence.providers.engine_port import ProviderCallResult
from app.infrastructure.code_intelligence.raw_models.relation import RawCallEdge, RawCallGraph
from app.infrastructure.code_intelligence.raw_models.symbol import RawSymbol


class _FakeProvider:
    name = "fake/codegraph"

    def __init__(self, *, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.calls: list[tuple[str, int]] = []

    def probe(self, root: Path) -> ProviderStatus:
        if self.unavailable:
            return ProviderStatus.unavailable("测试不可用")
        return ProviderStatus(
            available=True,
            version="fake-v1",
            asset_hash="sha256:" + "ab" * 32,
        )

    def calls_for_symbol(self, root: Path, file_rel: str, line_1based: int) -> ProviderCallResult:
        self.calls.append((file_rel, line_1based))
        root_id = str(line_1based)
        edges: tuple[RawCallEdge, ...] = ()
        nodes: tuple[RawSymbol, ...] = ()
        if line_1based == 4:
            nodes = (
                RawSymbol(
                    id="target",
                    name="target",
                    path=str(root / "app/m.py"),
                    line_start=1,
                    line_end=2,
                ),
            )
            edges = (RawCallEdge.model_validate({"from": root_id, "to": "target", "type": "calls"}),)
        return ProviderCallResult(RawCallGraph(nodes=nodes, edges=edges, root=root_id))


class _FailingProvider(_FakeProvider):
    def calls_for_symbol(self, root: Path, file_rel: str, line_1based: int) -> ProviderCallResult:
        return ProviderCallResult(error="测试超时")


class _AmbiguousProvider(_FakeProvider):
    def calls_for_symbol(self, root: Path, file_rel: str, line_1based: int) -> ProviderCallResult:
        root_id = str(line_1based)
        if line_1based != 7:
            return ProviderCallResult(RawCallGraph(root=root_id))
        target = RawSymbol(
            id="choose-2",
            name="choose",
            path=str(root / "app/m.py"),
            line_start=4,
            line_end=5,
        )
        edge = RawCallEdge.model_validate({"from": root_id, "to": target.id, "type": "calls"})
        return ProviderCallResult(RawCallGraph(nodes=(target,), edges=(edge,), root=root_id))


def _manifest(root: Path, source: str) -> SourceManifest:
    path = root / "app" / "m.py"
    path.parent.mkdir(parents=True)
    path.write_text(source, encoding="utf-8", newline="")
    digest = hashlib.sha256(source.encode()).hexdigest()
    return SourceManifest(
        repository_id="repo",
        revision="rev",
        files=(SourceFile(path="app/m.py", content_hash=f"sha256:{digest}"),),
    )


async def _analyze(
    root: Path,
    manifest: SourceManifest,
    provider: _FakeProvider | None,
    *,
    total_budget_seconds: int = 900,
) -> AnalyzeOutcome:
    return await PythonAstAnalyzer(
        provider,
        call_graph_total_budget_seconds=total_budget_seconds,
    ).analyze(ScanRequest(repository_id="repo", path=root), manifest)


@pytest.mark.asyncio
async def test_engine_merge_is_idempotent_and_writes_provenance(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _manifest(root, "def target():\n    return 1\n\ndef use():\n    return target()\n")
    provider = _FakeProvider()

    scanner = await _analyze(root, manifest, None)
    enriched = await _analyze(root, manifest, provider)

    assert scanner.graph is not None
    assert enriched.graph is not None
    assert enriched.graph.edges == scanner.graph.edges
    assert enriched.graph.provenance[0].name == "fake/codegraph"
    assert enriched.graph.provenance[0].version == "fake-v1"
    assert enriched.graph.provenance[0].tools_used == ("codegraph_get_call_graph",)
    assert provider.calls == [("app/m.py", 1), ("app/m.py", 4)]


@pytest.mark.asyncio
async def test_engine_only_edge_without_call_site_evidence_is_not_materialized(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _manifest(
        root,
        "def target():\n    return 1\n\ndef use(callback):\n    return callback()\n",
    )

    outcome = await _analyze(root, manifest, _FakeProvider())

    assert outcome.graph is not None
    assert not [edge for edge in outcome.graph.edges if edge.kind is EdgeKind.CALLS]
    assert outcome.graph.provenance


@pytest.mark.asyncio
async def test_engine_cannot_upgrade_one_candidate_in_ambiguous_cohort(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _manifest(
        root,
        "def choose():\n    return 1\n\ndef choose():\n    return 2\n\ndef use():\n    return choose()\n",
    )

    scanner = await _analyze(root, manifest, None)
    enriched = await _analyze(root, manifest, _AmbiguousProvider())

    assert scanner.graph is not None
    assert enriched.graph is not None
    assert enriched.graph.edges == scanner.graph.edges


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [_FakeProvider(unavailable=True), _FailingProvider()])
async def test_unavailable_or_failed_engine_degrades_to_scanner_only(tmp_path: Path, provider: _FakeProvider) -> None:
    root = tmp_path / "repo"
    manifest = _manifest(root, "def target():\n    return 1\n\ndef use():\n    return target()\n")

    scanner = await _analyze(root, manifest, None)
    degraded = await _analyze(root, manifest, provider)

    assert scanner.graph is not None
    assert degraded.graph is not None
    assert degraded.graph.edges == scanner.graph.edges
    assert degraded.graph.provenance == ()


@pytest.mark.asyncio
async def test_total_budget_breaker_discards_partial_engine_result(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    manifest = _manifest(root, "def target():\n    return 1\n\ndef use():\n    return target()\n")
    provider = _FakeProvider()

    scanner = await _analyze(root, manifest, None)
    degraded = await _analyze(root, manifest, provider, total_budget_seconds=0)

    assert scanner.graph is not None
    assert degraded.graph is not None
    assert degraded.graph.edges == scanner.graph.edges
    assert degraded.graph.provenance == ()
    assert provider.calls == []
