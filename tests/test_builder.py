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
