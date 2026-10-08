"""CodeGraph 的 JSON Artifact 持久化适配器。

设计口径（ADR-006 + 步骤 6 访问模式清单，见 docs/architecture/数据模型.md §3.1）：

- **内容**：Artifact 是 CodeGraph 的规范序列化（`model_dump_json(indent=2)` + 结尾换行），
  与 `tests/unit/domain/test_serialization_stability.py::_canonical` 以及采集 / 分析 CLI 的
  `--json` 输出同口径；因此产物可直接交给 `eval/codegraph/validate.py` 校验。
- **定位键**：`(repository_id, revision)`，与 `CodeGraphRepository` 端口签名一致。
- **路径布局**：`<root>/<repository_id>/<revision>.json`。`repository_id` 必须满足 ADR-010
  （非空且不含 `:`）；本适配器另外拒绝路径分隔符与 `.` / `..`，防止越出 artifact 根目录。
- **原子写入**：先写同目录临时文件并 `fsync`，再 `os.replace` 原子替换。进程中断只会留下
  临时文件，不会留下「看起来完整、实际是半截」的 Artifact。
- **完整性**：内容哈希以 sidecar `<revision>.json.sha256` 落盘；读取时若 sidecar 存在则校验，
  不匹配即拒绝（绝不把损坏的图当成功返回）；sidecar 缺失时跳过校验（例如人工只拷贝了 .json）。
- **冲突策略未定**：同一 `(repository_id, revision)` 重复 save 如何处理，是
  `docs/architecture/数据模型.md` §5.1 / §5.2 的待评审项，本适配器**不预设**——
  当前行为是后写覆盖；调用方可用 `render_artifact` + `artifact_digest` 先比对再决定。
"""

import asyncio
import hashlib
import os
from pathlib import Path

from app.domain.codegraph.ids import validate_repository_id
from app.domain.codegraph.models import CodeGraph

ARTIFACT_SUFFIX = ".json"
DIGEST_SUFFIX = ".sha256"

_TEMP_SUFFIX = ".tmp"


class ArtifactRepositoryError(RuntimeError):
    """Artifact 读写失败。

    调用方负责映射为领域错误（如 `ScanErrorCode.STORAGE_ERROR`）；
    本层不依赖 application 层模型，保持基础设施的独立可测性。
    """


def render_artifact(graph: CodeGraph) -> bytes:
    """把 CodeGraph 渲染为规范 Artifact 字节序列。

    确定性保证：同一领域对象两次渲染字节完全相同（Pydantic 按字段声明序输出，
    nodes / edges 的顺序由 ADR-010 的确定性纪律保证）。
    """
    return (graph.model_dump_json(indent=2) + "\n").encode("utf-8")


def artifact_digest(payload: bytes) -> str:
    """Artifact 内容哈希；格式与领域层 content_hash 一致：`sha256:<64 位小写十六进制>`。"""
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class JsonCodeGraphRepository:
    """以规范化 JSON Artifact 实现 `CodeGraphRepository` 端口。

    构造参数显式传入根目录，不读全局配置——便于测试隔离，也避免基础设施层依赖单例状态。
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        """Artifact 根目录（只读，供调用方与排障使用）。"""
        return self._root

    def artifact_path(self, repository_id: str, revision: str) -> Path:
        """返回某个 Artifact 的落盘路径（同时完成入参校验）。"""
        return self._artifact_path(repository_id, revision)

    async def save(self, graph: CodeGraph) -> None:
        """原子写入 Artifact 及其内容哈希 sidecar。"""
        await asyncio.to_thread(self._save_sync, graph)

    async def get(self, repository_id: str, revision: str) -> CodeGraph | None:
        """读取 Artifact；不存在返回 None，存在但损坏 / 哈希不符则抛错。"""
        return await asyncio.to_thread(self._get_sync, repository_id, revision)

    # ---------- 同步实现（经 asyncio.to_thread 调用，避免阻塞事件循环） ----------

    def _save_sync(self, graph: CodeGraph) -> None:
        payload = render_artifact(graph)
        artifact = self._artifact_path(graph.repository_id, graph.revision)
        artifact.parent.mkdir(parents=True, exist_ok=True)

        # 先写内容，再写哈希：中断在两者之间时，读取会因为 sidecar 缺失而跳过校验，
        # 而不是拿一个对不上的哈希去误判完整产物。
        _atomic_write(artifact, payload)
        _atomic_write(_digest_path(artifact), f"{artifact_digest(payload)}\n".encode())

    def _get_sync(self, repository_id: str, revision: str) -> CodeGraph | None:
        artifact = self._artifact_path(repository_id, revision)
        if not artifact.is_file():
            return None

        payload = artifact.read_bytes()
        digest_path = _digest_path(artifact)
        if digest_path.is_file():
            expected = digest_path.read_text(encoding="utf-8").strip()
            actual = artifact_digest(payload)
            if actual != expected:
                raise ArtifactRepositoryError(f"Artifact 内容哈希不匹配：{artifact}（期望 {expected}，实际 {actual}）")

        try:
            return CodeGraph.model_validate_json(payload)
        except ValueError as error:
            raise ArtifactRepositoryError(f"Artifact 无法解析为 CodeGraph：{artifact}（{error}）") from error

    def _artifact_path(self, repository_id: str, revision: str) -> Path:
        try:
            validate_repository_id(repository_id)
        except ValueError as error:
            raise ArtifactRepositoryError(f"repository_id 非法：{repository_id!r}（{error}）") from error
        # ADR-010 只约束了 ":"；路径安全由本层负责，避免越出 artifact 根目录。
        _reject_unsafe_path_part("repository_id", repository_id)
        _reject_unsafe_path_part("revision", revision)
        return self._root / repository_id / f"{revision}{ARTIFACT_SUFFIX}"


def _digest_path(artifact: Path) -> Path:
    """sidecar 路径：`<revision>.json` → `<revision>.json.sha256`。"""
    return artifact.parent / (artifact.name + DIGEST_SUFFIX)


def _reject_unsafe_path_part(field: str, value: str) -> None:
    """拒绝会越出 artifact 根目录或破坏扁平布局的取值。"""
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ArtifactRepositoryError(f"{field} 非法（不得为空、为点或双点、或含路径分隔符）：{value!r}")


def _atomic_write(target: Path, payload: bytes) -> None:
    """同目录临时文件 → fsync → 原子替换；失败时清理临时文件。"""
    temp = target.parent / (target.name + _TEMP_SUFFIX)
    try:
        with temp.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    except OSError as error:
        temp.unlink(missing_ok=True)
        raise ArtifactRepositoryError(f"写入 Artifact 失败：{target}（{error}）") from error
