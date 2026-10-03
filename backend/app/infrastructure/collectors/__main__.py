"""步骤 3 最小采集 CLI（开发狗粮工具）。

用法（在 backend/ 目录下）:
    uv run python -m app.infrastructure.collectors <仓库路径>
        [--repository-id ID] [--json]

退出码: 0 = 产出 Manifest（可能含局部错误）；1 = 整体失败（无 Manifest）。
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from app.application.scans.models import ScanRequest
from app.infrastructure.collectors.git_repository import GitRepositoryCollector

_LOGGER = logging.getLogger("insightgraph.scan_repo")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.infrastructure.collectors",
        description="把本地 Git 仓库采集为确定性 SourceManifest",
    )
    parser.add_argument("path", type=Path, help="仓库路径（子目录会解析到仓库根）")
    parser.add_argument("--repository-id", default=None, help="repository_id；默认取路径目录名")
    parser.add_argument("--json", action="store_true", help="输出规范 JSON Manifest（不打印摘要）")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    args = build_parser().parse_args(argv)
    repository_id = args.repository_id or args.path.resolve().name
    request = ScanRequest(repository_id=repository_id, path=args.path)

    outcome = asyncio.run(GitRepositoryCollector().collect(request))

    if outcome.manifest is None:
        _LOGGER.error("采集失败（无 Manifest）：")
        for error in outcome.errors:
            _LOGGER.error("  [%s] %s: %s", error.code, error.severity, error.message)
        return 1

    manifest = outcome.manifest
    if args.json:
        _LOGGER.info(manifest.model_dump_json(indent=2))
        return 0

    _LOGGER.info("repository_id: %s", manifest.repository_id)
    _LOGGER.info("revision: %s", manifest.revision)
    _LOGGER.info("worktree_dirty: %s", manifest.worktree_dirty)
    _LOGGER.info("files: %d", len(manifest.files))
    if outcome.errors:
        _LOGGER.warning("局部错误: %d 条", len(outcome.errors))
        for error in outcome.errors:
            _LOGGER.warning("  [%s] %s: %s", error.code, error.file_path or "-", error.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
