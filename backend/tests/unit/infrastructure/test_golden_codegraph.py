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


@pytest.mark.parametrize("case_name", ["golden-python-basic", "golden-python-calls"])
def test_golden_cases_match_expected_graph_semantically(case_name: str) -> None:
    evaluator = _load_evaluator()

    result = evaluator.run_case(case_name)
    metrics = result["metrics"]

    assert metrics["node_recall"] == 1.0, metrics["missing_nodes"][:5]
    assert metrics["node_precision"] == 1.0, metrics["extra_nodes"][:5]
    assert metrics["edge_recall"] == 1.0, metrics["missing_edges"][:5]
    assert metrics["edge_precision"] == 1.0, metrics["extra_edges"][:5]
    assert metrics["calls_recall"] == 1.0
    assert metrics["calls_precision"] == 1.0
    assert metrics["entry_recall"] == 1.0
    assert metrics["entry_precision"] == 1.0
    assert metrics["primary"] == 1.0


def test_historical_v1_baseline_is_preserved() -> None:
    evaluator = _load_evaluator()

    baseline_path = evaluator.BASELINES_DIR / "codegraph-parser-v1.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    assert baseline["dataset_version"] == "eval-v1"
    assert baseline["model_or_algorithm"] == "python-ast/0.1"
    assert baseline["metrics"]["primary"] == 1.0


def test_v2_baseline_matches_calls_metrics_when_created() -> None:
    evaluator = _load_evaluator()
    baseline_path = evaluator.BASELINES_DIR / "codegraph-parser-v2.json"
    if not baseline_path.exists():
        pytest.skip("Baseline v2 必须在实现提交后独立生成")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    result = evaluator.run_case("golden-python-calls")

    assert result["metrics"]["primary"] == baseline["metrics"]["primary"] == 1.0
    assert result["metrics"]["calls_recall"] == baseline["metrics"]["calls_recall"] == 1.0
    assert result["metrics"]["calls_precision"] == baseline["metrics"]["calls_precision"] == 1.0
