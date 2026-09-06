# srcseal

`srcseal` creates a ZIP archive from the current Git working tree.

Which files to include is decided by Git itself: existing tracked files plus
non-ignored untracked files. The stored bytes are the working-tree contents,
not `HEAD`.

## Requirements

- Python >= 3.13
- `git` available on `PATH`
- No Python runtime dependencies
- OS: Windows, Linux

## Installation

```powershell
git clone https://github.com/gomazarashi/srcseal.git
cd srcseal
pip install .
```

This provides the `srcseal` command (`python -m srcseal` works the same).

For development and tests:

```powershell
pip install -e .[test]
pytest
```

## Usage

```powershell
srcseal --help          # help (bare `srcseal` shows the same, no archive)
srcseal .               # archive the current repository
srcseal ../some-project # any directory inside the target repository works
srcseal . --name submission
srcseal . --no-prefix
srcseal . --no-links
srcseal . -o C:\tmp\out -n submission
```

## Options

- `path`: directory inside the repository to archive (root is resolved via git).
- `-o, --output-dir DIR`: existing output directory, never created automatically. Default: `~/Downloads`, or the current directory when `~/Downloads` is missing.
- `-n, --name NAME`: base name of the ZIP (`<name>_YYYYMMDD_HHMMSS.zip`) and of the top-level directory inside it. Default: repository root name. Must be a plain name; path components, absolute paths, and traversal are rejected, never sanitized.
- `--no-prefix`: place files at the ZIP root instead of under `<name>/`.
- `--no-links`: exclude symlinks with a warning instead of failing.
- `-h, --help`: show help.

## Included / excluded

Included:

- Existing tracked files (current working-tree contents, including modifications)
- Non-ignored untracked files

Excluded:

- Git-ignored files, deleted tracked files, empty directories
- Submodule contents
- Symlinks (see below)

A dirty working tree is fine: the archive is still created with a warning.
This is intentional, since the target is the working tree, not `HEAD`.

## Symlinks

Targets are never followed. By default a symlink aborts the run with an
error naming it (even when the target is inside the repository).
`--no-links` excludes symlinks with a warning instead.

## Submodules

Never archived recursively. Inner files are excluded with a warning, and the
exit status stays successful.

## Output location

The ZIP being created is never included in itself. Other existing ZIPs follow
normal Git rules. An existing output file is never overwritten (error exit).

## 日本語

`srcseal` は現在のGit working treeからZIPアーカイブを作成するツールです。

入れるファイルの判断はGit自身に任せています。存在しているtracked fileと、
ignore対象ではないuntracked fileを含めます。格納するのは `HEAD` ではなく、
working treeの今の内容です。

### 要件

- Python >= 3.13
- `git` が `PATH` 上で使えること
- Pythonのruntime dependencyなし
- 対応OS: Windows、Linux

### インストール

```powershell
git clone https://github.com/gomazarashi/srcseal.git
cd srcseal
pip install .
```

`srcseal` コマンドが使えるようになります（`python -m srcseal` も同じ）。

開発・テスト用:

```powershell
pip install -e .[test]
pytest
```

### 使い方

```powershell
srcseal --help          # help（引数なしも同じ、アーカイブは作らない）
srcseal .               # 今のリポジトリをアーカイブ
srcseal ../some-project # リポジトリ内のどのディレクトリでも可
srcseal . --name submission
srcseal . --no-prefix
srcseal . --no-links
srcseal . -o C:\tmp\out -n submission
```

### オプション

- `path`: アーカイブしたいリポジトリ内のディレクトリ（ルートはgitで特定）。
- `-o, --output-dir DIR`: 存在している出力ディレクトリを指定（自動作成しない）。既定は `~/Downloads`、なければ実行時のカレントディレクトリ。
- `-n, --name NAME`: ZIP名（`<name>_YYYYMMDD_HHMMSS.zip`）とZIP内のトップレベル名。既定はリポジトリ名。単純な名前のみ有効で、path component・絶対パス・traversalは自動補正せずエラー。
- `--no-prefix`: トップレベルを作らずZIP直下に置く。
- `--no-links`: symlinkをエラーにせずwarning付きで除外。
- `-h, --help`: helpを表示。

### 含まれるもの / 含まれないもの

含まれるもの:

- 存在しているtracked file（変更後のworking treeの内容そのまま）
- ignore対象ではないuntracked file

含まれないもの:

- Gitのignore対象、削除済みtracked file、空ディレクトリ
- submoduleの中身
- symlink（下記参照）

working treeがdirtyでもアーカイブは作成され、warningが出ます（意図した仕様です）。

### symlinkの扱い

リンク先をたどることは決してしません。既定では対象パスを示すエラーで中断します（リンク先がリポジトリ内でも同じ）。`--no-links` で除外＋warningになります。

### submoduleの扱い

再帰的に含めません。中身は除外してwarningを出し、終了ステータスは成功のままです。

### 出力先

作成中のZIP自体が混ざることはありません。他の既存ZIPは通常のGitルールに従います。同名ファイルがある場合は上書きせずエラー終了します。
