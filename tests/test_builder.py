from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from okf2html import cli, parser
from okf2html.builder import BuildError, build, render_frontmatter

SAMPLES = Path(__file__).parent / "samples"


def _build(tmp_path: Path, fmt: str = "html") -> Path:
    out = tmp_path / "site"
    build(str(SAMPLES), str(out), fmt=fmt, site_title="サンプル", log=lambda m: None, warn=lambda m: None)
    return out


def test_split_frontmatter_ok():
    meta, body, warn = parser.split_frontmatter("---\ntitle: A\ndate: 2026-01-02\n---\n本文\n")
    assert meta == {"title": "A", "date": dt.date(2026, 1, 2)}
    assert body == "本文\n"
    assert warn is None


def test_split_frontmatter_missing_and_broken():
    meta, body, warn = parser.split_frontmatter("# 見出し\n")
    assert meta is None and body == "# 見出し\n" and warn is None
    meta, body, warn = parser.split_frontmatter("---\nx: [unclosed\n---\n本文")
    assert meta is None and body == "本文" and "YAML" in warn


def test_format_value():
    assert parser.format_value(["a", "b"]) == ["a, b"]
    assert parser.format_value(dt.date(2026, 1, 2)) == ["2026-01-02"]
    assert parser.format_value("1行目\n2行目\n") == ["1行目", "2行目"]
    assert parser.format_value({"name": "x", "team": "y"}) == ["name: x", "team: y"]
    assert parser.format_value(None) == [""]


def test_rewrite_link():
    assert parser.rewrite_link("a/b.md#x", [".md"], ".aspx") == "a/b.aspx#x"
    assert parser.rewrite_link("https://example.com/a.md", [".md"], ".html") == "https://example.com/a.md"
    assert parser.rewrite_link("#top", [".md"], ".html") == "#top"
    assert parser.rewrite_link("img.png", [".md"], ".html") == "img.png"


def test_frontmatter_multiline_is_collapsed():
    html = render_frontmatter({"title": "<T>", "summary": "一\n二\n三"})
    assert "<th>title</th><td>&lt;T&gt;</td>" in html
    assert '<span class="fm-first">一</span>' in html
    assert "…（+2行）" in html
    assert '<div class="fm-rest">二\n三</div>' in html


def test_build_html(tmp_path):
    out = _build(tmp_path)
    page = (out / "ガイド" / "環境構築.html").read_text(encoding="utf-8")
    # ページ名は frontmatter の title
    assert '<h1 class="page-title">環境構築</h1>' in page
    assert "<title>環境構築 | サンプル</title>" in page
    # 現在ページのフォルダだけ開いている
    assert '<details class="folder" open><summary>ガイド</summary>' in page
    assert '<details class="folder"><summary>リファレンス</summary>' in page
    assert '<a class="page current" aria-current="page" href="環境構築.html">' in page
    # 本文リンクが .html に書き換わっている
    assert 'href="運用/デプロイ手順.html"' in page
    # 複数行の frontmatter は折りたたみ
    assert "…（+2行）" in page
    # 生成物の一式
    assert (out / "index.html").exists()
    assert (out / "リファレンス" / "api.html").exists()


def test_title_falls_back_to_filename(tmp_path):
    out = _build(tmp_path)
    api = (out / "リファレンス" / "api.html").read_text(encoding="utf-8")
    assert '<h1 class="page-title">api</h1>' in api
    no_fm = (out / "ガイド" / "運用" / "障害対応.html").read_text(encoding="utf-8")
    # 本文の見出しではなくファイル名を使う
    assert '<h1 class="page-title">障害対応</h1>' in no_fm
    assert "frontmatter" not in no_fm.split('<div class="body">')[0].split("</h1>")[1]


def test_build_aspx(tmp_path):
    out = _build(tmp_path, fmt="aspx")
    assert (out / "index.aspx").exists()
    assert not list(out.rglob("*.html"))
    top = (out / "はじめに.aspx").read_text(encoding="utf-8")
    assert 'href="ガイド/環境構築.aspx"' in top
    assert 'href="リファレンス/api.aspx#エンドポイント"' in top
    deep = (out / "ガイド" / "運用" / "デプロイ手順.aspx").read_text(encoding="utf-8")
    assert 'href="../../index.aspx"' in deep
    assert 'href="../環境構築.aspx"' in deep


