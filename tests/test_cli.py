"""CLI tests for srcseal."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import srcseal.archive
from srcseal import cli
from tests.conftest import fake_symlink, git


def _zips_in(directory: Path, pattern: str = "*.zip") -> list[Path]:
    return sorted(directory.glob(pattern))


def test_bare_invocation_prints_help_and_creates_no_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    code = cli.main([])
    assert code == 0
    out = capsys.readouterr()
    assert "usage" in out.out.lower()
    assert _zips_in(tmp_path) == []


def test_help_flag_exits_zero(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_short_help_flag() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["-h"])
    assert exc.value.code == 0


def test_main_creates_archive_with_default_prefix(
    sample_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(sample_repo)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([".", "--output-dir", str(out_dir)]) == 0
    created = _zips_in(out_dir, "sample-repo_*.zip")
    assert len(created) == 1
    stem_ts = created[0].stem.removeprefix("sample-repo_")
    assert len(stem_ts) == 15 and stem_ts[8] == "_"
    with zipfile.ZipFile(created[0]) as zf:
        assert "sample-repo/tracked.py" in zf.namelist()
        assert "sample-repo/untracked.md" in zf.namelist()


def test_main_accepts_other_repo_path(
    sample_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out_dir)]) == 0
    created = _zips_in(out_dir, "sample-repo_*.zip")
    assert len(created) == 1
    with zipfile.ZipFile(created[0]) as zf:
        assert "sample-repo/tracked.py" in zf.namelist()


def test_main_resolves_subdirectory_to_repo_root(
    sample_repo: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([str(sample_repo / "src"), "--output-dir", str(out_dir)]) == 0
    created = _zips_in(out_dir, "sample-repo_*.zip")
    assert len(created) == 1
    with zipfile.ZipFile(created[0]) as zf:
        # Whole repo, not just the subdir.
        assert "sample-repo/tracked.py" in zf.namelist()
        assert "sample-repo/src/module.py" in zf.namelist()


def test_main_includes_tracked_and_untracked_excludes_ignored(
    sample_repo: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out_dir)]) == 0
    created = _zips_in(out_dir, "sample-repo_*.zip")
    with zipfile.ZipFile(created[0]) as zf:
        names = zf.namelist()
    assert "sample-repo/tracked.py" in names
    assert "sample-repo/untracked.md" in names
    assert not any(n.endswith("debug.log") for n in names)
    assert not any(n.endswith(".env") for n in names)
    assert not any("/ignored/" in n or n.endswith("ignored/cache.bin") for n in names)


def test_main_archives_modified_worktree_content(
    sample_repo: Path, tmp_path: Path
) -> None:
    (sample_repo / "tracked.py").write_bytes(b"modified-by-hand\n")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out_dir)]) == 0
    created = _zips_in(out_dir, "sample-repo_*.zip")
    with zipfile.ZipFile(created[0]) as zf:
        assert zf.read("sample-repo/tracked.py") == b"modified-by-hand\n"


def test_main_excludes_deleted_tracked_file(
    sample_repo: Path, tmp_path: Path
) -> None:
    (sample_repo / "tracked.py").unlink()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out_dir)]) == 0
    created = _zips_in(out_dir, "sample-repo_*.zip")
    with zipfile.ZipFile(created[0]) as zf:
        assert "sample-repo/tracked.py" not in zf.namelist()


def test_main_warns_on_dirty_working_tree(
    sample_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out_dir)]) == 0
    err = capsys.readouterr().err.lower()
    assert "uncommitted" in err or "working tree" in err


def test_main_no_warning_for_clean_tree(
    clean_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([str(clean_repo), "--output-dir", str(out_dir)]) == 0
    err = capsys.readouterr().err
    assert "uncommitted" not in err.lower()


def test_main_default_prefix_and_no_prefix(
    sample_repo: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out_dir)]) == 0
    with zipfile.ZipFile(_zips_in(out_dir, "sample-repo_*.zip")[0]) as zf:
        assert "sample-repo/tracked.py" in zf.namelist()

    out2 = tmp_path / "out2"
    out2.mkdir()
    assert (
        cli.main([str(sample_repo), "--output-dir", str(out2), "--no-prefix"]) == 0
    )
    with zipfile.ZipFile(_zips_in(out2, "sample-repo_*.zip")[0]) as zf:
        assert "tracked.py" in zf.namelist()
        assert not any(n.startswith("sample-repo/") for n in zf.namelist())


def test_main_custom_name_used_for_file_and_prefix(
    sample_repo: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert (
        cli.main([str(sample_repo), "--output-dir", str(out_dir), "--name", "submission"])
        == 0
    )
    created = _zips_in(out_dir, "submission_*.zip")
    assert len(created) == 1
    with zipfile.ZipFile(created[0]) as zf:
        assert "submission/tracked.py" in zf.namelist()


def test_main_custom_name_with_no_prefix(
    sample_repo: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert (
        cli.main(
            [str(sample_repo), "--output-dir", str(out_dir), "--name", "submission", "--no-prefix"]
        )
        == 0
    )
    created = _zips_in(out_dir, "submission_*.zip")
    with zipfile.ZipFile(created[0]) as zf:
        assert "tracked.py" in zf.namelist()


def test_main_short_options(
    sample_repo: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert (
        cli.main([str(sample_repo), "-o", str(out_dir), "-n", "shortopt"]) == 0
    )
    assert len(_zips_in(out_dir, "shortopt_*.zip")) == 1


@pytest.mark.parametrize(
    "bad",
    ["", "..", ".", "a/b", "a\\b", "/abs", "C:/x", "../x", "trailing ", "star*"],
)
def test_main_rejects_dangerous_names(
    sample_repo: Path, tmp_path: Path, bad: str
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert (
        cli.main([str(sample_repo), "--output-dir", str(out_dir), "--name", bad]) == 1
    )
    assert _zips_in(out_dir) == []


def test_main_missing_explicit_output_dir(sample_repo: Path, tmp_path: Path) -> None:
    assert cli.main([str(sample_repo), "--output-dir", str(tmp_path / "missing")]) == 1


def test_main_output_dir_must_be_directory(
    sample_repo: Path, tmp_path: Path
) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    assert cli.main([str(sample_repo), "--output-dir", str(f)]) == 1


def test_main_refuses_overwrite(
    sample_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(srcseal.archive, "timestamp_now", lambda: "20260101_000000")
    assert (
        cli.main([str(sample_repo), "--output-dir", str(out_dir), "--name", "fixed"])
        == 0
    )
    created = _zips_in(out_dir, "fixed_*.zip")
    assert len(created) == 1
    before = created[0].read_bytes()
    assert (
        cli.main([str(sample_repo), "--output-dir", str(out_dir), "--name", "fixed"])
        == 1
    )
    assert created[0].read_bytes() == before


def test_main_rejects_symlink_by_default(
    sample_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    link = sample_repo / "link.txt"
    try:
        link.symlink_to(sample_repo / "tracked.py")
    except OSError:
        pytest.skip("cannot create symlinks on this platform")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    code = cli.main([str(sample_repo), "--output-dir", str(out_dir)])
    assert code == 1
    assert "link.txt" in capsys.readouterr().err
    assert _zips_in(out_dir) == []


def test_main_no_links_excludes_symlink(
    sample_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    link = sample_repo / "link.txt"
    try:
        link.symlink_to(sample_repo / "tracked.py")
    except OSError:
        pytest.skip("cannot create symlinks on this platform")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    code = cli.main([str(sample_repo), "--output-dir", str(out_dir), "--no-links"])
    assert code == 0
    err = capsys.readouterr().err.lower()
    assert "symlink" in err and "link.txt" in err
    created = _zips_in(out_dir, "sample-repo_*.zip")
    with zipfile.ZipFile(created[0]) as zf:
        assert "sample-repo/link.txt" not in zf.namelist()
        assert "sample-repo/tracked.py" in zf.namelist()


def test_main_does_not_follow_symlink_to_inside_file(
    sample_repo: Path, tmp_path: Path
) -> None:
    inner = sample_repo / "inner.txt"
    inner.write_bytes(b"INNER-CONTENT\n")
    link = sample_repo / "link.txt"
    try:
        link.symlink_to(inner)
    except OSError:
        pytest.skip("cannot create symlinks on this platform")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    # Default fails; target bytes never stored.
    assert cli.main([str(sample_repo), "--output-dir", str(out_dir)]) == 1
    out2 = tmp_path / "out2"
    out2.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out2), "--no-links"]) == 0
    with zipfile.ZipFile(_zips_in(out2, "sample-repo_*.zip")[0]) as zf:
        assert "sample-repo/link.txt" not in zf.namelist()
        # Real file still archived.
        assert zf.read("sample-repo/inner.txt") == b"INNER-CONTENT\n"


def test_main_rejects_symlink_logic_with_mock(
    sample_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Mock version of the symlink tests above."""
    fake_symlink(monkeypatch, sample_repo)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out_dir)]) == 1
    assert "tracked.py" in capsys.readouterr().err

    out2 = tmp_path / "out2"
    out2.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out2), "--no-links"]) == 0
    with zipfile.ZipFile(_zips_in(out2, "sample-repo_*.zip")[0]) as zf:
        assert "sample-repo/tracked.py" not in zf.namelist()


