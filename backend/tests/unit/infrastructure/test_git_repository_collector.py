"""GitRepositoryCollector 的确定性、过滤与错误隔离测试（真实临时 Git 仓库）。"""

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from app.application.scans.models import CollectOutcome, ScanErrorCode, ScanErrorSeverity, ScanRequest
from app.infrastructure.collectors import GitRepositoryCollector

_SHA256_PREFIX = "sha256:"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _write(repo: Path, relative: str, content: str | bytes) -> Path:
    file_path = repo / relative
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        file_path.write_bytes(content)
    else:
        file_path.write_text(content, encoding="utf-8", newline="")
    return file_path


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "config", "commit.gpgsign", "false")


def _make_repo(base: Path, files: dict[str, str | bytes], *, commit: bool = True) -> Path:
    repo = base / "repo"
    _init_repo(repo)
    for relative, content in files.items():
        _write(repo, relative, content)
    if commit:
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "init", "--no-verify")
    return repo


def _symlink_or_skip(link: Path, target: str | Path) -> None:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"当前环境不支持创建符号链接: {error}")


async def _scan(path: Path, repository_id: str = "repo") -> CollectOutcome:
    request = ScanRequest(repository_id=repository_id, path=path)
    return await GitRepositoryCollector().collect(request)


@pytest.mark.asyncio
async def test_same_revision_yields_identical_manifest(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, {"a.py": "print('a')\n", "pkg/b.py": "x = 1\n"})

    first = await _scan(repo)
    second = await _scan(repo)

    assert first.manifest is not None
    assert first.errors == ()
    assert first.manifest == second.manifest
    assert first.manifest.worktree_dirty is False


@pytest.mark.asyncio
async def test_manifest_collects_only_python_files_sorted(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, {"zeta.py": "", "alpha.py": "", "pkg/mid.py": "", "README.md": "x"})

    outcome = await _scan(repo)

    assert outcome.manifest is not None
    assert [source.path for source in outcome.manifest.files] == ["alpha.py", "pkg/mid.py", "zeta.py"]


@pytest.mark.asyncio
async def test_gitignore_venv_and_build_products_are_excluded(tmp_path: Path) -> None:
    repo = _make_repo(
        tmp_path,
        {
            ".gitignore": "ignored.py\n.venv/\nbuild/\n",
            "kept.py": "ok = True\n",
            "ignored.py": "no = True\n",
            ".venv/lib/mod.py": "x = 1\n",
            "build/artifact.py": "x = 1\n",
        },
    )

    outcome = await _scan(repo)

    assert outcome.manifest is not None
    assert [source.path for source in outcome.manifest.files] == ["kept.py"]


@pytest.mark.asyncio
async def test_worktree_dirty_flag_and_untracked_file(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, {"a.py": "x = 1\n"})
    clean = await _scan(repo)
    assert clean.manifest is not None
    assert clean.manifest.worktree_dirty is False

    _write(repo, "a.py", "x = 2\n")
    _write(repo, "new_file.py", "y = 1\n")

    dirty = await _scan(repo)

    assert dirty.manifest is not None
    assert dirty.manifest.worktree_dirty is True
    assert "new_file.py" in [source.path for source in dirty.manifest.files]


@pytest.mark.asyncio
async def test_crlf_is_normalized_before_hashing(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, {"crlf.py": b"a\r\nb\r\n"})

    outcome = await _scan(repo)

    assert outcome.manifest is not None
    content_hash = outcome.manifest.files[0].content_hash
    assert content_hash == _SHA256_PREFIX + hashlib.sha256(b"a\nb\n").hexdigest()
    assert content_hash != _SHA256_PREFIX + hashlib.sha256(b"a\r\nb\r\n").hexdigest()


@pytest.mark.asyncio
async def test_unicode_filename_is_preserved(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, {"模块/主逻辑.py": "x = 1\n"})

    outcome = await _scan(repo)

    assert outcome.manifest is not None
    assert [source.path for source in outcome.manifest.files] == ["模块/主逻辑.py"]


@pytest.mark.asyncio
async def test_deleted_tracked_file_is_local_error_without_abort(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, {"keep.py": "x = 1\n", "gone.py": "y = 1\n"})
    (repo / "gone.py").unlink()

    outcome = await _scan(repo)

    assert outcome.manifest is not None
    assert [source.path for source in outcome.manifest.files] == ["keep.py"]
    assert [error.code for error in outcome.errors] == [ScanErrorCode.FILE_DISAPPEARED]
    assert outcome.errors[0].file_path == "gone.py"


@pytest.mark.asyncio
async def test_invalid_utf8_is_encoding_error_and_skipped(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, {"ok.py": "x = 1\n", "bad.py": b"\xff\xfe\x00bad"})

    outcome = await _scan(repo)

    assert outcome.manifest is not None
    assert [source.path for source in outcome.manifest.files] == ["ok.py"]
    assert [error.code for error in outcome.errors] == [ScanErrorCode.FILE_ENCODING]


@pytest.mark.asyncio
async def test_symlink_escaping_repo_root_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("secret = 1\n", encoding="utf-8")
    repo = _make_repo(tmp_path, {"keep.py": "x = 1\n"})
    _symlink_or_skip(repo / "escape.py", outside)

    outcome = await _scan(repo)

    assert outcome.manifest is not None
    assert [source.path for source in outcome.manifest.files] == ["keep.py"]
    assert [error.code for error in outcome.errors] == [ScanErrorCode.SYMLINK_REJECTED]
    assert outcome.errors[0].file_path == "escape.py"


@pytest.mark.asyncio
async def test_internal_symlink_is_followed(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, {"real.py": "value = 1\n"})
    _symlink_or_skip(repo / "alias.py", "real.py")

    outcome = await _scan(repo)

    assert outcome.manifest is not None
    hashes = {source.path: source.content_hash for source in outcome.manifest.files}
    assert set(hashes) == {"alias.py", "real.py"}
    assert hashes["alias.py"] == hashes["real.py"]


@pytest.mark.asyncio
async def test_subdirectory_path_resolves_to_repository_root(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, {"pkg/mod.py": "x = 1\n", "root.py": "y = 1\n"})

    outcome = await _scan(repo / "pkg")

    assert outcome.manifest is not None
    assert [source.path for source in outcome.manifest.files] == ["pkg/mod.py", "root.py"]


@pytest.mark.asyncio
async def test_missing_path_is_fatal(tmp_path: Path) -> None:
    outcome = await _scan(tmp_path / "nope")

    assert outcome.manifest is None
    assert [error.code for error in outcome.errors] == [ScanErrorCode.PATH_INVALID]
    assert outcome.errors[0].severity is ScanErrorSeverity.FATAL


@pytest.mark.asyncio
async def test_non_repo_directory_is_fatal(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    outcome = await _scan(plain)

    assert outcome.manifest is None
    assert [error.code for error in outcome.errors] == [ScanErrorCode.PATH_INVALID]


@pytest.mark.asyncio
async def test_repo_without_commit_is_fatal(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, {"a.py": "x = 1\n"}, commit=False)

    outcome = await _scan(repo)

    assert outcome.manifest is None
    assert [error.code for error in outcome.errors] == [ScanErrorCode.GIT_ERROR]


@pytest.mark.asyncio
async def test_empty_repository_with_commit_has_empty_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    _init_repo(repo)
    _git(repo, "commit", "--allow-empty", "-m", "init", "--no-verify")

    outcome = await _scan(repo)

    assert outcome.manifest is not None
    assert outcome.manifest.files == ()
    assert outcome.errors == ()
    assert outcome.manifest.worktree_dirty is False
