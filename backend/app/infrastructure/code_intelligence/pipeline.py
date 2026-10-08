"""CALLS scanner 与外部 Provider 的降级、适配和合并编排。"""

import logging
import time
from pathlib import Path

from app.domain.codegraph.kinds import NodeKind
from app.domain.codegraph.models import CodeNode
from app.infrastructure.analyzers.python_calls import CallFact, DefinitionSymbol
from app.infrastructure.code_intelligence.adapter.canonicalize import merge_call_facts
from app.infrastructure.code_intelligence.adapter.identity import match_canonical_node
from app.infrastructure.code_intelligence.adapter.provenance import build_provider_record
from app.infrastructure.code_intelligence.adapter.relation_mapper import map_relation_kind
from app.infrastructure.code_intelligence.models import CallEnrichmentResult, EngineCallFact
from app.infrastructure.code_intelligence.providers.engine_port import CallGraphProvider

_LOGGER = logging.getLogger(__name__)
_TOOL_NAME = "codegraph_get_call_graph"


class CallEnrichment:
    """Provider 可选；任何引擎失败都确定性降级为 scanner-only。"""

    def __init__(self, provider: CallGraphProvider | None = None, total_budget_seconds: int = 900) -> None:
        self._provider = provider
        self._total_budget_seconds = total_budget_seconds

    def enrich(
        self,
        root: Path,
        nodes: tuple[CodeNode, ...],
        symbols: list[DefinitionSymbol],
        scanner_facts: list[CallFact],
    ) -> CallEnrichmentResult:
        valid_ids = {node.id for node in nodes}
        scanner_edges, scanner_diagnostics = merge_call_facts(scanner_facts, [], valid_ids)
        if self._provider is None:
            return CallEnrichmentResult(edges=scanner_edges, diagnostics=scanner_diagnostics)

        status = self._provider.probe(root)
        if not status.available:
            _LOGGER.warning("CodeGraph Provider 不可用，降级为 scanner-only: %s", status.reason)
            return CallEnrichmentResult(edges=scanner_edges, diagnostics=scanner_diagnostics)

        started_at = time.monotonic()
        engine_facts: list[EngineCallFact] = []
        invalid_records = 0
        nodes_by_raw_id: dict[str, CodeNode]
        for symbol in sorted(symbols, key=lambda item: item.node_id):
            if symbol.kind is not NodeKind.FUNCTION:
                continue
            if time.monotonic() - started_at >= self._total_budget_seconds:
                _LOGGER.warning(
                    "CodeGraph Provider 超过整批预算 %ds，熔断并降级为 scanner-only",
                    self._total_budget_seconds,
                )
                return CallEnrichmentResult(edges=scanner_edges, diagnostics=scanner_diagnostics)
            source = next(node for node in nodes if node.id == symbol.node_id)
            result = self._provider.calls_for_symbol(root, source.source.file_path, symbol.node.lineno)
            if result.error is not None or result.graph is None:
                _LOGGER.warning(
                    "CodeGraph Provider 查询失败，整次降级为 scanner-only（%s:%d）: %s",
                    source.source.file_path,
                    symbol.node.lineno,
                    result.error,
                )
                return CallEnrichmentResult(edges=scanner_edges, diagnostics=scanner_diagnostics)
            if time.monotonic() - started_at >= self._total_budget_seconds:
                _LOGGER.warning(
                    "CodeGraph Provider 超过整批预算 %ds，丢弃未完成引擎结果并降级为 scanner-only",
                    self._total_budget_seconds,
                )
                return CallEnrichmentResult(edges=scanner_edges, diagnostics=scanner_diagnostics)
            invalid_records += result.invalid_records
            graph = result.graph
            nodes_by_raw_id = {}
            for raw in (*graph.nodes, *((graph.root_node,) if graph.root_node is not None else ())):
                matched = match_canonical_node(raw, nodes, root)
                if matched is not None:
                    nodes_by_raw_id[raw.id] = matched
            for edge in graph.edges:
                if map_relation_kind(edge.type) is None or edge.from_id != graph.root:
                    continue
                target = nodes_by_raw_id.get(edge.to_id)
                if target is not None:
                    engine_facts.append(EngineCallFact(source_id=source.id, target_id=target.id))

        edges, diagnostics = merge_call_facts(
            scanner_facts,
            engine_facts,
            valid_ids,
            invalid_raw_records=invalid_records,
        )
        record = build_provider_record(self._provider.name, status, _TOOL_NAME)
        _LOGGER.info(
            "CodeGraph Provider 合并完成: engine_only=%d scanner_only=%d dropped=%d invalid_raw=%d",
            diagnostics.engine_only,
            diagnostics.scanner_only,
            diagnostics.dropped_endpoints,
            diagnostics.invalid_raw_records,
        )
        return CallEnrichmentResult(
            edges=edges,
            provenance=(record,) if record is not None else (),
            diagnostics=diagnostics,
        )
