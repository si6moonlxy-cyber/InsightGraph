"""scanner 与 engine 调用事实的确定性合并。"""

from app.domain.codegraph.ids import build_edge_id
from app.domain.codegraph.kinds import CallResolution, EdgeKind
from app.domain.codegraph.models import CodeEdge
from app.infrastructure.analyzers.python_calls import CallFact
from app.infrastructure.code_intelligence.adapter.resolution import engine_resolution
from app.infrastructure.code_intelligence.models import EngineCallFact, EnrichmentDiagnostics


def merge_call_facts(
    scanner_facts: list[CallFact],
    engine_facts: list[EngineCallFact],
    valid_node_ids: set[str],
    *,
    invalid_raw_records: int = 0,
) -> tuple[tuple[CodeEdge, ...], EnrichmentDiagnostics]:
    """引擎只增强已有证据的边；无 call-site span 的 engine-only 边不得物化。"""
    valid_engine = {
        (fact.source_id, fact.target_id)
        for fact in engine_facts
        if fact.source_id in valid_node_ids and fact.target_id in valid_node_ids and fact.source_id != fact.target_id
    }
    grouped: dict[tuple[str, str], list[CallFact]] = {}
    ambiguous_targets: dict[tuple[str, str, int, int], set[str]] = {}
    dropped_endpoints = 0
    for fact in scanner_facts:
        if fact.source_id not in valid_node_ids or fact.target_id not in valid_node_ids:
            dropped_endpoints += 1
            continue
        grouped.setdefault((fact.source_id, fact.target_id), []).append(fact)
        if fact.resolution is CallResolution.AMBIGUOUS:
            call_key = (
                fact.source_id,
                fact.call_span.file_path,
                fact.call_span.line_start,
                fact.call_span.line_end,
            )
            ambiguous_targets.setdefault(call_key, set()).add(fact.target_id)

    edges: list[CodeEdge] = []
    for (source_id, target_id), group in grouped.items():
        protected_ambiguity = any(
            item.resolution is CallResolution.AMBIGUOUS
            and len(
                ambiguous_targets.get(
                    (
                        item.source_id,
                        item.call_span.file_path,
                        item.call_span.line_start,
                        item.call_span.line_end,
                    ),
                    (),
                )
            )
            > 1
            for item in group
        )
        resolution = (
            engine_resolution()
            if ((source_id, target_id) in valid_engine and not protected_ambiguity)
            or any(item.resolution is CallResolution.RESOLVED for item in group)
            else CallResolution.AMBIGUOUS
        )
        representative = min(
            (item.call_span for item in group),
            key=lambda span: (span.line_start, span.line_end),
        )
        edges.append(
            CodeEdge(
                id=build_edge_id(EdgeKind.CALLS, source_id, target_id),
                kind=EdgeKind.CALLS,
                source_id=source_id,
                target_id=target_id,
                source_span=representative,
                resolution=resolution,
                is_truncated=resolution is CallResolution.AMBIGUOUS and any(item.is_truncated for item in group),
            )
        )
    scanner_pairs = set(grouped)
    edges.sort(key=lambda edge: edge.id)
    return tuple(edges), EnrichmentDiagnostics(
        engine_only=len(valid_engine - scanner_pairs),
        scanner_only=len(scanner_pairs - valid_engine),
        dropped_endpoints=dropped_endpoints,
        invalid_raw_records=invalid_raw_records,
    )
