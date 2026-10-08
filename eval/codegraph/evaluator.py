"""CodeGraph 解析评测入口（首个评测能力，对应步骤 4）。

用法（任意目录下皆可）:
    python eval/codegraph/evaluator.py                    # 运行默认 case，打印报告
    python eval/codegraph/evaluator.py --write-baseline   # 显式写入基线（规则见 eval/README.md）

对比口径（步骤 4 决策记录）：语义集合 100%——节点 / 边按投影后的集合双向比对
（既无缺失、也无多余），投影只取确定字段（容忍未来新增字段）；
Artifact 的字节级稳定性由 pytest 的“双跑自比”测试覆盖。

规则约束（eval/README.md）：Baseline 只创建、不自动覆盖；Golden 修改必须人工审核，
AI 只能生成候选样本与预标注。
"""

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.application.scans.models import ScanRequest, SourceFile, SourceManifest  # noqa: E402
from app.domain.codegraph.models import CodeEdge, CodeGraph, CodeNode, EntryPoint  # noqa: E402
from app.infrastructure.analyzers.python_ast import PythonAstAnalyzer  # noqa: E402

_LOGGER = logging.getLogger("insightgraph.eval.codegraph")

CASES_DIR = Path(__file__).resolve().parent / "cases"
BASELINES_DIR = Path(__file__).resolve().parent / "baselines"
OUTPUTS_DIR = Path(__file__).resolve().parent / ".outputs"

DEFAULT_CASE = "golden-python-basic"
DATASET_VERSION = "eval-v2"
FIXTURE_REVISION = "fixture-v1"


def build_fixture_manifest(repo_dir: Path, repository_id: str) -> SourceManifest:
    """为固定 fixture 目录构建 SourceManifest（不经 git，供评测使用）。

    口径与 GitRepositoryCollector 一致：仓库相对 POSIX 路径、升序、
    CRLF→LF 归一的 SHA-256，仅收 `.py`。评测夹具目录不是独立 Git 仓库，
    故在此以本地实现生成清单（真实 Collector 由独立单测覆盖）。
    """
    collected: list[tuple[str, str]] = []
    for path in repo_dir.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(repo_dir).as_posix()
        normalized = path.read_bytes().replace(b"\r\n", b"\n")
        collected.append((relative, f"sha256:{hashlib.sha256(normalized).hexdigest()}"))
    collected.sort(key=lambda item: item[0])
    return SourceManifest(
        repository_id=repository_id,
        revision=FIXTURE_REVISION,
        worktree_dirty=False,
        files=tuple(SourceFile(path=relative, content_hash=content_hash) for relative, content_hash in collected),
    )


def _node_projection(node: CodeNode) -> tuple[object, ...]:
    return (
        node.id,
        node.kind.value,
        node.qualified_name,
        node.language,
        node.source.file_path,
        node.source.line_start,
        node.source.line_end,
        node.content_hash,
    )


def _edge_projection(edge: CodeEdge) -> tuple[object, ...]:
    span = edge.source_span
    return (
        edge.id,
        edge.kind.value,
        edge.source_id,
        edge.target_id,
        edge.resolution.value if edge.resolution is not None else None,
        span.file_path if span is not None else None,
        span.line_start if span is not None else None,
        span.line_end if span is not None else None,
        edge.is_truncated,
    )


def _node_projection_from_json(node: dict) -> tuple[object, ...]:
    source = node["source"]
    return (
        node["id"],
        node["kind"],
        node["qualified_name"],
        node["language"],
        source["file_path"],
        source["line_start"],
        source["line_end"],
        node["content_hash"],
    )


def _edge_projection_from_json(edge: dict) -> tuple[object, ...]:
    span = edge.get("source_span")
    return (
        edge["id"],
        edge["kind"],
        edge["source_id"],
        edge["target_id"],
        edge.get("resolution"),
        span["file_path"] if span is not None else None,
        span["line_start"] if span is not None else None,
        span["line_end"] if span is not None else None,
        edge.get("is_truncated", False),
    )


def _entry_projection(entry: EntryPoint) -> tuple[object, ...]:
    span = entry.span
    return (
        entry.kind.value,
        entry.module_id,
        span.file_path,
        span.line_start,
        span.line_end,
        entry.symbol,
        entry.target_node_id,
    )


def _entry_projection_from_json(entry: dict) -> tuple[object, ...]:
    span = entry["span"]
    return (
        entry["kind"],
        entry["module_id"],
        span["file_path"],
        span["line_start"],
        span["line_end"],
        entry.get("symbol"),
        entry.get("target_node_id"),
    )


