"""Temp Git repos for tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_INHERITED_GIT_ENV_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_COMMON_DIR",
)


@pytest.fixture(autouse=True)
def _isolate_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _INHERITED_GIT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def git(repo: Path, *args: str) -> None:
    """Run git in *repo*."""
    subprocess.run(("git", *args), cwd=repo, check=True, capture_output=True)


def init_repo(repo: Path) -> Path:
    """New repo with local test identity."""
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "commit.gpgsign", "false")
    return repo


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Tracked + untracked + ignored files."""
    repo = init_repo(tmp_path / "sample-repo")
    (repo / ".gitignore").write_text("ignored/\n*.log\n.env\n", encoding="utf-8")
    (repo / "tracked.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "module.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", ".gitignore", "tracked.py", "src/module.py")
    git(repo, "commit", "-m", "init")
    (repo / "untracked.md").write_text("# memo\n", encoding="utf-8")
    (repo / "debug.log").write_text("log\n", encoding="utf-8")
    (repo / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (repo / "ignored").mkdir()
    (repo / "ignored" / "cache.bin").write_bytes(b"\x00")
    return repo


@pytest.fixture
def clean_repo(tmp_path: Path) -> Path:
    """Committed repo, no changes."""
    repo = init_repo(tmp_path / "clean-repo")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-m", "init")
    return repo


def fake_symlink(
    monkeypatch: pytest.MonkeyPatch, repo: Path, name: str = "tracked.py"
) -> None:
    """Fake a symlink (no privilege needed)."""
    orig = Path.is_symlink

    def fake_is_symlink(self: Path) -> bool:
        try:
            if self.name == name and self.resolve().parent == repo.resolve():
                return True
        except OSError:
            pass
        return orig(self)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)
