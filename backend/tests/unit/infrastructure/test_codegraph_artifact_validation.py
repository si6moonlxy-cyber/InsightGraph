"""CodeGraph 产物不变量校验：正向（golden 工件 + 实时产出图）与反向（三类违例必须被捕获）。"""

import importlib.util
import json
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
_VALIDATE_PATH = _ROOT / "eval" / "codegraph" / "validate.py"
_EVALUATOR_PATH = _ROOT / "eval" / "codegraph" / "evaluator.py"
_CASE_DIR = _ROOT / "eval" / "codegraph" / "cases" / "golden-python-basic"


def _load_module(path: Path, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"无法加载 {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _golden_artifact() -> dict:
    data = json.loads((_CASE_DIR / "expected_codegraph.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_golden_artifact_passes_invariants() -> None:
    validator = _load_module(_VALIDATE_PATH, "codegraph_validate")

    assert validator.validate_artifact(_golden_artifact(), _CASE_DIR / "repo") == []


def test_produced_graph_passes_invariants() -> None:
    validator = _load_module(_VALIDATE_PATH, "codegraph_validate")
    evaluator = _load_module(_EVALUATOR_PATH, "codegraph_evaluator")

    result = evaluator.run_case("golden-python-basic")
    artifact = json.loads(result["graph"].model_dump_json())

    assert validator.validate_artifact(artifact, _CASE_DIR / "repo") == []


def test_missing_defines_edge_is_caught() -> None:
    validator = _load_module(_VALIDATE_PATH, "codegraph_validate")
    artifact = _golden_artifact()
    kinds = {node["id"]: node["kind"] for node in artifact["nodes"]}
    class_edges = [
        edge for edge in artifact["edges"] if edge["kind"] == "defines" and kinds[edge["target_id"]] == "class"
    ]
    assert class_edges, "golden 工件应包含 class 的 DEFINES 边"
    removed = class_edges[0]
    artifact["edges"] = [edge for edge in artifact["edges"] if edge is not removed]

    violations = validator.validate_artifact(artifact, _CASE_DIR / "repo")

    assert any(v.startswith("[defines]") and removed["target_id"] in v for v in violations)


def test_hash_mismatch_is_caught() -> None:
    validator = _load_module(_VALIDATE_PATH, "codegraph_validate")
    artifact = _golden_artifact()
    target = artifact["nodes"][0]
    original = target["content_hash"]
    target["content_hash"] = original[:-1] + ("0" if original[-1] != "0" else "1")

    violations = validator.validate_artifact(artifact, _CASE_DIR / "repo")

    assert any(v.startswith("[hash]") and target["id"] in v for v in violations)


def test_imports_target_must_be_module_node() -> None:
    validator = _load_module(_VALIDATE_PATH, "codegraph_validate")
    artifact = _golden_artifact()
    class_id = next(node["id"] for node in artifact["nodes"] if node["kind"] == "class")
    imports_edge = next(edge for edge in artifact["edges"] if edge["kind"] == "imports")
    imports_edge["target_id"] = class_id

    violations = validator.validate_artifact(artifact, _CASE_DIR / "repo")

    assert any(v.startswith("[imports]") and imports_edge["id"] in v for v in violations)