def test_main_excludes_submodule_contents(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    from tests.conftest import init_repo

    sub_src = init_repo(tmp_path / "sub-src")
    (sub_src / "inner.txt").write_text("submodule-inner\n", encoding="utf-8")
    git(sub_src, "add", "inner.txt")
    git(sub_src, "commit", "-m", "sub init")

    main_repo = init_repo(tmp_path / "main-repo")
    (main_repo / "top.txt").write_text("top\n", encoding="utf-8")
    git(main_repo, "add", "top.txt")
    git(main_repo, "commit", "-m", "init")
    # returncode is checked below; check=True would prevent the skip.
    proc = subprocess.run(  # noqa: PLW1510
        ("git", "-c", "protocol.file.allow=always", "submodule", "add", str(sub_src), "sub"),
        cwd=main_repo,
        capture_output=True,
    )
    if proc.returncode != 0:
        pytest.skip(f"cannot create submodule: {proc.stderr.decode(errors='replace')}")
    git(main_repo, "commit", "-m", "add submodule")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    code = cli.main([str(main_repo), "--output-dir", str(out_dir)])
    assert code == 0
    err = capsys.readouterr().err.lower()
    assert "submodule" in err
    created = _zips_in(out_dir, "main-repo_*.zip")
    assert len(created) == 1
    with zipfile.ZipFile(created[0]) as zf:
        names = zf.namelist()
    assert "main-repo/top.txt" in names
    assert not any("inner.txt" in n for n in names)
    assert not any(n.startswith("main-repo/sub/") for n in names)


def test_main_output_inside_repo_is_not_self_included(
    sample_repo: Path,
) -> None:
    out_dir = sample_repo / "out"
    out_dir.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out_dir)]) == 0
    created = _zips_in(out_dir, "sample-repo_*.zip")
    assert len(created) == 1
    with zipfile.ZipFile(created[0]) as zf:
        assert not any(n.endswith(".zip") for n in zf.namelist())


