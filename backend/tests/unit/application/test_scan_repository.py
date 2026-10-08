"""扫描应用服务只负责编排端口。"""

from pathlib import Path

import pytest

from app.application.scans.models import (
    AnalyzeOutcome,
    CallFunnel,
    CollectOutcome,
    ScanError,
    ScanErrorCode,
    ScanErrorSeverity,
    ScanRequest,
    ScanResult,
    ScanStage,
    ScanStats,
    ScanStatus,
    SourceFile,
    SourceManifest,
)
from app.application.scans.service import ScanRepository
from app.domain.codegraph.models import CodeGraph

_SHA = "sha256:" + "2" * 64


def _manifest(files: int = 2) -> SourceManifest:
    return SourceManifest(
        repository_id="demo",
        revision="abc123",
        files=tuple(SourceFile(path=f"app/mod_{index}.py", content_hash=_SHA) for index in range(files)),
    )


def _graph() -> CodeGraph:
    return CodeGraph(repository_id="demo", revision="abc123", parser_version="fake/1")


def _local_syntax_error() -> ScanError:
    return ScanError(
        stage=ScanStage.ANALYZE,
        code=ScanErrorCode.SYNTAX_ERROR,
        severity=ScanErrorSeverity.LOCAL,
        message="语法错误",
        file_path="app/mod_1.py",
    )


class FakeCollector:
    def __init__(self, outcome: CollectOutcome) -> None:
        self._outcome = outcome

    async def collect(self, request: ScanRequest) -> CollectOutcome:
        return self._outcome


class FakeAnalyzer:
    def __init__(self, outcome: AnalyzeOutcome) -> None:
        self._outcome = outcome

    async def analyze(self, request: ScanRequest, manifest: SourceManifest) -> AnalyzeOutcome:
        return self._outcome


class ExplodingAnalyzer:
    async def analyze(self, request: ScanRequest, manifest: SourceManifest) -> AnalyzeOutcome:
        raise AssertionError("整体失败时不应继续调用分析")


class InMemoryCodeGraphRepository:
    def __init__(self) -> None:
        self.graph: CodeGraph | None = None
        self.save_calls = 0

    async def save(self, graph: CodeGraph) -> None:
        self.save_calls += 1
        self.graph = graph

    async def get(self, repository_id: str, revision: str) -> CodeGraph | None:
        if self.graph is None:
            return None
        if self.graph.repository_id == repository_id and self.graph.revision == revision:
            return self.graph
        return None


class FailingRepository:
    async def save(self, graph: CodeGraph) -> None:
        raise OSError("disk full")

    async def get(self, repository_id: str, revision: str) -> CodeGraph | None:
        return None


def _request() -> ScanRequest:
    return ScanRequest(repository_id="demo", path=Path("fixtures/demo"))


@pytest.mark.asyncio
async def test_completed_scan_returns_graph_and_saves() -> None:
    repository = InMemoryCodeGraphRepository()
    graph = _graph()
    service = ScanRepository(
        FakeCollector(CollectOutcome(manifest=_manifest())),
        FakeAnalyzer(AnalyzeOutcome(graph=graph)),
        repository,
    )

    result = await service.execute(_request())

    assert result.status is ScanStatus.COMPLETED
    assert result.graph == graph
    assert result.errors == ()
    assert result.stats == ScanStats(files_collected=2, files_analyzed=2, files_failed=0)
    assert repository.graph == graph
    assert repository.save_calls == 1


@pytest.mark.asyncio
async def test_collector_fatal_failure_skips_analysis_and_save() -> None:
    repository = InMemoryCodeGraphRepository()
    fatal = ScanError(
        stage=ScanStage.COLLECT,
        code=ScanErrorCode.PATH_INVALID,
        severity=ScanErrorSeverity.FATAL,
        message="路径无效",
    )
    service = ScanRepository(FakeCollector(CollectOutcome(errors=(fatal,))), ExplodingAnalyzer(), repository)

    result = await service.execute(_request())

    assert result.status is ScanStatus.FAILED
    assert result.revision is None
    assert result.graph is None
    assert result.errors == (fatal,)
    assert repository.save_calls == 0


