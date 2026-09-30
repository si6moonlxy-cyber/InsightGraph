"""仓库扫描用例编排。"""

from app.application.scans.models import ScanRequest
from app.application.scans.ports import CodeAnalyzer, RepositoryCollector
from app.domain.codegraph.models import CodeGraph
from app.domain.codegraph.ports import CodeGraphRepository


class ScanRepository:
    """只编排端口；采集、分析和存储实现均由外层注入。"""

    def __init__(
        self,
        collector: RepositoryCollector,
        analyzer: CodeAnalyzer,
        repository: CodeGraphRepository,
    ) -> None:
        self._collector = collector
        self._analyzer = analyzer
        self._repository = repository

    async def execute(self, request: ScanRequest) -> CodeGraph:
        manifest = await self._collector.collect(request)
        graph = await self._analyzer.analyze(manifest)
        await self._repository.save(graph)
        return graph
