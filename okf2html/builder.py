"""OKF フォルダから 2 ペインの静的サイトを生成する。"""
from __future__ import annotations

import posixpath
import shutil
import unicodedata
from dataclasses import dataclass, field
from html import escape
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import parser, template

FORMATS = {"html": ".html", "aspx": ".aspx"}

# 本文から参照されることの多いファイルは、そのまま出力先へコピーする
ASSET_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".pdf"}


class BuildError(Exception):
    pass


@dataclass
class Page:
    src: Path
    rel: PurePosixPath  # 入力フォルダからの相対パス（元の拡張子）
    out_rel: str  # 出力フォルダからの相対パス（posix 形式）
    title: str
    meta: Optional[dict]
    body: str


@dataclass
class Folder:
    name: str
    path: str  # 入力フォルダからの相対パス（ルートは ""）
    folders: Dict[str, "Folder"] = field(default_factory=dict)
    pages: List[Page] = field(default_factory=list)


def _sort_key(s: str) -> str:
    return s.casefold()


def _title_for(meta: Optional[dict], src: Path) -> str:
    if meta:
        t = meta.get("title")
        if t is not None and str(t).strip():
            return str(t).strip()
    return src.stem


def _rel_href(from_out_rel: str, to_out_rel: str) -> str:
    start = posixpath.dirname(from_out_rel) or "."
    return posixpath.relpath(to_out_rel, start)


def _is_hidden(rel: PurePosixPath) -> bool:
    return any(p.startswith(".") for p in rel.parts)


def _build_tree(pages: Sequence[Page]) -> Folder:
    root = Folder(name="", path="")
    for page in pages:
        node = root
        acc: List[str] = []
        for part in page.rel.parts[:-1]:
            acc.append(part)
            node = node.folders.setdefault(part, Folder(name=part, path="/".join(acc)))
        node.pages.append(page)
    return root


def _render_nav(node: Folder, current_out: str, index_out: str, site_title: str) -> str:
    current_dir = posixpath.dirname(current_out)

    def contains_current(folder: Folder) -> bool:
        return current_dir == folder.path or current_dir.startswith(folder.path + "/")

    def render(folder: Folder) -> str:
        out: List[str] = []
        for page in sorted(folder.pages, key=lambda p: (_sort_key(p.title), p.out_rel)):
            cls = "page current" if page.out_rel == current_out else "page"
            aria = ' aria-current="page"' if page.out_rel == current_out else ""
            out.append(
                f'<a class="{cls}"{aria} href="{escape(_rel_href(current_out, page.out_rel))}">'
                f"{escape(page.title)}</a>"
            )
        for name in sorted(folder.folders, key=_sort_key):
            sub = folder.folders[name]
            is_open = " open" if contains_current(sub) else ""
            out.append(
                f'<details class="folder"{is_open}><summary>{escape(sub.name)}</summary>'
                f'<div class="folder-body">{render(sub)}</div></details>'
            )
        return "".join(out)

    home_cls = "site-title current" if current_out == index_out else "site-title"
    return (
        f'<a class="{home_cls}" href="{escape(_rel_href(current_out, index_out))}">{escape(site_title)}</a>'
        f'<div class="nav-tree">{render(node)}</div>'
    )


def _norm(s: str) -> str:
    # macOS のファイル名は濁点が分解された形（NFD）のことがあるので揃える
    return unicodedata.normalize("NFC", s).casefold()


class WikiIndex:
    """[[リンク先]] を出力ページに対応づける。

    探す順番: 今のページからの相対パス → 入力フォルダからのパス → ファイル名 → title
    """

    def __init__(self, pages: Sequence[Page], source_exts: Sequence[str]):
        self.source_exts = tuple(source_exts)
        self.by_path: Dict[str, Page] = {}
        self.by_stem: Dict[str, List[Page]] = {}
        self.by_title: Dict[str, List[Page]] = {}
        for p in pages:
            no_ext = p.rel.with_suffix("").as_posix()
            self.by_path[_norm(no_ext)] = p
            self.by_stem.setdefault(_norm(p.rel.stem), []).append(p)
            self.by_title.setdefault(_norm(p.title), []).append(p)

    def _strip_ext(self, target: str) -> str:
        for ext in self.source_exts:
            if target.lower().endswith(ext):
                return target[: -len(ext)]
        return target

    def find(self, target: str, current: Page) -> Optional[Page]:
        target = self._strip_ext(target.strip().replace("\\", "/")).strip("/")
        if not target:
            return None
        cur_dir = posixpath.dirname(current.rel.as_posix())
        for path in (posixpath.join(cur_dir, target), target):
            hit = self.by_path.get(_norm(posixpath.normpath(path)))
            if hit:
                return hit
        if "/" not in target:
            same_dir_first = lambda p: (posixpath.dirname(p.rel.as_posix()) != cur_dir, len(p.rel.parts), p.out_rel)
            for table in (self.by_stem, self.by_title):
                found = table.get(_norm(target))
                if found:
                    return sorted(found, key=same_dir_first)[0]
        return None

    def resolver(self, current: Page, warn: Callable[[str], None]) -> Callable[[str], Optional[Tuple[str, str]]]:
        """[[リンク先]] → (href, title)"""

        def resolve(target: str) -> Optional[Tuple[str, str]]:
            hit = self.find(target, current)
            if hit is None:
                warn(f"警告: {current.rel}: リンク先が見つかりません: [[{target}]]")
                return None
            return _rel_href(current.out_rel, hit.out_rel), hit.title

        return resolve

    def link_title(self, current: Page) -> Callable[[str], Optional[str]]:
        """[表示名](パス) のパス → リンク先ページの title（パスは今のページからの相対）"""

        def title_for(path: str) -> Optional[str]:
            path = self._strip_ext(path.replace("\\", "/"))
            if not path or path.startswith("/"):
                return None
            cur_dir = posixpath.dirname(current.rel.as_posix())
            hit = self.by_path.get(_norm(posixpath.normpath(posixpath.join(cur_dir, path))))
            return hit.title if hit else None

        return title_for


