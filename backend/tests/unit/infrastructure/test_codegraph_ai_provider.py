"""CodeGraphAI Provider 的 CLI 契约、宽容解析与失败显式化测试。"""

import hashlib
import json
import subprocess
from pathlib import Path

from app.infrastructure.code_intelligence.providers.codegraph_ai import CodeGraphAIProvider


def test_probe_records_version_and_binary_hash(tmp_path: Path, monkeypatch: object) -> None:
    executable = tmp_path / "codegraph.exe"
    executable.write_bytes(b"fixed-binary")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, stdout="codegraph-server v0.20.1 (abc)\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)  # type: ignore[attr-defined]
    status = CodeGraphAIProvider(executable).probe(tmp_path)

    assert status.available is True
    assert status.version == "codegraph-server v0.20.1 (abc)"
    assert status.asset_hash == "sha256:" + hashlib.sha256(b"fixed-binary").hexdigest()


def test_calls_use_real_one_based_line_and_skip_invalid_records(tmp_path: Path, monkeypatch: object) -> None:
    executable = tmp_path / "codegraph.exe"
    executable.write_bytes(b"binary")
    source = tmp_path / "app" / "main.py"
    source.parent.mkdir()
    source.write_text("def run():\n    pass\n", encoding="utf-8")
    captured: list[str] = []
    payload = {
        "root": "1",
        "root_node": {
            "id": "1",
            "name": "run",
            "path": str(source),
            "line_start": 1,
            "line_end": 2,
        },
        "nodes": [
            {"id": "2", "name": "target", "path": str(source), "line_start": 5, "line_end": 6},
            {"id": "broken"},
        ],
        "edges": [
            {"from": "1", "to": "2", "type": "calls"},
            {"from": "1", "type": "calls"},
        ],
    }

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.extend(command)
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="diagnostic")

    monkeypatch.setattr(subprocess, "run", fake_run)  # type: ignore[attr-defined]
    result = CodeGraphAIProvider(executable).calls_for_symbol(tmp_path, "app/main.py", 7)

    assert result.error is None
    assert result.graph is not None
    assert result.invalid_records == 2
    tool_args = json.loads(captured[captured.index("--tool-args") + 1])
    assert tool_args["line"] == 7
    assert tool_args["depth"] == 1
    assert result.graph.edges[0].from_id == "1"


def test_missing_binary_is_unavailable(tmp_path: Path) -> None:
    status = CodeGraphAIProvider(tmp_path / "missing.exe").probe(tmp_path)

    assert status.available is False
    assert status.reason is not None
    assert "不存在" in status.reason


def test_diagnostic_only_empty_response_is_a_valid_empty_graph(tmp_path: Path, monkeypatch: object) -> None:
    executable = tmp_path / "codegraph.exe"
    executable.write_bytes(b"binary")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        payload = {"diagnostic": {"node_found": False}, "nodes": [], "edges": []}
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)  # type: ignore[attr-defined]
    result = CodeGraphAIProvider(executable).calls_for_symbol(tmp_path, "missing.py", 1)

    assert result.error is None
    assert result.graph is not None
    assert result.graph.root == ""
    assert result.invalid_records == 1
