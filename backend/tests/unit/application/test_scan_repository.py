"""扫描应用服务只负责编排端口。"""

from pathlib import Path

import pytest

from app.application.scans.models import ScanRequest, SourceManifest
from app.application.scans.service import ScanRepository
from app.domain.codegraph.models import CodeGraph


class FakeCollector:
    async def collect(self, request: ScanRequest) -> SourceManifest:
        return SourceManifest(
            repository_id=request.repository_id,
            revision="abc123",
        )


class FakeAnalyzer:
    async def analyze(self, manifest: SourceManifest) -> CodeGraph:
        return CodeGraph(
            repository_id=manifest.repository_id,
            revision=manifest.revision,
            parser_version="fake/1",
        )


class InMemoryCodeGraphRepository:
    def __init__(self) -> None:
        self.graph: CodeGraph | None = None

    async def save(self, graph: CodeGraph) -> None:
        self.graph = graph

    async def get(self, repository_id: str, revision: str) -> CodeGraph | None:
        if self.graph is None:
            return None
        if self.graph.repository_id == repository_id and self.graph.revision == revision:
            return self.graph
        return None


@pytest.mark.asyncio
async def test_scan_repository_composes_ports() -> None:
    repository = InMemoryCodeGraphRepository()
    service = ScanRepository(FakeCollector(), FakeAnalyzer(), repository)

    graph = await service.execute(
        ScanRequest(repository_id="demo", path=Path("fixtures/demo")),
    )

    assert graph.revision == "abc123"
    assert repository.graph == graph