@pytest.mark.asyncio
async def test_analyze_fatal_failure_returns_failed_with_revision() -> None:
    repository = InMemoryCodeGraphRepository()
    fatal = ScanError(
        stage=ScanStage.ANALYZE,
        code=ScanErrorCode.FILE_ENCODING,
        severity=ScanErrorSeverity.FATAL,
        message="整体编码失败",
    )
    service = ScanRepository(
        FakeCollector(CollectOutcome(manifest=_manifest())),
        FakeAnalyzer(AnalyzeOutcome(errors=(fatal,))),
        repository,
    )

    result = await service.execute(_request())

    assert result.status is ScanStatus.FAILED
    assert result.revision == "abc123"
    assert result.graph is None
    assert result.stats.files_collected == 2
    assert repository.save_calls == 0


@pytest.mark.asyncio
async def test_local_analyze_error_yields_partial() -> None:
    repository = InMemoryCodeGraphRepository()
    graph = _graph()
    service = ScanRepository(
        FakeCollector(CollectOutcome(manifest=_manifest())),
        FakeAnalyzer(AnalyzeOutcome(graph=graph, errors=(_local_syntax_error(),))),
        repository,
    )

    result = await service.execute(_request())

    assert result.status is ScanStatus.PARTIAL
    assert result.graph == graph
    assert result.errors == (_local_syntax_error(),)
    assert result.stats == ScanStats(files_collected=2, files_analyzed=1, files_failed=1)
    assert repository.save_calls == 1


@pytest.mark.asyncio
async def test_call_funnel_is_copied_to_scan_stats() -> None:
    service = ScanRepository(
        FakeCollector(CollectOutcome(manifest=_manifest())),
        FakeAnalyzer(
            AnalyzeOutcome(
                graph=_graph(),
                call_funnel=CallFunnel(
                    calls_dynamic=2,
                    calls_unresolved=3,
                    oversized_ambiguous_calls=1,
                ),
            )
        ),
        InMemoryCodeGraphRepository(),
    )

    result = await service.execute(_request())

    assert result.stats.calls_dynamic == 2
    assert result.stats.calls_unresolved == 3
    assert result.stats.oversized_ambiguous_calls == 1


@pytest.mark.asyncio
async def test_persist_failure_is_fatal_storage_error() -> None:
    graph = _graph()
    service = ScanRepository(
        FakeCollector(CollectOutcome(manifest=_manifest())),
        FakeAnalyzer(AnalyzeOutcome(graph=graph)),
        FailingRepository(),
    )

    result = await service.execute(_request())

    assert result.status is ScanStatus.FAILED
    assert result.graph is None
    assert result.revision == "abc123"
    persist_error = result.errors[-1]
    assert persist_error.stage is ScanStage.PERSIST
    assert persist_error.code is ScanErrorCode.STORAGE_ERROR
    assert persist_error.severity is ScanErrorSeverity.FATAL


@pytest.mark.asyncio
async def test_local_collect_error_is_carried_into_partial_result() -> None:
    repository = InMemoryCodeGraphRepository()
    graph = _graph()
    local = ScanError(
        stage=ScanStage.COLLECT,
        code=ScanErrorCode.FILE_UNREADABLE,
        severity=ScanErrorSeverity.LOCAL,
        message="文件不可读",
        file_path="app/mod_1.py",
    )
    service = ScanRepository(
        FakeCollector(CollectOutcome(manifest=_manifest(), errors=(local,))),
        FakeAnalyzer(AnalyzeOutcome(graph=graph)),
        repository,
    )

    result: ScanResult = await service.execute(_request())

    assert result.status is ScanStatus.PARTIAL
    assert result.errors == (local,)


@pytest.mark.asyncio
async def test_in_memory_repository_roundtrip() -> None:
    """InMemoryCodeGraphRepository 的 save/get 行为与端口语义一致。"""

    repository = InMemoryCodeGraphRepository()
    await repository.save(_graph())

    assert await repository.get("demo", "abc123") is not None
    assert await repository.get("demo", "def456") is None