def render_frontmatter(meta: Optional[dict]) -> str:
    if not meta:
        return ""
    rows: List[str] = []
    for key, value in meta.items():
        lines = parser.format_value(value)
        if len(lines) <= 1:
            cell = escape(lines[0] if lines else "")
        else:
            rest = "\n".join(lines[1:])
            cell = (
                "<details><summary>"
                f'<span class="fm-first">{escape(lines[0])}</span>'
                f'<span class="fm-more">…（+{len(lines) - 1}行）</span>'
                f'</summary><div class="fm-rest">{escape(rest)}</div></details>'
            )
        rows.append(f"<tr><th>{escape(str(key))}</th><td>{cell}</td></tr>")
    # 表は最初は閉じておき、クリックで開く
    return (
        '<details class="frontmatter-block">'
        f'<summary>frontmatter<span class="fm-count">{len(rows)} 項目</span></summary>'
        f'<table class="frontmatter">{"".join(rows)}</table></details>'
    )


def _render_index_body(root: Folder, index_out: str) -> str:
    def render(folder: Folder) -> str:
        items: List[str] = []
        for page in sorted(folder.pages, key=lambda p: (_sort_key(p.title), p.out_rel)):
            items.append(f'<li><a href="{escape(_rel_href(index_out, page.out_rel))}">{escape(page.title)}</a></li>')
        for name in sorted(folder.folders, key=_sort_key):
            sub = folder.folders[name]
            items.append(f'<li class="index-folder">{escape(sub.name)}{render(sub)}</li>')
        return f"<ul>{''.join(items)}</ul>" if items else ""

    return f'<div class="index-list">{render(root)}</div>'


def build(
    input_dir: str,
    output_dir: str,
    fmt: str = "html",
    site_title: Optional[str] = None,
    exts: Sequence[str] = (".md",),
    external_icon: bool = True,
    log: Callable[[str], None] = print,
    warn: Callable[[str], None] = print,
) -> int:
    """サイトを生成し、生成したページ数を返す。"""
    if fmt not in FORMATS:
        raise BuildError(f"未対応の形式です: {fmt}（html か aspx を指定してください）")
    out_ext = FORMATS[fmt]
    src_root = Path(input_dir).resolve()
    dst_root = Path(output_dir).resolve()
    if not src_root.is_dir():
        raise BuildError(f"入力フォルダが見つかりません: {input_dir}")
    if dst_root == src_root:
        raise BuildError("出力フォルダは入力フォルダと別にしてください")
    exts = tuple(e.lower() if e.startswith(".") else "." + e.lower() for e in exts)
    site_title = site_title or src_root.name

    def under_output(p: Path) -> bool:
        return p == dst_root or dst_root in p.parents

    sources: List[Path] = []
    assets: List[Path] = []
    for p in sorted(src_root.rglob("*")):
        if not p.is_file() or under_output(p):
            continue
        rel = PurePosixPath(p.relative_to(src_root).as_posix())
        if _is_hidden(rel):
            continue
        if p.suffix.lower() in exts:
            sources.append(p)
        elif p.suffix.lower() in ASSET_EXTS:
            assets.append(p)

    if not sources:
        raise BuildError(f"{', '.join(exts)} のファイルが見つかりません: {input_dir}")

    pages: List[Page] = []
    for src in sources:
        rel = PurePosixPath(src.relative_to(src_root).as_posix())
        try:
            text = src.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            warn(f"警告: UTF-8 として読めないためスキップしました: {rel}")
            continue
        meta, body, problem = parser.split_frontmatter(text)
        if problem:
            warn(f"警告: {rel}: {problem}")
        out_rel = rel.with_suffix(out_ext).as_posix()
        pages.append(Page(src, rel, out_rel, _title_for(meta, src), meta, body))

    index_out = "index" + out_ext
    has_own_index = any(p.out_rel.lower() == index_out for p in pages)
    css = template.load_css()
    tree = _build_tree(pages)
    dst_root.mkdir(parents=True, exist_ok=True)

    def write(out_rel: str, html: str) -> None:
        dest = dst_root / Path(*out_rel.split("/"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)

    wiki = WikiIndex(pages, exts)
    total = len(pages)
    for i, page in enumerate(pages, 1):
        body_html = parser.render_markdown(
            page.body, exts, out_ext, wiki.resolver(page, warn), wiki.link_title(page), external_icon
        )
        content = render_frontmatter(page.meta) + '<div class="body">' + body_html + "</div>"
        html = template.render_page(
            title=page.title,
            site_title=site_title,
            css=css,
            nav=_render_nav(tree, page.out_rel, index_out, site_title),
            heading=page.title,
            content=content,
        )
        write(page.out_rel, html)
        log(f"[{i}/{total}] {page.rel} -> {page.out_rel}")

    if not has_own_index:
        html = template.render_page(
            title=site_title,
            site_title=site_title,
            css=css,
            nav=_render_nav(tree, index_out, index_out, site_title),
            heading=site_title,
            content=_render_index_body(tree, index_out),
        )
        write(index_out, html)
        log(f"一覧ページ -> {index_out}")

    for asset in assets:
        dest = dst_root / asset.relative_to(src_root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, dest)
    if assets:
        log(f"画像などのファイルを {len(assets)} 件コピーしました")

    log(f"完了: {total} ページを {dst_root} に出力しました")
    return total
