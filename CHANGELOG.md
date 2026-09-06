# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Minimal `CONTRIBUTING.md` and pull request template.

## [0.1.1] - 2026-09-06

### Fixed
- Stage the ZIP in a temp file so a mid-run failure leaves no partial archive.
  An existing output file is still never overwritten.
- Reject Windows-absolute/traversal entry paths (`..\evil.txt`, `C:\evil.txt`,
  UNC paths, drive-relative paths) so archives stay safe when extracted on Windows.
- Report a missing `git` executable as a clean CLI error instead of a traceback.
- Reject non-UTF-8-encodable filenames with a clear error instead of a traceback.

### Changed
- PEP 639 license metadata (`License-Expression: MIT`).

## [0.1.0] - 2026-09-06

### Added
- Initial release: create a ZIP archive from the current Git working tree
  (tracked files plus non-ignored untracked files, working-tree bytes not `HEAD`).
- Options: `--output-dir`, `--name`, `--no-prefix`, `--no-links`.
- Symlink refusal (or exclusion with `--no-links`), submodule warning,
  dirty-tree warning, executable-bit preservation.
- Windows and Linux support via GitHub Actions.

[Unreleased]: https://github.com/gomazarashi/srcseal/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/gomazarashi/srcseal/releases/tag/v0.1.1
[0.1.0]: https://github.com/gomazarashi/srcseal/releases/tag/v0.1.0
