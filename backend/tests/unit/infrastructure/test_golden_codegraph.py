"""Golden Dataset 回归：eval/codegraph 评测入口必须保持 100% 语义匹配。"""

import importlib.util
import json
import types
from pathlib import Path

import pytest

_EVALUATOR_PATH = Path(__file__).resolve().parents[4] / "eval" / "codegraph" / "evaluator.py"


def _load_evaluator() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("codegraph_evaluator", _EVALUATOR_PATH)
    assert spec is not None and spec.loader is not None, "无法加载 eval/codegraph/evaluator.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_golden_case_matches_expected_graph_semantically() -> None:
    evaluator = _load_evaluator()

    result = evaluator.run_case("golden-python-basic")
    metrics = result["metrics"]

    assert metrics["node_recall"] == 1.0, metrics["missing_nodes"][:5]
    assert metrics["node_precision"] == 1.0, metrics["extra_nodes"][:5]
    assert metrics["edge_recall"] == 1.0, metrics["missing_edges"][:5]
    assert metrics["edge_precision"] == 1.0, metrics["extra_edges"][:5]
    assert metrics["primary"] == 1.0


def test_baseline_matches_current_metrics() -> None:
    evaluator = _load_evaluator()

    baseline_path = evaluator.BASELINES_DIR / "codegraph-parser-v1.json"
    if not baseline_path.exists():
        pytest.skip("baseline 尚未创建（首次运行 evaluator --write-baseline 后生效）")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    result = evaluator.run_case("golden-python-basic")

    assert result["metrics"]["primary"] == baseline["metrics"]["primary"] == 1.0