def compare_graphs(actual: CodeGraph, expected: dict) -> dict:
    """语义集合比对：返回四项比率与缺失 / 多余明细。"""
    actual_nodes = {_node_projection(node) for node in actual.nodes}
    expected_nodes = {_node_projection_from_json(node) for node in expected["nodes"]}
    actual_edges_source = actual.edges
    if expected.get("schema_version", 1) == 1:
        # v1 基线只验证既有结构边，CALLS 由 v2 Golden 单独冻结。
        actual_edges_source = tuple(edge for edge in actual.edges if edge.kind.value != "calls")
    actual_edges = {_edge_projection(edge) for edge in actual_edges_source}
    expected_edges = {_edge_projection_from_json(edge) for edge in expected["edges"]}
    actual_entries = {_entry_projection(entry) for entry in actual.entries}
    expected_entries = {_entry_projection_from_json(entry) for entry in expected.get("entries", [])}

    matched_nodes = len(actual_nodes & expected_nodes)
    matched_edges = len(actual_edges & expected_edges)
    calls_actual = {edge for edge in actual_edges if edge[1] == "calls"}
    calls_expected = {edge for edge in expected_edges if edge[1] == "calls"}
    matched_calls = len(calls_actual & calls_expected)
    matched_entries = len(actual_entries & expected_entries)
    def ratio(matched: int, total: int) -> float:
        return 1.0 if total == 0 else matched / total

    return {
        "node_recall": matched_nodes / max(1, len(expected_nodes)),
        "node_precision": matched_nodes / max(1, len(actual_nodes)),
        "edge_recall": matched_edges / max(1, len(expected_edges)),
        "edge_precision": matched_edges / max(1, len(actual_edges)),
        "calls_recall": ratio(matched_calls, len(calls_expected)),
        "calls_precision": ratio(matched_calls, len(calls_actual)),
        "entry_recall": ratio(matched_entries, len(expected_entries)),
        "entry_precision": ratio(matched_entries, len(actual_entries)),
        "missing_nodes": sorted(expected_nodes - actual_nodes),
        "extra_nodes": sorted(actual_nodes - expected_nodes),
        "missing_edges": sorted(expected_edges - actual_edges),
        "extra_edges": sorted(actual_edges - expected_edges),
        "missing_entries": sorted(expected_entries - actual_entries),
        "extra_entries": sorted(actual_entries - expected_entries),
    }


