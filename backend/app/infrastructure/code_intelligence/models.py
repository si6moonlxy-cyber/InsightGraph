"""code_intelligence 层内部传递模型。"""

from dataclasses import dataclass

from app.domain.codegraph.models import CodeEdge, ProviderRecord


@dataclass(frozen=True)
class ProviderStatus:
    """外部引擎可用性与可追溯版本信息。"""

    available: bool
    reason: str | None = None
    version: str | None = None
    asset_hash: str | None = None

    @classmethod
    def unavailable(cls, reason: str) -> "ProviderStatus":
        return cls(available=False, reason=reason)


@dataclass(frozen=True)
class EngineCallFact:
    """已映射到 Canonical 节点、但不伪造调用点 span 的引擎调用事实。"""

    source_id: str
    target_id: str


@dataclass(frozen=True)
class EnrichmentDiagnostics:
    """只用于日志与测试的适配诊断，不进入稳定领域契约。"""

    engine_only: int = 0
    scanner_only: int = 0
    dropped_endpoints: int = 0
    invalid_raw_records: int = 0


@dataclass(frozen=True)
class CallEnrichmentResult:
    """CALLS 合并后的边、来源记录与诊断。"""

    edges: tuple[CodeEdge, ...]
    provenance: tuple[ProviderRecord, ...] = ()
    diagnostics: EnrichmentDiagnostics = EnrichmentDiagnostics()
