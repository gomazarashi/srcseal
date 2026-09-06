"""Unit tests for srcseal.archive."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from srcseal import archive
from tests.conftest import fake_symlink, git


def test_list_archive_files_excludes_ignored_paths(sample_repo: Path) -> None:
    assert archive.list_archive_files(sample_repo) == [
        ".gitignore",
        "src/module.py",
        "tracked.py",
        "untracked.md",
    ]


def test_list_archive_files_skips_deleted_tracked_files(sample_repo: Path) -> None:
    (sample_repo / "tracked.py").unlink()
    names = archive.list_archive_files(sample_repo)
    assert "tracked.py" not in names
    assert "src/module.py" in names


def test_list_archive_files_uses_worktree_bytes_for_modified(sample_repo: Path) -> None:
    (sample_repo / "tracked.py").write_text("modified\n", encoding="utf-8")
    assert "tracked.py" in archive.list_archive_files(sample_repo)


def test_list_archive_files_keeps_symlink_candidates(
    sample_repo: Path, tmp_path: Path
) -> None:
    target = sample_repo / "tracked.py"
    link = sample_repo / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("cannot create symlinks on this platform")
    names = archive.list_archive_files(sample_repo)
    assert "link.txt" in names


def test_list_archive_files_handles_space_and_unicode_names(
    sample_repo: Path,
) -> None:
    spaced = sample_repo / "dir with space" / "file with space.txt"
    spaced.parent.mkdir()
    spaced.write_text("spaced\n", encoding="utf-8")
    uni = sample_repo / "ユニコード_テスト.txt"
    uni.write_text("unicode\n", encoding="utf-8")
    names = archive.list_archive_files(sample_repo)
    assert "dir with space/file with space.txt" in names
    assert "ユニコード_テスト.txt" in names


def test_list_archive_files_handles_special_names(sample_repo: Path) -> None:
    # Windows-safe names only.
    special = sample_repo / "weird [brackets] (parens) #hash;.txt"
    special.write_bytes(b"x\n")
    quoted = sample_repo / "quote'single-plus+equals=.txt"
    quoted.write_bytes(b"y\n")
    names = archive.list_archive_files(sample_repo)
    assert "weird [brackets] (parens) #hash;.txt" in names
    assert "quote'single-plus+equals=.txt" in names


def test_get_file_modes_reports_executable_bit(sample_repo: Path) -> None:
    script = sample_repo / "run.sh"
    script.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    git(sample_repo, "add", "run.sh")
    git(sample_repo, "commit", "-m", "add script")
    git(sample_repo, "update-index", "--chmod=+x", "run.sh")
    modes = archive.get_file_modes(sample_repo)
    assert modes["run.sh"] == "100755"
    assert modes["tracked.py"] == "100644"


def test_find_submodules_from_modes() -> None:
    assert archive.find_submodules({"a.txt": "100644", "sub": "160000"}) == ["sub"]
    assert archive.find_submodules({"a.txt": "100644"}) == []


def test_has_uncommitted_changes_true_for_sample_repo(sample_repo: Path) -> None:
    # Dirty by design (untracked file).
    assert archive.has_uncommitted_changes(sample_repo)


def test_has_uncommitted_changes_clean_vs_dirty(clean_repo: Path) -> None:
    assert not archive.has_uncommitted_changes(clean_repo)
    (clean_repo / "a.txt").write_text("changed\n", encoding="utf-8")
    assert archive.has_uncommitted_changes(clean_repo)


def test_find_repo_root_from_subdirectory(sample_repo: Path) -> None:
    subdir = sample_repo / "src"
    assert archive.find_repo_root(subdir) == sample_repo


def test_find_repo_root_rejects_non_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    with pytest.raises(archive.ArchiveError, match="not a git repository"):
        archive.find_repo_root(outside)


def test_validate_archive_name_accepts_simple() -> None:
    assert archive.validate_archive_name("submission") == "submission"
    assert archive.validate_archive_name("my-project_1") == "my-project_1"
    assert archive.validate_archive_name("..foo") == "..foo"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        ".",
        "..",
        "a/b",
        "a\\b",
        "/",
        "/abs",
        "C:/x",
        "C:\\x",
        "../escape",
        "a/../b",
        "with space/sep",
        "semi;colon:name",
        "star*",
        "quest?",
        "less<than",
        "greater>than",
        'double"quote',
        "pipe|char",
        "trailing ",
        "trailing.",
        "nul\x00byte",
        "ctrl\x01char",
    ],
)
def test_validate_archive_name_rejects_dangerous(bad: str) -> None:
    with pytest.raises(archive.ArchiveError):
        archive.validate_archive_name(bad)


def test_resolve_output_dir_explicit_must_exist(tmp_path: Path) -> None:
    with pytest.raises(archive.ArchiveError, match="output directory"):
        archive.resolve_output_dir(tmp_path / "missing")


def test_resolve_output_dir_explicit_file_rejected(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(archive.ArchiveError, match="output directory"):
        archive.resolve_output_dir(f)


def test_resolve_output_dir_explicit_ok(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    assert archive.resolve_output_dir(out) == out


def test_resolve_output_dir_default_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No ~/Downloads here, so CWD is the fallback.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    assert not (tmp_path / "Downloads").exists()
    assert archive.resolve_output_dir(None) == cwd


def test_build_archive_writes_prefixed_entries(
    sample_repo: Path, tmp_path: Path
) -> None:
    out_path = tmp_path / "out" / "sample.zip"
    out_path.parent.mkdir()
    count = archive.build_archive(
        sample_repo,
        archive.list_archive_files(sample_repo),
        out_path,
        prefix="sample-repo",
        file_modes=archive.get_file_modes(sample_repo),
    )
    assert count == 4
    with zipfile.ZipFile(out_path) as zf:
        names = zf.namelist()
        assert "sample-repo/tracked.py" in names
        assert "sample-repo/src/module.py" in names
        assert not any(n.endswith(".log") for n in names)
        assert not any(n.endswith(".env") for n in names)
        expected = (sample_repo / "tracked.py").read_bytes()
        assert zf.read("sample-repo/tracked.py") == expected


def test_build_archive_without_prefix(sample_repo: Path, tmp_path: Path) -> None:
    out_path = tmp_path / "flat.zip"
    archive.build_archive(
        sample_repo,
        archive.list_archive_files(sample_repo),
        out_path,
        prefix="",
        file_modes=archive.get_file_modes(sample_repo),
    )
    with zipfile.ZipFile(out_path) as zf:
        assert "tracked.py" in zf.namelist()


def test_build_archive_refuses_overwrite(sample_repo: Path, tmp_path: Path) -> None:
    out_path = tmp_path / "exists.zip"
    out_path.write_bytes(b"old")
    with pytest.raises(archive.ArchiveError, match="already exists"):
        archive.build_archive(
            sample_repo, ["tracked.py"], out_path, prefix="p", file_modes={}
        )
    assert out_path.read_bytes() == b"old"


def test_build_archive_preserves_git_executable_bit(
    sample_repo: Path, tmp_path: Path
) -> None:
    script = sample_repo / "run.sh"
    script.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    git(sample_repo, "add", "run.sh")
    git(sample_repo, "commit", "-m", "add script")
    git(sample_repo, "update-index", "--chmod=+x", "run.sh")
    out_path = tmp_path / "exec.zip"
    archive.build_archive(
        sample_repo,
        ["run.sh", "tracked.py"],
        out_path,
        prefix="p",
        file_modes=archive.get_file_modes(sample_repo),
    )
    with zipfile.ZipFile(out_path) as zf:
        exec_attr = (zf.getinfo("p/run.sh").external_attr >> 16) & 0o777
        plain_attr = (zf.getinfo("p/tracked.py").external_attr >> 16) & 0o777
    assert exec_attr & 0o111, f"expected exec bit, got {oct(exec_attr)}"
    assert exec_attr & 0o755 == 0o755
    assert plain_attr == 0o644


def test_build_archive_never_follows_symlink(
    sample_repo: Path, tmp_path: Path
) -> None:
    secret_outside = tmp_path / "secret.txt"
    secret_outside.write_bytes(b"TOP-SECRET\n")
    link = sample_repo / "link.txt"
    try:
        link.symlink_to(secret_outside)
    except OSError:
        pytest.skip("cannot create symlinks on this platform")
    out_path = tmp_path / "out.zip"
    with pytest.raises(archive.ArchiveError, match="symlink"):
        archive.build_archive(
            sample_repo, ["link.txt"], out_path, prefix="p", file_modes={}
        )
    # The failed run must not store the symlink target.
    if out_path.exists():
        with zipfile.ZipFile(out_path) as zf:
            for name in zf.namelist():
                assert zf.read(name) != b"TOP-SECRET\n"


def test_build_archive_never_follows_symlink_mock(
    sample_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mock version of the symlink test above."""
    fake_symlink(monkeypatch, sample_repo)
    out_path = tmp_path / "out.zip"
    with pytest.raises(archive.ArchiveError, match="symlink"):
        archive.build_archive(
            sample_repo, ["tracked.py"], out_path, prefix="p", file_modes={}
        )


def test_build_archive_roundtrip_space_and_unicode(
    sample_repo: Path, tmp_path: Path
) -> None:
    spaced = sample_repo / "dir with space" / "file with space.txt"
    spaced.parent.mkdir()
    spaced.write_bytes(b"spaced-bytes\n")
    uni = sample_repo / "ユニコード_テスト.txt"
    uni.write_bytes(b"unicode-bytes\n")
    rels = archive.list_archive_files(sample_repo)
    out_path = tmp_path / "names.zip"
    archive.build_archive(sample_repo, rels, out_path, prefix="p", file_modes={})
    with zipfile.ZipFile(out_path) as zf:
        assert zf.read("p/dir with space/file with space.txt") == b"spaced-bytes\n"
        assert zf.read("p/ユニコード_テスト.txt") == b"unicode-bytes\n"


def test_timestamp_format() -> None:
    ts = archive.timestamp_now()
    assert len(ts) == 15
    assert ts[8] == "_"
    assert ts[:8].isdigit() and ts[9:].isdigit()
    # Valid month.
    assert 1 <= int(ts[4:6]) <= 12
