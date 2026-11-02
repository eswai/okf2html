"""ページの HTML テンプレート。"""
from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template

PAGE = Template(
    """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="okf2html">
<title>$title</title>
<style>
$css
</style>
</head>
<body>
<div class="layout">
<nav class="sidebar" aria-label="ページ一覧">
$nav
</nav>
<main class="content">
<article>
<h1 class="page-title">$heading</h1>
$content
</article>
</main>
</div>
</body>
</html>
"""
)


def load_css() -> str:
    return (Path(__file__).with_name("style.css")).read_text(encoding="utf-8")


def render_page(*, title: str, site_title: str, css: str, nav: str, heading: str, content: str) -> str:
    full_title = title if title == site_title else f"{title} | {site_title}"
    return PAGE.substitute(
        title=escape(full_title),
        css=css,
        nav=nav,
        heading=escape(heading),
        content=content,
    )
