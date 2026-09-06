"""Command-line interface for srcseal."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import archive


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="srcseal",
        description=(
            "Create a ZIP archive from the current Git working tree "
            "(tracked files plus non-ignored untracked files)."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=None,
        help=(
            "Directory inside the repository to archive. "
            "The containing repository root is resolved via git. "
            "If omitted, show this help instead of creating an archive."
        ),
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Output directory (must already exist; never created). "
            "Default: ~/Downloads, falling back to the current directory "
            "when ~/Downloads does not exist."
        ),
    )
    parser.add_argument(
        "-n",
        "--name",
        default=None,
        help=(
            "Base name used for the ZIP file and the top-level directory "
            "inside it. Default: repository root directory name."
        ),
    )
    parser.add_argument(
        "--no-prefix",
        action="store_true",
        help="Store files at the ZIP root without a top-level directory.",
    )
    parser.add_argument(
        "--no-links",
        action="store_true",
        help="Exclude symlinks with a warning instead of failing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``srcseal`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.path is None:
        # Spec: bare invocation shows help instead of archiving.
        parser.print_help()
        return 0
    try:
        start = args.path.expanduser()
        if not start.is_dir():
            raise archive.ArchiveError(
                f"specified directory does not exist or is not a directory: {args.path}"
            )
        repo_root = archive.find_repo_root(start)
        output_dir = archive.resolve_output_dir(args.output_dir)

        raw_name = args.name if args.name is not None else repo_root.name
        name = archive.validate_archive_name(raw_name)
        out_path = output_dir / f"{name}_{archive.timestamp_now()}.zip"
        if out_path.exists():
            raise archive.ArchiveError(
                f"output file already exists (will not overwrite): {out_path}"
            )

        relative_paths = archive.list_archive_files(repo_root)
        # Exclude only the ZIP being created; past ZIPs follow git rules.
        try:
            # resolve() covers relative dirs and symlinked parents.
            out_rel = out_path.resolve().relative_to(repo_root.resolve()).as_posix()
        except (ValueError, OSError):
            # Outside the repo: nothing to exclude.
            out_rel = None
        if out_rel is not None and out_rel in relative_paths:
            relative_paths = [p for p in relative_paths if p != out_rel]

        symlinks = [p for p in relative_paths if (repo_root / p).is_symlink()]
        if symlinks:
            listed = ", ".join(sorted(symlinks))
            if args.no_links:
                print(
                    f"warning: excluding {len(symlinks)} symlink(s): {listed}",
                    file=sys.stderr,
                )
                excluded = set(symlinks)
                relative_paths = [p for p in relative_paths if p not in excluded]
            else:
                raise archive.ArchiveError(
                    f"found {len(symlinks)} symlink(s); refusing to follow them "
                    f"(use --no-links to exclude): {listed}"
                )

        file_modes = archive.get_file_modes(repo_root)
        submodules = archive.find_submodules(file_modes)
        if submodules:
            print(
                "warning: submodules are not archived recursively "
                f"(excluded {len(submodules)}): {', '.join(submodules)}",
                file=sys.stderr,
            )

        if not relative_paths:
            raise archive.ArchiveError("no files to archive.")
        prefix = "" if args.no_prefix else name
        count = archive.build_archive(
            repo_root,
            relative_paths,
            out_path,
            prefix=prefix,
            file_modes=file_modes,
        )
    except archive.ArchiveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        size_mb = out_path.stat().st_size / 1024 / 1024
    except OSError:
        # Report-only value; never fail the run for it.
        size_mb = 0.0
    print(f"archived {count:,} file(s) / {size_mb:.2f} MB")
    print(f"output: {out_path}")
    if archive.has_uncommitted_changes(repo_root):
        print(
            "warning: working tree has uncommitted changes or untracked files. "
            "The archive contains the current working tree, not HEAD.",
            file=sys.stderr,
        )
    return 0
