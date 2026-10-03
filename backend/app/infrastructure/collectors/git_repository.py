"""本地 Git 仓库采集器：把仓库工作区转换成确定性 SourceManifest。

口径（ADR-010 / ADR-011）：
- 文件枚举交给 git（`ls-files --cached --others --exclude-standard`），
  不自行实现 .gitignore 解析，保证 ignore 语义单一真源；
- 读取工作区字节，CRLF→LF 归一后计算 SHA-256；
- 输出路径为仓库根相对 POSIX 路径，大小写保留，不做 Unicode 归一化；
- 局部失败不中断整体采集，统一经 CollectOutcome 通道返回。
"""

import asyncio
import hashlib
import os
import subprocess
from pathlib import Path

from app.application.scans.models import (
    CollectOutcome,
    ScanError,
    ScanErrorCode,
    ScanErrorSeverity,
    ScanRequest,
    ScanStage,
    SourceFile,
    SourceManifest,
)

LANGUAGE_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "python": (".py",),
}

_GIT_TIMEOUT_SECONDS = 60


class _GitUnavailableError(Exception):
    """git 可执行文件缺失或命令超时。"""


class _GitCommandError(Exception):
    """git 命令返回非零退出码。"""


class GitRepositoryCollector:
    """RepositoryCollector 的本地 Git 实现。

    扫描边界为 `git rev-parse --show-toplevel` 确定的仓库根：**请求必须是仓库根**，
    子目录会被拒绝（组合方可用 `resolve_repository_root` 先归一）；
    子模块（gitlink 目录项）不参与采集。
    """

    async def collect(self, request: ScanRequest) -> CollectOutcome:
        """异步外壳；git 与文件 IO 在线程中执行，不阻塞事件循环。"""
        return await asyncio.to_thread(self._collect_sync, request)

    def _collect_sync(self, request: ScanRequest) -> CollectOutcome:
        path = request.path
        if not path.is_dir():
            return _fatal(f"路径不存在或不是目录: {path}", ScanErrorCode.PATH_INVALID)

        try:
            root = Path(_run_git(path, "rev-parse", "--show-toplevel")).resolve()
        except _GitUnavailableError as error:
            return _fatal(str(error), ScanErrorCode.GIT_ERROR)
        except _GitCommandError as error:
            return _fatal(f"不是可用的 Git 仓库（{path}）: {error}", ScanErrorCode.PATH_INVALID)

        # 管道不变量：request.path 必须为仓库根——manifest 路径相对该根，
        # 下游 Analyzer 不做子目录推导，这里 fail-fast 拦截
        if str(root).casefold() != str(path.resolve()).casefold():
            return _fatal(
                f"请指向仓库根而不是子目录: {path}（仓库根为 {root}）",
                ScanErrorCode.PATH_INVALID,
            )

        try:
            revision = _run_git(root, "rev-parse", "HEAD")
            worktree_dirty = bool(_run_git_bytes(root, "status", "--porcelain").strip())
            listed = _run_git_bytes(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        except (_GitUnavailableError, _GitCommandError) as error:
            return _fatal(f"git 采集失败: {error}", ScanErrorCode.GIT_ERROR)

        extensions = _extensions_for(request.languages)
        errors: list[ScanError] = []
        files: list[SourceFile] = []
        for entry in sorted(part for part in listed.split(b"\0") if part):
            try:
                path_text = entry.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(_local_error(ScanErrorCode.FILE_ENCODING, f"文件名无法按 UTF-8 解码: {entry!r}"))
                continue
            if not path_text.endswith(extensions):
                continue
            collected = _collect_file(root, path_text, errors)
            if collected is not None:
                files.append(collected)

        manifest = SourceManifest(
            repository_id=request.repository_id,
            revision=revision,
            worktree_dirty=worktree_dirty,
            files=tuple(files),
        )
        return CollectOutcome(manifest=manifest, errors=tuple(errors))


def resolve_repository_root(path: Path) -> Path | None:
    """把路径解析为所在 Git 仓库的根（toplevel）；不在仓库内或 git 不可用时返回 None。

    供流水线组合方（CLI / 未来的 API 层）在接受用户输入后归一
    `ScanRequest.path` 使用；SourceManifest 中的路径均相对该仓库根。
    """
    try:
        return Path(_run_git(path, "rev-parse", "--show-toplevel")).resolve()
    except (_GitUnavailableError, _GitCommandError):
        return None


def _extensions_for(languages: tuple[str, ...]) -> tuple[str, ...]:
    """把语言标识展开为扩展名集合；未知语言不匹配任何文件。"""
    extensions: list[str] = []
    for language in languages:
        extensions.extend(LANGUAGE_EXTENSIONS.get(language, ()))
    return tuple(extensions)


def _collect_file(root: Path, path_text: str, errors: list[ScanError]) -> SourceFile | None:
    """采集单个文件；任何局部失败登记错误并返回 None，不中断整体。"""
    full_path = root / path_text
    if os.path.islink(full_path):
        resolved = full_path.resolve()
        if not resolved.is_relative_to(root):
            errors.append(
                _local_error(
                    ScanErrorCode.SYMLINK_REJECTED,
                    f"软链接越出仓库根，已拒绝: {path_text} -> {resolved}",
                    file_path=path_text,
                )
            )
            return None
    elif full_path.is_dir():
        # 子模块（gitlink）等目录项不是文件事实，跳过
        return None

    try:
        data = full_path.read_bytes()
    except FileNotFoundError:
        errors.append(_local_error(ScanErrorCode.FILE_DISAPPEARED, "文件在采集期间消失", file_path=path_text))
        return None
    except OSError as error:
        errors.append(_local_error(ScanErrorCode.FILE_UNREADABLE, f"文件无法读取: {error}", file_path=path_text))
        return None

    normalized = data.replace(b"\r\n", b"\n")
    try:
        normalized.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(_local_error(ScanErrorCode.FILE_ENCODING, "内容不是有效 UTF-8", file_path=path_text))
        return None

    content_hash = f"sha256:{hashlib.sha256(normalized).hexdigest()}"
    return SourceFile(path=path_text, content_hash=content_hash)


def _local_error(code: ScanErrorCode, message: str, file_path: str | None = None) -> ScanError:
    return ScanError(
        stage=ScanStage.COLLECT,
        code=code,
        severity=ScanErrorSeverity.LOCAL,
        message=message,
        file_path=file_path,
    )


def _fatal(message: str, code: ScanErrorCode) -> CollectOutcome:
    return CollectOutcome(
        errors=(
            ScanError(
                stage=ScanStage.COLLECT,
                code=code,
                severity=ScanErrorSeverity.FATAL,
                message=message,
            ),
        )
    )


def _run_git(cwd: Path, *args: str) -> str:
    """执行 git 命令，返回 UTF-8 解码并去除首尾空白的输出。"""
    return _run_git_bytes(cwd, *args).decode("utf-8").strip()


def _run_git_bytes(cwd: Path, *args: str) -> bytes:
    """执行 git 命令并返回原始字节输出；失败抛出内部异常。"""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as error:
        raise _GitUnavailableError("未找到 git 可执行文件") from error
    except subprocess.TimeoutExpired as error:
        raise _GitUnavailableError(f"git {args[0]} 执行超时") from error
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise _GitCommandError(f"git {args[0]} 失败: {message}")
    return result.stdout
