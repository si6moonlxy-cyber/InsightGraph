"""codegraph-ai/CodeGraph 的 headless one-shot Provider。"""

import hashlib
import json
import logging
import subprocess
from pathlib import Path

from app.infrastructure.code_intelligence.models import ProviderStatus
from app.infrastructure.code_intelligence.providers.engine_port import ProviderCallResult
from app.infrastructure.code_intelligence.raw_models.relation import RawCallGraph

_LOGGER = logging.getLogger(__name__)
_TOOL_NAME = "codegraph_get_call_graph"


class CodeGraphAIProvider:
    """以无 shell 的 subprocess 调用固定路径 CodeGraphAI 二进制。"""

    name = "codegraph-ai/CodeGraph"

    def __init__(self, executable: Path, timeout_seconds: int = 30) -> None:
        self._executable = executable
        self._timeout_seconds = timeout_seconds

    def probe(self, root: Path) -> ProviderStatus:
        if not root.is_dir():
            return ProviderStatus.unavailable(f"仓库根目录不可用: {root}")
        if not self._executable.is_file():
            return ProviderStatus.unavailable(f"引擎二进制不存在: {self._executable}")
        try:
            completed = self._run(["--info"])
        except (OSError, subprocess.TimeoutExpired) as error:
            return ProviderStatus.unavailable(f"引擎探测失败: {error}")
        if completed.returncode != 0:
            return ProviderStatus.unavailable(f"引擎 --info 退出码 {completed.returncode}")
        first_line = next((line.strip() for line in completed.stdout.splitlines() if line.strip()), "")
        if not first_line:
            return ProviderStatus.unavailable("引擎 --info 未返回版本")
        return ProviderStatus(
            available=True,
            version=first_line,
            asset_hash=_sha256_file(self._executable),
        )

    def calls_for_symbol(self, root: Path, file_rel: str, line_1based: int) -> ProviderCallResult:
        tool_args = json.dumps(
            {"uri": (root / file_rel).resolve().as_uri(), "line": line_1based, "depth": 1},
            separators=(",", ":"),
            sort_keys=True,
        )
        command = [
            "--workspace",
            str(root),
            "--graph-only",
            "--run-tool",
            _TOOL_NAME,
            "--tool-args",
            tool_args,
        ]
        try:
            completed = self._run(command)
        except subprocess.TimeoutExpired:
            return ProviderCallResult(error=f"{_TOOL_NAME} 超时（{self._timeout_seconds}s）")
        except OSError as error:
            return ProviderCallResult(error=f"{_TOOL_NAME} 启动失败: {error}")
        if completed.returncode != 0:
            return ProviderCallResult(error=f"{_TOOL_NAME} 退出码 {completed.returncode}")
        try:
            payload = json.loads(completed.stdout)
            if not isinstance(payload, dict):
                raise ValueError("顶层 JSON 不是对象")
            graph, invalid = RawCallGraph.parse_lossy(payload)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            return ProviderCallResult(error=f"{_TOOL_NAME} 响应无效: {error}")
        if completed.stderr:
            _LOGGER.debug("CodeGraphAI stderr: %s", completed.stderr.strip())
        return ProviderCallResult(graph, invalid_records=invalid)

    def _run(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self._executable), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self._timeout_seconds,
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
