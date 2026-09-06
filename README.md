# srcseal

`srcseal` creates a ZIP archive from the current Git working tree.

It uses Git itself to decide which files to include: tracked files that exist
plus untracked files that are not ignored. The stored bytes are the current
working-tree contents, not `HEAD`.

## Requirements

- Python >= 3.13
- `git` available on `PATH`

No Python runtime dependencies.

Supported OS: Windows, Linux.

## Installation

From a cloned GitHub repository:

```powershell
git clone https://github.com/<owner>/srcseal.git
cd srcseal
pip install .
```

After installation the `srcseal` command is available. `python -m srcseal`
works equivalently.

For development and tests:

```powershell
pip install -e .[test]
pytest
```

## Usage

Show help (also shown when run without arguments; no archive is created):

```powershell
srcseal --help
srcseal
```

Archive the repository containing the current directory:

```powershell
srcseal .
```

Archive another repository (any directory inside it works):

```powershell
srcseal ../some-project
```

Common options:

```powershell
srcseal . --name submission
srcseal . --no-prefix
srcseal . --no-links
srcseal . -o C:\tmp\out -n submission
```

## Options

| Option | Description |
| --- | --- |
| `path` | Directory inside the repository to archive. The repository root is resolved with `git rev-parse --show-toplevel`. |
| `-o, --output-dir DIR` | Output directory. Must already exist; never created automatically. Default: `~/Downloads`, falling back to the current working directory when `~/Downloads` does not exist. |
| `-n, --name NAME` | Base name for the ZIP file (`<name>_YYYYMMDD_HHMMSS.zip`) and for the top-level directory inside it. Default: repository root directory name. Strictly validated as a plain name; path components, absolute paths, and traversal are rejected with an error (never sanitized). |
| `--no-prefix` | Store files at the ZIP root instead of under `<name>/`. |
| `--no-links` | Exclude symlinks with a warning instead of failing. |
| `-h, --help` | Show help. |

## What is included

Included:

- Tracked files that currently exist (working-tree bytes, including modified files)
- Untracked files that Git does not ignore

Not included:

- Files ignored by normal Git ignore rules (`.gitignore`, `.git/info/exclude`, etc.)
- Deleted tracked files
- Empty directories
- Submodule contents (the submodule mount point itself is not a file and is skipped)
- Symlinks (see below)

`srcseal` archives the current working tree, not `HEAD`. Modified but
uncommitted tracked files are stored with their current contents.

If the working tree is dirty (uncommitted changes or untracked files), the
archive is still created and a warning is printed. This is intentional.

## Symlinks

Symlink targets are never followed.

By default, if an archivable path is a symlink, `srcseal` aborts with an
error naming the symlink(s). This applies even when the target is inside the
repository.

With `--no-links`, symlinks are excluded from the archive and a warning is
printed.

## Submodules

Submodule contents are never archived recursively. If submodules exist, their
inner files are excluded, a warning naming the submodule(s) is printed, and
the exit status stays successful.

## Output location

Default output directory is `~/Downloads`. When `~/Downloads` does not exist,
the current working directory at execution time is used instead.

An explicit `--output-dir` must already exist and be a directory; it is never
created automatically. Otherwise `srcseal` exits with an error.

The ZIP being created is never included in itself, even when the output
directory is inside the repository. Other existing ZIP files follow normal
Git tracked/untracked/ignore rules and are not specially excluded.

If the final output path already exists, `srcseal` does not overwrite it and
exits with an error.