def generate_candidate(case_name: str, repository_id: str | None = None) -> dict:
    """运行分析并落盘候选；不把 AI 生成结果自动晋升为 Golden。"""
    case_dir = CASES_DIR / case_name
    expected_path = case_dir / "expected_codegraph.json"
    if repository_id is None and expected_path.exists():
        repository_id = json.loads(expected_path.read_text(encoding="utf-8"))["repository_id"]
    repository_id = repository_id or case_name

    manifest = build_fixture_manifest(case_dir / "repo", repository_id)
    request = ScanRequest(repository_id=repository_id, path=case_dir / "repo")
    outcome = asyncio.run(PythonAstAnalyzer().analyze(request, manifest))
    if outcome.graph is None:
        raise RuntimeError(f"case {case_name} 未产出 CodeGraph: {[error.code.value for error in outcome.errors]}")
    if outcome.errors:
        raise RuntimeError(
            f"case {case_name} 出现局部错误: {[(error.code.value, error.file_path) for error in outcome.errors]}"
        )

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    candidate_path = OUTPUTS_DIR / f"{case_name}.candidate.json"
    candidate_path.write_text(
        outcome.graph.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    calls_count = sum(edge.kind.value == "calls" for edge in outcome.graph.edges)
    unresolved = outcome.call_funnel.calls_unresolved if outcome.call_funnel is not None else 0
    dynamic = outcome.call_funnel.calls_dynamic if outcome.call_funnel is not None else 0
    denominator = dynamic + unresolved + calls_count
    return {
        "case": case_name,
        "graph": outcome.graph,
        "candidate_path": candidate_path,
        "call_funnel": outcome.call_funnel,
        "unresolved_ratio": (dynamic + unresolved) / denominator if denominator else 0.0,
    }


def run_case(case_name: str = DEFAULT_CASE) -> dict:
    """运行单个已冻结 case：生成候选 → 与 Golden 做语义比对。"""
    case_dir = CASES_DIR / case_name
    expected = json.loads((case_dir / "expected_codegraph.json").read_text(encoding="utf-8"))
    generated = generate_candidate(case_name, expected["repository_id"])
    graph = generated["graph"]

    comparison = compare_graphs(graph, expected)
    primary_metrics = [
        comparison["node_recall"],
        comparison["node_precision"],
        comparison["edge_recall"],
        comparison["edge_precision"],
    ]
    if expected.get("schema_version", 1) >= 2:
        primary_metrics.extend((comparison["entry_recall"], comparison["entry_precision"]))
    primary = min(primary_metrics)
    comparison["primary"] = primary if primary == 1.0 else primary
    comparison["case"] = case_name
    comparison["unresolved_ratio"] = generated["unresolved_ratio"]
    return {**generated, "metrics": comparison, "evaluation_schema_version": expected.get("schema_version", 1)}


def _print_report(result: dict) -> None:
    metrics = result["metrics"]
    _LOGGER.info("Feature: codegraph-parser")
    _LOGGER.info("Dataset: %s（case: %s）", DATASET_VERSION, result["case"])
    _LOGGER.info(
        "Primary: %.4f（node_recall=%.4f node_precision=%.4f edge_recall=%.4f edge_precision=%.4f）",
        metrics["primary"],
        metrics["node_recall"],
        metrics["node_precision"],
        metrics["edge_recall"],
        metrics["edge_precision"],
    )
    if result.get("evaluation_schema_version", 1) >= 2:
        _LOGGER.info(
            "CALLS: recall=%.4f precision=%.4f unresolved_ratio=%.4f",
            metrics["calls_recall"],
            metrics["calls_precision"],
            metrics["unresolved_ratio"],
        )
    _LOGGER.info(
        "缺失节点/边: %d / %d；多余节点/边: %d / %d",
        len(metrics["missing_nodes"]),
        len(metrics["missing_edges"]),
        len(metrics["extra_nodes"]),
        len(metrics["extra_edges"]),
    )
    for label, entries in (
        ("missing_node", metrics["missing_nodes"]),
        ("extra_node", metrics["extra_nodes"]),
        ("missing_edge", metrics["missing_edges"]),
        ("extra_edge", metrics["extra_edges"]),
    ):
        for entry in entries[:5]:
            _LOGGER.info("  [%s] %s", label, entry)


def write_baseline(result: dict) -> Path:
    """写入基线摘要（显式 --write-baseline 才会执行；规则：只创建、不自动覆盖）。"""
    metrics = result["metrics"]
    git_sha = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    record = {
        "feature": "codegraph-parser",
        "case": result["case"],
        "dataset_version": DATASET_VERSION,
        "git_sha": git_sha,
        "timestamp": dt.datetime.now(dt.UTC).isoformat(),
        "runner": "eval/codegraph/evaluator.py",
        "model_or_algorithm": result["graph"].parser_version,
        "metrics": {
            "primary": metrics["primary"],
            "node_recall": metrics["node_recall"],
            "node_precision": metrics["node_precision"],
            "edge_recall": metrics["edge_recall"],
            "edge_precision": metrics["edge_precision"],
            "calls_recall": metrics["calls_recall"],
            "calls_precision": metrics["calls_precision"],
            "entry_recall": metrics["entry_recall"],
            "entry_precision": metrics["entry_precision"],
            "unresolved_ratio": metrics["unresolved_ratio"],
        },
        "raw_outputs": result["candidate_path"].relative_to(_REPO_ROOT).as_posix(),
    }
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_version = result["graph"].schema_version
    baseline_path = BASELINES_DIR / f"codegraph-parser-v{baseline_version}.json"
    if baseline_path.exists():
        raise FileExistsError(f"Baseline 只允许新建，不允许覆盖: {baseline_path}")
    baseline_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return baseline_path


def main(argv: list[str] | None = None) -> int:
    reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
    reconfigure_stderr = getattr(sys.stderr, "reconfigure", None)
    if callable(reconfigure_stdout):
        reconfigure_stdout(encoding="utf-8")
    if callable(reconfigure_stderr):
        reconfigure_stderr(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    parser = argparse.ArgumentParser(description="CodeGraph 解析评测（语义集合 100% 口径）")
    parser.add_argument("--case", default=DEFAULT_CASE, help="case 名称（cases/ 下的目录名）")
    parser.add_argument("--write-baseline", action="store_true", help="显式写入基线摘要（baselines/）")
    parser.add_argument("--candidate-only", action="store_true", help="仅生成候选，不要求 Golden 已存在")
    args = parser.parse_args(argv)

    if args.candidate_only:
        result = generate_candidate(args.case)
        _LOGGER.info("candidate written: %s", result["candidate_path"])
        return 0
    result = run_case(args.case)
    _print_report(result)
    if args.write_baseline:
        baseline_path = write_baseline(result)
        _LOGGER.info("baseline written: %s", baseline_path)
    return 0 if result["metrics"]["primary"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
