"""CodeGraph 产物不变量校验（CI 用；也可作为手工脚本运行）。

三项检查（步骤 4 复核后固化，经 pytest 在 CI 强制执行）：
1. 每个 class / function 节点至少有一条 DEFINES 入边（模块节点作为根不要求入边）。
2. 每个节点的 content_hash 与源码重算结果一致：
   按 SourceSpan 取行，CRLF→LF 归一后计算 SHA-256。
3. 每条 imports 边的 target_id 必须指向已存在的模块节点。

用法:
    python eval/codegraph/validate.py <artifact.json> --repo-root <仓库根目录>

退出码: 0 = 全部通过；1 = 存在违例（明细打印，最多 50 条）。
"""

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path

_LOGGER = logging.getLogger("insightgraph.eval.validate")


def _normalized_lines(path: Path) -> list[bytes]:
    return path.read_bytes().replace(b"\r\n", b"\n").splitlines(keepends=True)


def validate_artifact(artifact: dict, repo_root: Path) -> list[str]:
    """校验 CodeGraph 工件，返回违例描述列表（空列表 = 全部通过）。"""
    violations: list[str] = []
    nodes = artifact["nodes"]
    edges = artifact["edges"]

    # 检查 1：class / function 必须有 DEFINES 入边（模块为根，不要求）
    defines_targets = {edge["target_id"] for edge in edges if edge["kind"] == "defines"}
    for node in nodes:
        if node["kind"] in ("class", "function") and node["id"] not in defines_targets:
            violations.append(f"[defines] {node['kind']} 节点缺少 DEFINES 入边: {node['id']}")

    # 检查 2：content_hash 与源码重算一致
    for node in nodes:
        source = node["source"]
        file_path = repo_root / source["file_path"]
        try:
            lines = _normalized_lines(file_path)
        except OSError as error:
            violations.append(f"[hash] 源码不可读: {source['file_path']}（{error}）")
            continue
        start, end = source["line_start"], source["line_end"]
        span = b"".join(lines[start - 1 : end])
        recomputed = "sha256:" + hashlib.sha256(span).hexdigest()
        if recomputed != node["content_hash"]:
            violations.append(
                f"[hash] content_hash 不一致: {node['id']}（重算 {recomputed}，工件 {node['content_hash']}）"
            )

    # 检查 3：imports 边的 target 必须是已存在的模块节点
    module_ids = {node["id"] for node in nodes if node["kind"] == "module"}
    for edge in edges:
        if edge["kind"] == "imports" and edge["target_id"] not in module_ids:
            violations.append(f"[imports] target 不是已存在的模块节点: {edge['id']}")

    return violations


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    parser = argparse.ArgumentParser(description="CodeGraph 产物三项不变量校验")
    parser.add_argument("artifact", type=Path, help="CodeGraph JSON 工件路径")
    parser.add_argument("--repo-root", type=Path, required=True, help="源码仓库根（工件内路径的相对基准）")
    args = parser.parse_args(argv)

    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    violations = validate_artifact(artifact, args.repo_root)
    _LOGGER.info("nodes: %d, edges: %d", len(artifact["nodes"]), len(artifact["edges"]))
    if violations:
        _LOGGER.error("发现 %d 条违例：", len(violations))
        for violation in violations[:50]:
            _LOGGER.error("  %s", violation)
        return 1
    _LOGGER.info("三项不变量全部通过 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