def test_errors(tmp_path):
    with pytest.raises(BuildError):
        build(str(tmp_path / "none"), str(tmp_path / "out"), log=lambda m: None)
    with pytest.raises(BuildError):
        build(str(SAMPLES), str(tmp_path / "out"), fmt="pdf", log=lambda m: None)


def test_cli_exit_codes(tmp_path, capsys):
    assert cli.main([str(SAMPLES), "-o", str(tmp_path / "o"), "--format", "aspx"]) == 0
    assert "警告" in capsys.readouterr().err  # 用語集.md の壊れた YAML
    assert cli.main([str(tmp_path / "none"), "-o", str(tmp_path / "o")]) == 1


def test_split_wikilink():
    assert parser.split_wikilink("a") == ("a", "", "")
    assert parser.split_wikilink("a|表示") == ("a", "", "表示")
    assert parser.split_wikilink("a#見出し") == ("a", "見出し", "")
    assert parser.split_wikilink(" #見出し | 表示 ") == ("", "見出し", "表示")


def test_wikilinks(tmp_path):
    out = tmp_path / "site"
    warnings = []
    build(str(SAMPLES), str(out), fmt="aspx", log=lambda m: None, warn=warnings.append)
    top = (out / "はじめに.aspx").read_text(encoding="utf-8")
    assert '<a class="wikilink" href="ガイド/環境構築.aspx">環境構築</a>' in top
    assert '<a class="wikilink" href="ガイド/運用/デプロイ手順.aspx">デプロイのやり方</a>' in top
    assert '<a class="wikilink" href="リファレンス/api.aspx#エンドポイント">api &gt; エンドポイント</a>' in top
    assert '<a class="wikilink" href="ガイド/運用/障害対応.aspx">障害対応</a>' in top
    assert '<a class="wikilink" href="FAQ/よくある質問.aspx">よくある質問</a>' in top
    assert '<span class="wikilink missing"' in top and "まだ無いページ</span>" in top
    assert "<code>[[環境構築]]</code>" in top
    assert any("[[まだ無いページ]]" in w for w in warnings)
    deploy = (out / "ガイド" / "運用" / "デプロイ手順.aspx").read_text(encoding="utf-8")
    assert '<a class="wikilink" href="障害対応.aspx">障害対応</a>' in deploy
    assert '<a class="wikilink" href="#手順">手順</a>' in deploy
    assert '<h2 id="手順">手順</h2>' in deploy


def test_japanese_heading_anchor(tmp_path):
    out = _build(tmp_path)
    api = (out / "リファレンス" / "api.html").read_text(encoding="utf-8")
    assert '<h2 id="エンドポイント">' in api


def test_wikilink_nfd_filename(tmp_path):
    import unicodedata

    src = tmp_path / "src"
    src.mkdir()
    (src / unicodedata.normalize("NFD", "デプロイ.md")).write_text("x", encoding="utf-8")
    (src / "top.md").write_text("[[デプロイ]]", encoding="utf-8")
    build(str(src), str(tmp_path / "o"), log=lambda m: None, warn=lambda m: None)
    top = (tmp_path / "o" / "top.html").read_text(encoding="utf-8")
    assert 'class="wikilink" href=' in top


def test_empty_wikilink_is_left_as_text():
    html = parser.render_markdown("見出し [[ ]] と [[|x]]", [".md"], ".html")
    assert "[[ ]]" in html and "[[|x]]" in html


def test_link_text_uses_title(tmp_path):
    out = _build(tmp_path)
    top = (out / "はじめに.html").read_text(encoding="utf-8")
    deploy = 'href="ガイド/運用/デプロイ手順.html"'
    # [[ファイル名]] はリンク先の title で表示、[[x|表示名]] はそのまま
    assert f'<a class="wikilink" {deploy}>デプロイのやり方</a>' in top
    # [](x.md) / [ファイル名](x.md) / [パス](x.md) は title で表示
    assert top.count(f"<a {deploy}>本番環境へのデプロイ</a>") == 3
    # 表示名を書いたものはそのまま
    assert f"<a {deploy}>手順書はこちら</a>" in top
    # 見出しつきは「title > 見出し」
    assert '<a href="リファレンス/api.html#エンドポイント">api &gt; エンドポイント</a>' in top
    # 外部リンクや画像は触らない
    html = parser.render_markdown("[a.md](https://x.test/a.md)", [".md"], ".html", link_title=lambda p: "T")
    assert 'data-label="a.md"' in html and "T" not in html


