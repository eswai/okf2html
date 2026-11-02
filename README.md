# okf2html

OKF（Markdown + YAML frontmatter）のフォルダから、2 ペイン構成の静的サイトを生成します。Mac / Windows で動きます。

- 左ペイン: ページ一覧。フォルダごとに折りたたみ・展開できる（今開いているページのフォルダだけ最初から開く）
- 右ペイン: frontmatter をコンパクトな表で表示し、その下に本文
  - 値が複数行になる項目は 1 行目だけ表示し、残りはクリックで展開
- ページ名: frontmatter の `title`。無ければファイル名（拡張子なし）
- 出力形式: `html` または `aspx`（拡張子とページ間リンクが `.aspx` になる。中身は同じ HTML）
- CSS は各ページに埋め込むので、出力フォルダをそのまま置くだけで表示できる
- 本文中の `xxx.md` へのリンクは出力形式の拡張子に書き換える
- `[[ ]]` 形式のリンクも使える
  - `[[ページ]]` / `[[ページ|表示名]]` / `[[ページ#見出し]]` / `[[#見出し]]`（同じページ内）
  - リンク先は「今のページからの相対パス → 入力フォルダからのパス → ファイル名 → title」の順に探す（`.md` は付けても付けなくてもよい）
  - 同じファイル名が複数あるときは、同じフォルダのページを優先する
  - 見つからないときはリンクにせず薄い点線で表示し、警告を出す
- 画像・PDF（png, jpg, gif, svg, webp, pdf など）は同じフォルダ構成で出力先へコピーする
- 入力のルートに `index.md` が無ければ、全ページの一覧ページ `index.html|aspx` を作る

## インストール

パッケージ管理には [uv](https://docs.astral.sh/uv/) を使います。

```bash
uv sync
```

`.python-version` で Python 3.13 を指定しています。uv が Python ごと用意するので、事前の Python のインストールは不要です（uv の Python には Tkinter が入っています）。依存は `pyproject.toml`、固定バージョンは `uv.lock` で管理します。

### GUI を Mac で使う場合の注意

uv 以外の Python を使う場合、GUI には Tk 8.6 以上が必要です。macOS 標準の `/usr/bin/python3`（Tk 8.5）では画面が固まり、Homebrew の Python は `brew install python-tk@3.xx` が別途必要です。CLI だけならどの Python 3.9 以上でも動きます。

## CLI

```
okf2html INPUT_DIR -o OUTPUT_DIR [--format html|aspx] [--title サイト名] [--ext .md,.okf]
```

| オプション | 説明 |
|---|---|
| `-o, --output` | 出力先フォルダ（必須） |
| `-f, --format` | `html`（既定）または `aspx` |
| `-t, --title` | サイト名（既定: 入力フォルダ名） |
| `--ext` | 対象の拡張子。カンマ区切りで複数可（既定: `.md`） |

例:

```bash
uv run okf2html docs -o _site --format aspx --title "社内ナレッジ"
```

`uv run python -m okf2html ...` でも同じです。成功すると終了コード 0、エラーなら 1 を返します。frontmatter が壊れているファイルは警告を出し、frontmatter 無しとして生成を続けます。

## GUI

```bash
uv run okf2html-gui        # または uv run python -m okf2html.gui
```

入力フォルダ・出力フォルダ・サイト名・形式を指定して「生成」を押します。GUI は裏で CLI を呼び出し、その出力をログ欄に表示します。

## 単体実行ファイルにする（任意）

各 OS 上で PyInstaller を実行します（Mac 用は Mac で、Windows 用は Windows で作ります）。

```bash
# Mac
uv run --with pyinstaller pyinstaller --windowed --name okf2html --add-data "okf2html/style.css:okf2html" okf2html_gui.py
# Windows
uv run --with pyinstaller pyinstaller --windowed --name okf2html --add-data "okf2html/style.css;okf2html" okf2html_gui.py
```

できた実行ファイルは、そのまま起動すると GUI、`--cli` を付けると CLI として動きます（例: `okf2html --cli docs -o _site`）。

## 開発

```bash
uv sync          # pytest を含む dev グループも入る
uv run pytest
uv add <パッケージ>   # 依存を追加する
```

`tests/samples/` にサンプルの OKF があります。