def test_main_space_and_unicode_filenames(
    sample_repo: Path, tmp_path: Path
) -> None:
    spaced = sample_repo / "dir with space" / "file with space.txt"
    spaced.parent.mkdir()
    spaced.write_bytes(b"spaced\n")
    uni = sample_repo / "ユニコード.txt"
    uni.write_bytes(b"unicode\n")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out_dir)]) == 0
    created = _zips_in(out_dir, "sample-repo_*.zip")
    with zipfile.ZipFile(created[0]) as zf:
        assert zf.read("sample-repo/dir with space/file with space.txt") == (
            sample_repo / "dir with space" / "file with space.txt"
        ).read_bytes()
        assert zf.read("sample-repo/ユニコード.txt") == (sample_repo / "ユニコード.txt").read_bytes()


def test_main_preserves_git_executable_bit(
    sample_repo: Path, tmp_path: Path
) -> None:
    script = sample_repo / "run.sh"
    script.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    git(sample_repo, "add", "run.sh")
    git(sample_repo, "commit", "-m", "add script")
    git(sample_repo, "update-index", "--chmod=+x", "run.sh")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out_dir)]) == 0
    created = _zips_in(out_dir, "sample-repo_*.zip")
    with zipfile.ZipFile(created[0]) as zf:
        mode = (zf.getinfo("sample-repo/run.sh").external_attr >> 16) & 0o777
    assert mode & 0o111


def test_main_rejects_missing_path(tmp_path: Path) -> None:
    assert cli.main([str(tmp_path / "missing")]) == 1


def test_main_reports_missing_git_without_traceback(
    sample_repo: Path, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    monkeypatch.setenv("PATH", "")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert cli.main([str(sample_repo), "--output-dir", str(out_dir)]) == 1
    captured = capsys.readouterr()
    assert "not found on PATH" in captured.err
    assert "Traceback" not in captured.err and "Traceback" not in captured.out
    assert _zips_in(out_dir) == []


def test_python_module_entrypoint_shows_help() -> None:
    # returncode is asserted below.
    proc = subprocess.run(  # noqa: PLW1510
        (sys.executable, "-m", "srcseal", "--help"), capture_output=True, text=True
    )
    assert proc.returncode == 0
    assert "usage" in proc.stdout.lower()
