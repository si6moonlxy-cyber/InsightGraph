"""仓库扫描用例编排。"""

from app.application.scans.models import (
    AnalyzeOutcome,
    ScanError,
    ScanErrorCode,
    ScanErrorSeverity,
    ScanRequest,
    ScanResult,
    ScanStage,
    ScanStats,
    ScanStatus,
    SourceManifest,
)
from app.application.scans.ports import CodeAnalyzer, RepositoryCollector
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

    async def execute(self, request: ScanRequest) -> ScanResult:
        collect_outcome = await self._collector.collect(request)
        if collect_outcome.manifest is None:
            # CollectOutcome 不变量保证此时必有 fatal 错误；无 revision 可携带
            return ScanResult(
                repository_id=request.repository_id,
                status=ScanStatus.FAILED,
                errors=collect_outcome.errors,
            )
        manifest = collect_outcome.manifest
        analyze_outcome = await self._analyzer.analyze(request, manifest)
        errors = collect_outcome.errors + analyze_outcome.errors
        stats = _build_stats(manifest, analyze_outcome)
        if analyze_outcome.graph is None:
            return ScanResult(
                repository_id=request.repository_id,
                revision=manifest.revision,
                status=ScanStatus.FAILED,
                errors=errors,
                stats=stats,
            )
        graph = analyze_outcome.graph
        try:
            await self._repository.save(graph)
        except Exception as error:  # 步骤 6 接入真实存储后按需收窄捕获范围
            return ScanResult(
                repository_id=request.repository_id,
                revision=manifest.revision,
                status=ScanStatus.FAILED,
                errors=errors
                + (
                    ScanError(
                        stage=ScanStage.PERSIST,
                        code=ScanErrorCode.STORAGE_ERROR,
                        severity=ScanErrorSeverity.FATAL,
                        message=f"保存 CodeGraph 失败: {error!r}",
                    ),
                ),
                stats=stats,
            )
        status = ScanStatus.PARTIAL if errors else ScanStatus.COMPLETED
        return ScanResult(
            repository_id=request.repository_id,
            revision=manifest.revision,
            status=status,
            graph=graph,
            errors=errors,
            stats=stats,
        )


def _build_stats(manifest: SourceManifest, analyze_outcome: AnalyzeOutcome) -> ScanStats:
    """按漏斗口径统计：analyzed = collected - 有局部错误的去重文件数。"""
    failed_files = {error.file_path for error in analyze_outcome.errors if error.file_path is not None}
    call_funnel = analyze_outcome.call_funnel
    return ScanStats(
        files_collected=len(manifest.files),
        files_failed=len(failed_files),
        files_analyzed=len(manifest.files) - len(failed_files),
        calls_dynamic=call_funnel.calls_dynamic if call_funnel is not None else 0,
        calls_unresolved=call_funnel.calls_unresolved if call_funnel is not None else 0,
        oversized_ambiguous_calls=call_funnel.oversized_ambiguous_calls if call_funnel is not None else 0,
    )
