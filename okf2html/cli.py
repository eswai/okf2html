"""コマンドライン版。"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .builder import FORMATS, BuildError, build


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="okf2html",
        description="OKF（Markdown + YAML frontmatter）から 2 ペインの静的サイトを生成します。",
    )
    p.add_argument("input", help="OKF ファイルのあるフォルダ（サブフォルダも対象）")
    p.add_argument("-o", "--output", required=True, help="出力先フォルダ")
    p.add_argument("-f", "--format", choices=sorted(FORMATS), default="html", help="出力形式（既定: html）")
    p.add_argument("-t", "--title", help="サイト名（既定: 入力フォルダ名）")
    p.add_argument("--ext", default=".md", help="対象の拡張子。カンマ区切りで複数指定可（既定: .md）")
    p.add_argument(
        "--external-icon",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="外部リンク（http/https）を表示名なしのアイコンにし、表示名はマウスを乗せたときに出す（既定: する。--no-external-icon でしない）",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _safe_stdio() -> None:
    # 文字コードの合わない端末でも、表示できない文字で落ちないようにする
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace", line_buffering=True)  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def main(argv: Optional[List[str]] = None) -> int:
    _safe_stdio()
    args = _make_parser().parse_args(argv)
    exts = [e.strip() for e in args.ext.split(",") if e.strip()]
    try:
        build(
            args.input,
            args.output,
            fmt=args.format,
            site_title=args.title,
            exts=exts,
            external_icon=args.external_icon,
            log=lambda m: print(m, flush=True),
            warn=lambda m: print(m, file=sys.stderr, flush=True),
        )
    except BuildError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"エラー: ファイルの読み書きに失敗しました: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
