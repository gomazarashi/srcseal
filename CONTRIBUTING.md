# Contributing to srcseal

Small PRs are welcome. For anything beyond a trivial fix,
please open an issue first.

```powershell
pip install -e .[test]
pytest
```

- Stdlib only for now: no new runtime dependencies at this stage.
- Add a test under `tests/` when behavior changes.

## 日本語

小さなPRを歓迎します。自明な修正を超える内容は、先にIssueを作成してください。

```powershell
pip install -e .[test]
pytest
```

- 現時点では標準ライブラリのみ。runtime dependencyは追加しないでください。
- 挙動が変わる場合は `tests/` にテストを追加してください。
