"""OKF ファイル（Markdown + YAML frontmatter）の読み込みと変換。"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import markdown
import yaml
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

_FRONTMATTER_RE = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)


def split_frontmatter(text: str) -> Tuple[Optional[dict], str, Optional[str]]:
    """本文から frontmatter を取り出す。

    戻り値は (frontmatter, 本文, 警告メッセージ)。frontmatter が無い・不正な場合は None。
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None, text.lstrip("﻿"), None
    body = text[m.end():]
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        problem = getattr(e, "problem", None) or str(e).splitlines()[0]
        where = f"（{mark.line + 2} 行目）" if mark is not None else ""  # +2: 0 始まりと先頭の --- の分
        return None, body, f"frontmatter の YAML が不正です{where}: {problem}"
    if data is None:
        return {}, body, None
    if not isinstance(data, dict):
        return None, body, "frontmatter がキー/値の形式ではありません"
    return data, body, None


def _scalar(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.isoformat()
    return str(v)


def _is_scalar(v: Any) -> bool:
    return not isinstance(v, (dict, list, tuple, set))


def format_value(v: Any) -> List[str]:
    """frontmatter の値を表示用の行のリストにする。"""
    if isinstance(v, (list, tuple)) and all(_is_scalar(x) for x in v):
        return [", ".join(_scalar(x) for x in v)]
    if not _is_scalar(v):
        dumped = yaml.safe_dump(v, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return dumped.rstrip("\n").splitlines() or [""]
    text = _scalar(v).rstrip("\n")
    return text.splitlines() or [""]


class _LinkRewriter(Treeprocessor):
    def __init__(self, md, source_exts: Iterable[str], out_ext: str):
        super().__init__(md)
        self.source_exts = tuple(e.lower() for e in source_exts)
        self.out_ext = out_ext

    def run(self, root):
        for a in root.iter("a"):
            href = a.get("href")
            if href:
                a.set("href", rewrite_link(href, self.source_exts, self.out_ext))


class _LinkRewriteExtension(Extension):
    def __init__(self, source_exts: Iterable[str], out_ext: str):
        super().__init__()
        self.source_exts = source_exts
        self.out_ext = out_ext

    def extendMarkdown(self, md):
        md.treeprocessors.register(_LinkRewriter(md, self.source_exts, self.out_ext), "okf_links", 0)


def rewrite_link(href: str, source_exts: Iterable[str], out_ext: str) -> str:
    """相対リンク先が OKF ファイルなら、拡張子を出力形式のものに置き換える。"""
    parts = urlsplit(href)
    if parts.scheme or parts.netloc or not parts.path:
        return href
    lower = parts.path.lower()
    for ext in source_exts:
        if lower.endswith(ext):
            new_path = parts.path[: -len(ext)] + out_ext
            return urlunsplit(parts._replace(path=new_path))
    return href


def render_markdown(body: str, source_exts: Iterable[str], out_ext: str) -> str:
    md = markdown.Markdown(
        extensions=[
            "tables",
            "fenced_code",
            "toc",
            "sane_lists",
            _LinkRewriteExtension(list(source_exts), out_ext),
        ],
        output_format="html",
    )
    return md.convert(body)
