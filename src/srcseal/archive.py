"""ZIP archive of the current Git working tree."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath


class ArchiveError(RuntimeError):
    """Raised when the archive cannot be created."""


class GitNotFoundError(ArchiveError):
    """Raised when the git executable is missing from PATH."""


def _run_git(repo: Path, *args: str) -> bytes:
    """Run git in *repo*; return raw stdout (bytes-safe paths)."""
    try:
        completed = subprocess.run(
            ("git", *args),
            cwd=repo,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        # A clear CLI error instead of a traceback.
        raise GitNotFoundError(
            "git was not found on PATH "
            "(install git and ensure it is available on PATH)"
        ) from None
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        joined = " ".join(args)
        detail = f": {stderr}" if stderr else ""
        raise ArchiveError(f"git {joined} failed{detail}")
    return completed.stdout


def find_repo_root(start: Path) -> Path:
    """Return the top-level directory of the repository containing *start*."""
    try:
        output = _run_git(start, "rev-parse", "--show-toplevel")
    except GitNotFoundError:
        raise
    except ArchiveError:
        raise ArchiveError(f"not a git repository: {start}") from None
    # rev-parse prints one line.
    text = os.fsdecode(output).strip()
    if not text:
        raise ArchiveError(f"not a git repository: {start}")
    return Path(text)


def list_archive_files(repo_root: Path) -> list[str]:
    """Tracked + non-ignored untracked files, as sorted relative paths.

    Symlinks are kept so the caller can reject or skip them.
    """
    raw = _run_git(
        repo_root, "ls-files", "--cached", "--others", "--exclude-standard", "-z"
    )
    names = [os.fsdecode(part) for part in raw.split(b"\x00") if part]
    result: list[str] = []
    for name in names:
        if not name or name in (".", ".."):
            continue
        full = repo_root / name
        try:
            if full.is_symlink() or full.is_file():
                result.append(name)
        except OSError:
            # Best effort: skip entries we cannot stat.
            continue
    return sorted(result)


def get_file_modes(repo_root: Path) -> dict[str, str]:
    """Tracked path -> git mode ("100644"; submodules are "160000")."""
    raw = _run_git(repo_root, "ls-files", "--stage", "-z")
    modes: dict[str, str] = {}
    for entry in raw.split(b"\x00"):
        if not entry:
            continue
        # Format: "<mode> SP <sha> TAB <path>".
        meta, sep, path_bytes = entry.partition(b"\t")
        if not sep:
            continue
        try:
            mode = meta.split(b" ", 1)[0].decode("ascii")
        except (ValueError, UnicodeDecodeError):
            continue
        if not mode.isdigit():
            continue
        modes[os.fsdecode(path_bytes)] = mode
    return modes


def find_submodules(file_modes: dict[str, str]) -> list[str]:
    """Return sorted submodule mount points (gitlinks, mode 160000)."""
    return sorted(path for path, mode in file_modes.items() if mode == "160000")


def has_uncommitted_changes(repo_root: Path) -> bool:
    """Return True when the working tree differs from HEAD in any way."""
    output = _run_git(repo_root, "status", "--porcelain=v1", "-z")
    return bool(output.strip(b"\x00 \t\r\n"))


def validate_archive_name(name: str) -> str:
    """Validate *name* as a plain name; raise instead of sanitizing."""
    if not name:
        raise ArchiveError("archive name must not be empty")
    if name in (".", ".."):
        raise ArchiveError(f"invalid archive name: {name!r}")
    if "/" in name or "\\" in name or "\x00" in name:
        raise ArchiveError(f"invalid archive name (must be a plain name): {name!r}")
    if PurePosixPath(name).is_absolute() or PureWindowsPath(name).is_absolute():
        raise ArchiveError(f"invalid archive name (must not be absolute): {name!r}")
    # C:foo is drive-relative, not absolute, so is_absolute() misses it.
    if len(name) >= 2 and name[1] == ":":
        raise ArchiveError(f"invalid archive name (must not be absolute): {name!r}")
    if PurePosixPath(name).name != name or PureWindowsPath(name).name != name:
        raise ArchiveError(f"invalid archive name (must be a plain name): {name!r}")
    if any(c in '<>:"|?*' for c in name):
        raise ArchiveError(f"invalid archive name (illegal character): {name!r}")
    if any(ord(c) < 0x20 for c in name):
        raise ArchiveError(f"invalid archive name (control character): {name!r}")
    if name[-1] in (" ", "."):
        # Windows silently strips these, breaking the file name.
        raise ArchiveError(
            f"invalid archive name (must not end with space or dot): {name!r}"
        )
    return name


def resolve_output_dir(explicit: Path | None) -> Path:
    """Explicit dir must exist; default is ~/Downloads, else CWD."""
    if explicit is not None:
        candidate = explicit.expanduser()
        if not candidate.is_dir():
            raise ArchiveError(
                f"output directory does not exist or is not a directory: {explicit} "
                "(specify an existing directory; --output-dir never creates one)"
            )
        return candidate
    downloads = Path.home() / "Downloads"
    try:
        if downloads.is_dir():
            return downloads
    except OSError:
        pass
    return Path.cwd()


def timestamp_now() -> str:
    """Aware local time as ``YYYYMMDD_HHMMSS`` (not naive ``datetime.now()``)."""
    return datetime.now(UTC).astimezone().strftime("%Y%m%d_%H%M%S")


def _check_safe_relative_path(rel: str) -> None:
    """Reject archive entries that could escape the target directory.

    Both separators count: a name legal on Linux (e.g. ``..\\evil.txt``)
    can act as traversal when the ZIP is extracted on Windows.
    """
    if not rel or rel in (".", ".."):
        raise ArchiveError(f"refusing unsafe path from git: {rel!r}")
    posix = PurePosixPath(rel)
    if posix.is_absolute():
        raise ArchiveError(f"refusing unsafe absolute path from git: {rel!r}")
    if ".." in posix.parts:
        raise ArchiveError(f"refusing unsafe path from git: {rel!r}")
    windows = PureWindowsPath(rel)
    # Drive-absolute (C:\...), UNC (\\server\...), or rooted (\...).
    # Rooted paths lack a drive, so is_absolute() alone misses them.
    if windows.is_absolute() or rel.startswith("\\"):
        raise ArchiveError(f"refusing unsafe absolute path from git: {rel!r}")
    if len(rel) >= 2 and rel[0].isalpha() and rel[1] == ":":
        # Drive-relative (C:foo); is_absolute() misses it.
        raise ArchiveError(f"refusing unsafe path from git: {rel!r}")
    if ".." in windows.parts:
        raise ArchiveError(f"refusing unsafe path from git: {rel!r}")


def _check_zip_encodable(arcname: str, rel: str) -> None:
    """Reject names zipfile cannot store instead of leaking a traceback."""
    try:
        arcname.encode("utf-8")
    except UnicodeEncodeError:
        # Never sanitize: say which file, in printable form.
        shown = rel.encode("utf-8", "backslashreplace").decode("ascii")
        raise ArchiveError(
            f"cannot store filename in ZIP (not UTF-8 encodable): {shown}"
        ) from None


def build_archive(
    repo_root: Path,
    relative_paths: list[str],
    out_path: Path,
    *,
    prefix: str,
    file_modes: dict[str, str] | None = None,
) -> int:
    """Store working-tree bytes; preserve the git executable bit."""
    if out_path.exists():
        raise ArchiveError(
            f"output file already exists (will not overwrite): {out_path}"
        )
    if not out_path.parent.is_dir():
        raise ArchiveError(f"output directory does not exist: {out_path.parent}")

    modes = file_modes if file_modes is not None else {}
    # Stage in a temp file: a mid-run failure must not leave a partial ZIP.
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{out_path.name}.", suffix=".tmp", dir=out_path.parent
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        count = 0
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for rel in relative_paths:
                _check_safe_relative_path(rel)
                arcname = f"{prefix}/{rel}" if prefix else rel
                _check_zip_encodable(arcname, rel)
                full = repo_root / rel
                # Never follow symlinks.
                try:
                    if full.is_symlink():
                        raise ArchiveError(
                            f"refusing to follow symlink during archiving: {rel}"
                        )
                    if not full.is_file():
                        continue
                except OSError as exc:
                    raise ArchiveError(
                        f"cannot read file for archiving: {rel}: {exc}"
                    ) from exc
                try:
                    data = full.read_bytes()
                    file_stat = full.stat()
                except OSError as exc:
                    raise ArchiveError(
                        f"cannot read file for archiving: {rel}: {exc}"
                    ) from exc

                git_mode = modes.get(rel)
                if git_mode == "100755":
                    unix_mode = 0o755
                elif git_mode is not None:
                    unix_mode = 0o644
                else:
                    # Git has no mode for untracked files; use the filesystem bit.
                    unix_mode = 0o755 if (file_stat.st_mode & 0o111) else 0o644

                info = zipfile.ZipInfo(
                    filename=arcname,
                    date_time=time.localtime(file_stat.st_mtime)[:6],
                )
                info.create_system = 3  # Unix: unzip honors the mode bits.
                info.compress_type = zipfile.ZIP_DEFLATED
                # Upper 16 bits hold the Unix file mode.
                info.external_attr = (stat.S_IFREG | unix_mode) << 16
                archive.writestr(info, data)
                count += 1
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    if out_path.exists():
        # Re-check: never overwrite, even if the file appeared mid-run.
        tmp_path.unlink(missing_ok=True)
        raise ArchiveError(
            f"output file already exists (will not overwrite): {out_path}"
        )
    try:
        os.replace(tmp_path, out_path)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise ArchiveError(f"cannot write output file: {out_path}: {exc}") from exc
    return count
