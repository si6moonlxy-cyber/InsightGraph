"""步骤 4 采集 + 分析一条链 CLI（开发狗粮工具）。

用法（在 backend/ 目录下）:
    uv run python -m app.infrastructure.analyzers <仓库路径>
        [--repository-id ID] [--json]

退出码: 0 = 产出 CodeGraph；1 = 整体失败（采集失败或无图）。
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from app.application.scans.models import ScanError, ScanRequest, SourceManifest
from app.domain.codegraph.models import CodeGraph
from app.foundation.config import get_settings
from app.infrastructure.analyzers.python_ast import PythonAstAnalyzer
from app.infrastructure.code_intelligence.providers import create_call_graph_provider
from app.infrastructure.collectors import GitRepositoryCollector, resolve_repository_root

_LOGGER = logging.getLogger("insightgraph.codegraph")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.infrastructure.analyzers",
        description="采集并分析本地 Git 仓库，输出 CodeGraph IR",
    )
    parser.add_argument("path", type=Path, help="仓库路径（子目录会被自动归一为仓库根）")
    parser.add_argument("--repository-id", default=None, help="repository_id；默认取路径目录名")
    parser.add_argument("--json", action="store_true", help="输出规范 JSON CodeGraph（不打印摘要）")
    return parser


async def _run(request: ScanRequest) -> tuple[tuple[ScanError, ...], SourceManifest | None, CodeGraph | None]:
    collect_outcome = await GitRepositoryCollector().collect(request)
    if collect_outcome.manifest is None:
        return collect_outcome.errors, None, None
    settings = get_settings()
    provider = (
        create_call_graph_provider(
            "codegraph-ai",
            Path(settings.codegraph_engine_path),
            settings.codegraph_engine_timeout_seconds,
        )
        if settings.codegraph_engine_enabled
        else None
    )
    analyze_outcome = await PythonAstAnalyzer(
        provider,
        call_graph_total_budget_seconds=settings.codegraph_engine_total_budget_seconds,
    ).analyze(request, collect_outcome.manifest)
    return collect_outcome.errors + analyze_outcome.errors, collect_outcome.manifest, analyze_outcome.graph


def main(argv: list[str] | None = None) -> int:
    reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure_stdout):
        reconfigure_stdout(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    args = build_parser().parse_args(argv)
    path = resolve_repository_root(args.path) or args.path
    repository_id = args.repository_id or path.resolve().name
    request = ScanRequest(repository_id=repository_id, path=path)

    errors, manifest, graph = asyncio.run(_run(request))

    if graph is None or manifest is None:
        _LOGGER.error("分析失败（无 CodeGraph）：")
        for error in errors:
            _LOGGER.error("  [%s] %s: %s", error.code, error.severity, error.message)
        return 1

    if args.json:
        _LOGGER.info(graph.model_dump_json(indent=2))
        return 0

    _LOGGER.info("repository_id: %s", graph.repository_id)
    _LOGGER.info("revision: %s", graph.revision)
    _LOGGER.info("nodes: %d", len(graph.nodes))
    _LOGGER.info("edges: %d", len(graph.edges))
    _LOGGER.info("局部错误: %d 条", len(errors))
    for error in errors:
        _LOGGER.warning("  [%s] %s: %s", error.code, error.file_path or "-", error.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
