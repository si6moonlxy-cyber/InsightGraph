"""扫描用例依赖的外部能力端口。"""

from typing import Protocol

from app.application.scans.models import AnalyzeOutcome, CollectOutcome, ScanRequest, SourceManifest


class RepositoryCollector(Protocol):
    """收集仓库事实，不分析代码语义。"""

    async def collect(self, request: ScanRequest) -> CollectOutcome: ...


class CodeAnalyzer(Protocol):
    """把文件清单转换为 CodeGraph IR。"""

    async def analyze(self, manifest: SourceManifest) -> AnalyzeOutcome: ...