def test_wikilink_without_label_uses_title(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "p.md").write_text("---\ntitle: ページP\n---\n## 節\n", encoding="utf-8")
    (src / "top.md").write_text("[[p]] [[p#節]] [[p|自分で]] [x](p.md)", encoding="utf-8")
    build(str(src), str(tmp_path / "o"), log=lambda m: None, warn=lambda m: None)
    top = (tmp_path / "o" / "top.html").read_text(encoding="utf-8")
    assert '<a class="wikilink" href="p.html">ページP</a>' in top
    assert '<a class="wikilink" href="p.html#節">ページP &gt; 節</a>' in top
    assert '<a class="wikilink" href="p.html">自分で</a>' in top
    assert '<a href="p.html">x</a>' in top


def test_is_external_link():
    assert parser.is_external_link("https://example.com/a.md")
    assert parser.is_external_link("http://example.com")
    assert parser.is_external_link("//example.com/x")
    assert not parser.is_external_link("page.md")
    assert not parser.is_external_link("../a/b.pdf")
    assert not parser.is_external_link("#top")
    assert not parser.is_external_link("mailto:a@example.com")


def test_external_icon_on_by_default():
    md = "[外](https://example.com) [内](page.md) <https://example.com/x> [[p]]"
    html = parser.render_markdown(md, [".md"], ".html", wiki_resolver=lambda t: ("p.html", "P"))
    # 表示名は消してアイコンだけにし、表示名は data-label / aria-label に入れる
    assert '<a aria-label="外" class="external" data-label="外" href="https://example.com"></a>' in html
    assert 'data-label="https://example.com/x"' in html
    assert '<a href="page.html">内</a>' in html
    assert '<a class="wikilink" href="p.html">P</a>' in html


def test_external_icon_off():
    html = parser.render_markdown("[外](https://example.com)", [".md"], ".html", external_icon=False)
    assert '<a href="https://example.com">外</a>' in html


def test_cli_external_icon_option(tmp_path):
    on, off = tmp_path / "on", tmp_path / "off"
    assert cli.main([str(SAMPLES), "-o", str(on)]) == 0
    assert cli.main([str(SAMPLES), "-o", str(off), "--no-external-icon"]) == 0
    page = Path("ガイド") / "環境構築.html"
    assert 'class="external"' in (on / page).read_text(encoding="utf-8")
    assert 'class="external"' not in (off / page).read_text(encoding="utf-8")


def test_external_icon_label_details():
    md = "[**太字** と `code`](https://e.test) [![画像](a.png)](https://e.test/img) []()"
    html = parser.render_markdown(md, [".md"], ".html")
    # 書式つきの表示名は文字だけを取り出す
    assert 'data-label="太字 と code"' in html
    assert "<strong>" not in html
    # 画像を囲んだリンクは画像を残す（アイコン化しない）
    assert '<img alt="画像" src="a.png"' in html
    assert 'data-label="画像"' not in html
    # 表示名が " の場合もエスケープされる
    html = parser.render_markdown('[a"b](https://e.test)', [".md"], ".html")
    assert 'data-label="a&quot;b"' in html


def test_leading_h1_is_dropped():
    html = parser.render_markdown("# タイトル\n\n本文\n\n# 後の見出し\n", [".md"], ".html")
    assert "タイトル" not in html
    assert "後の見出し" in html
    # 先頭が見出し1でなければそのまま
    html = parser.render_markdown("前置き\n\n# 見出し\n", [".md"], ".html")
    assert "<h1" in html


def test_page_title_not_duplicated(tmp_path):
    out = _build(tmp_path)
    page = (out / "ガイド" / "運用" / "障害対応.html").read_text(encoding="utf-8")
    assert page.count("<h1") == 1
