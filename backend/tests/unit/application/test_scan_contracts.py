"""扫描结果与阶段契约的不变量测试。"""

import pytest
from pydantic import ValidationError

from app.application.scans.models import (
    AnalyzeOutcome,
    CollectOutcome,
    ScanError,
    ScanErrorCode,
    ScanErrorSeverity,
    ScanResult,
    ScanStage,
    ScanStats,
    ScanStatus,
    SourceFile,
    SourceManifest,
)
from app.domain.codegraph.models import CodeGraph

_SHA = "sha256:" + "1" * 64


def _graph(repository_id: str = "demo", revision: str = "abc123") -> CodeGraph:
    return CodeGraph(repository_id=repository_id, revision=revision, parser_version="fake/1")


def _manifest(repository_id: str = "demo", revision: str = "abc123") -> SourceManifest:
    return SourceManifest(
        repository_id=repository_id,
        revision=revision,
        files=(SourceFile(path="app/main.py", content_hash=_SHA),),
    )


def _error(
    stage: ScanStage = ScanStage.ANALYZE,
    code: ScanErrorCode = ScanErrorCode.SYNTAX_ERROR,
    severity: ScanErrorSeverity = ScanErrorSeverity.LOCAL,
) -> ScanError:
    return ScanError(stage=stage, code=code, severity=severity, message="坏文件", file_path="app/bad.py")


def test_error_message_is_required() -> None:
    with pytest.raises(ValidationError, match="message"):
        ScanError(
            stage=ScanStage.ANALYZE,
            code=ScanErrorCode.SYNTAX_ERROR,
            severity=ScanErrorSeverity.LOCAL,
            message="",
        )


def test_stats_funnel_invariant() -> None:
    with pytest.raises(ValidationError, match="不能超过"):
        ScanStats(files_collected=1, files_analyzed=1, files_failed=1)


def test_collect_outcome_requires_manifest_without_fatal() -> None:
    local = _error(stage=ScanStage.COLLECT, code=ScanErrorCode.FILE_UNREADABLE)
    fatal = _error(stage=ScanStage.COLLECT, code=ScanErrorCode.PATH_INVALID, severity=ScanErrorSeverity.FATAL)

    with pytest.raises(ValidationError, match="必须产出 manifest"):
        CollectOutcome(manifest=None, errors=(local,))
    assert CollectOutcome(manifest=None, errors=(fatal,)).manifest is None
    assert CollectOutcome(manifest=_manifest(), errors=(local,)).errors == (local,)


def test_collect_outcome_rejects_foreign_stage() -> None:
    with pytest.raises(ValidationError, match="collect"):
        CollectOutcome(manifest=_manifest(), errors=(_error(stage=ScanStage.ANALYZE),))


def test_analyze_outcome_requires_graph_without_fatal() -> None:
    local = _error()
    fatal = _error(severity=ScanErrorSeverity.FATAL)

    with pytest.raises(ValidationError, match="必须产出 CodeGraph"):
        AnalyzeOutcome(graph=None, errors=(local,))
    assert AnalyzeOutcome(graph=None, errors=(fatal,)).graph is None
    assert AnalyzeOutcome(graph=_graph(), errors=(local,)).errors == (local,)


def test_analyze_outcome_rejects_foreign_stage() -> None:
    with pytest.raises(ValidationError, match="analyze"):
        AnalyzeOutcome(graph=_graph(), errors=(_error(stage=ScanStage.COLLECT),))


def test_completed_result_requires_graph_and_no_errors() -> None:
    result = ScanResult(
        repository_id="demo",
        revision="abc123",
        status=ScanStatus.COMPLETED,
        graph=_graph(),
    )

    assert result.stats.files_collected == 0

    with pytest.raises(ValidationError, match="没有任何错误"):
        ScanResult(
            repository_id="demo",
            revision="abc123",
            status=ScanStatus.COMPLETED,
            graph=_graph(),
            errors=(_error(),),
        )
    with pytest.raises(ValidationError, match="必须产出图"):
        ScanResult(repository_id="demo", revision="abc123", status=ScanStatus.COMPLETED)
    with pytest.raises(ValidationError, match="revision"):
        ScanResult(repository_id="demo", status=ScanStatus.COMPLETED, graph=_graph())


def test_partial_result_requires_graph_and_local_errors() -> None:
    result = ScanResult(
        repository_id="demo",
        revision="abc123",
        status=ScanStatus.PARTIAL,
        graph=_graph(),
        errors=(_error(),),
    )

    assert result.status is ScanStatus.PARTIAL

    with pytest.raises(ValidationError, match="不允许包含 fatal"):
        ScanResult(
            repository_id="demo",
            revision="abc123",
            status=ScanStatus.PARTIAL,
            graph=_graph(),
            errors=(_error(severity=ScanErrorSeverity.FATAL),),
        )
    with pytest.raises(ValidationError, match="至少有一条局部错误"):
        ScanResult(repository_id="demo", revision="abc123", status=ScanStatus.PARTIAL, graph=_graph())


def test_failed_result_requires_fatal_and_no_graph() -> None:
    fatal = _error(stage=ScanStage.COLLECT, code=ScanErrorCode.PATH_INVALID, severity=ScanErrorSeverity.FATAL)
    result = ScanResult(repository_id="demo", status=ScanStatus.FAILED, errors=(fatal,))

    assert result.revision is None
    assert result.graph is None

    with pytest.raises(ValidationError, match="不携带图"):
        ScanResult(
            repository_id="demo",
            revision="abc123",
            status=ScanStatus.FAILED,
            graph=_graph(),
            errors=(fatal,),
        )
    with pytest.raises(ValidationError, match="至少有一条 fatal"):
        ScanResult(repository_id="demo", status=ScanStatus.FAILED, errors=(_error(),))


def test_graph_identity_must_match_result() -> None:
    with pytest.raises(ValidationError, match="repository_id"):
        ScanResult(
            repository_id="demo",
            revision="abc123",
            status=ScanStatus.COMPLETED,
            graph=_graph(repository_id="other"),
        )
    with pytest.raises(ValidationError, match="revision"):
        ScanResult(
            repository_id="demo",
            revision="abc123",
            status=ScanStatus.COMPLETED,
            graph=_graph(revision="def456"),
        )
