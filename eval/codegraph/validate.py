"""CodeGraph 产物不变量校验（CI 用；也可作为手工脚本运行）。

五项检查（步骤 4 基线 + 步骤 5 schema v2 增量，经 pytest 在 CI 强制执行）：
1. 每个 class / function 节点至少有一条 DEFINES 入边（模块节点作为根不要求入边）。
2. 每个节点的 content_hash 与源码重算结果一致：
   按 SourceSpan 取行，CRLF→LF 归一后计算 SHA-256。
3. 每条 imports 边的 target_id 必须指向已存在的模块节点。
4. 每条 calls 边必须携带合法 source_span 与 resolved/ambiguous resolution。
5. entries 引用存在、类型正确且与入口 span 位于同一文件。

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

    # 检查 4：calls 边必须携带可追溯且合法的调用证据
    nodes_by_id = {node["id"]: node for node in nodes}
    for edge in edges:
        if edge["kind"] != "calls":
            continue
        span = edge.get("source_span")
        if span is None or edge.get("resolution") not in ("resolved", "ambiguous"):
            violations.append(f"[calls] 缺少合法 source_span/resolution: {edge['id']}")
            continue
        source = nodes_by_id.get(edge["source_id"])
        if source is None or source["source"]["file_path"] != span["file_path"]:
            violations.append(f"[calls] source_span 与调用源不在同一文件: {edge['id']}")
        if edge.get("is_truncated", False) and edge.get("resolution") != "ambiguous":
            violations.append(f"[calls] is_truncated 只能用于 ambiguous: {edge['id']}")

    # 检查 5：入口引用必须落在同文件的 module/function 节点
    for entry in artifact.get("entries", []):
        module = nodes_by_id.get(entry["module_id"])
        if module is None or module["kind"] != "module":
            violations.append(f"[entries] module_id 不是已存在的模块节点: {entry['module_id']}")
            continue
        if module["source"]["file_path"] != entry["span"]["file_path"]:
            violations.append(f"[entries] span 与模块不在同一文件: {entry['module_id']}")
        target_id = entry.get("target_node_id")
        if target_id is not None:
            target = nodes_by_id.get(target_id)
            if target is None or target["kind"] != "function":
                violations.append(f"[entries] target_node_id 不是已存在的函数节点: {target_id}")
            elif target["source"]["file_path"] != entry["span"]["file_path"]:
                violations.append(f"[entries] 目标与入口不在同一文件: {target_id}")

    return violations


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    parser = argparse.ArgumentParser(description="CodeGraph 产物五项不变量校验")
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
    _LOGGER.info("五项不变量全部通过 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
