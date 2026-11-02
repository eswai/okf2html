"""簡易 GUI。生成処理は CLI を別プロセスで呼び出して行う。"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import List, Optional


def _cli_command(args: List[str]) -> List[str]:
    if getattr(sys, "frozen", False):
        # PyInstaller で単体実行ファイルにした場合は、自分自身を CLI モードで起動する
        return [sys.executable, "--cli", *args]
    return [sys.executable, "-m", "okf2html", *args]


def _open_folder(path: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.proc: Optional[subprocess.Popen] = None
        self.lines: "queue.Queue[Optional[str]]" = queue.Queue()

        root.title("okf2html")
        root.minsize(560, 420)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.title_var = tk.StringVar()
        self.ext_var = tk.StringVar(value=".md")
        self.format_var = tk.StringVar(value="html")

        frm = ttk.Frame(root, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="入力フォルダ").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(frm, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(frm, text="参照…", command=self.choose_input).grid(row=0, column=2)

        ttk.Label(frm, text="出力フォルダ").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(frm, textvariable=self.output_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(frm, text="参照…", command=self.choose_output).grid(row=1, column=2)

        ttk.Label(frm, text="サイト名").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Entry(frm, textvariable=self.title_var).grid(row=2, column=1, sticky="ew", padx=6)

        ttk.Label(frm, text="対象拡張子").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(frm, textvariable=self.ext_var, width=20).grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(frm, text="出力形式").grid(row=4, column=0, sticky="w", pady=3)
        fmt_box = ttk.Frame(frm)
        fmt_box.grid(row=4, column=1, sticky="w", padx=6)
        ttk.Radiobutton(fmt_box, text="HTML (.html)", value="html", variable=self.format_var).pack(side="left")
        ttk.Radiobutton(fmt_box, text="ASPX (.aspx)", value="aspx", variable=self.format_var).pack(side="left", padx=12)

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 6))
        self.run_btn = ttk.Button(btns, text="生成", command=self.run)
        self.run_btn.pack(side="left")
        self.open_btn = ttk.Button(btns, text="出力フォルダを開く", command=self.open_output)
        self.open_btn.pack(side="left", padx=8)

        self.log = ScrolledText(frm, height=12, state="disabled", wrap="word")
        self.log.grid(row=6, column=0, columnspan=3, sticky="nsew")
        frm.rowconfigure(6, weight=1)

    def choose_input(self) -> None:
        path = filedialog.askdirectory(title="入力フォルダを選択")
        if path:
            self.input_var.set(path)
            if not self.output_var.get():
                self.output_var.set(os.path.join(path, "_site"))

    def choose_output(self) -> None:
        path = filedialog.askdirectory(title="出力フォルダを選択")
        if path:
            self.output_var.set(path)

    def open_output(self) -> None:
        path = self.output_var.get().strip()
        if not path or not os.path.isdir(path):
            messagebox.showinfo("okf2html", "出力フォルダがまだありません。")
            return
        _open_folder(path)

    def append(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def run(self) -> None:
        src = self.input_var.get().strip()
        dst = self.output_var.get().strip()
        if not src or not dst:
            messagebox.showwarning("okf2html", "入力フォルダと出力フォルダを指定してください。")
            return
        args = [src, "-o", dst, "--format", self.format_var.get()]
        if self.title_var.get().strip():
            args += ["--title", self.title_var.get().strip()]
        if self.ext_var.get().strip():
            args += ["--ext", self.ext_var.get().strip()]

        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.run_btn.configure(state="disabled")

        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        kwargs = {}
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW: コンソール窓を出さない
        try:
            self.proc = subprocess.Popen(
                _cli_command(args),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                **kwargs,
            )
        except OSError as e:
            self.append(f"起動に失敗しました: {e}")
            self.run_btn.configure(state="normal")
            return
        threading.Thread(target=self._reader, daemon=True).start()
        self.root.after(100, self._poll)

    def _reader(self) -> None:
        assert self.proc and self.proc.stdout
        for raw in self.proc.stdout:
            self.lines.put(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
        self.proc.wait()
        self.lines.put(None)

    def _poll(self) -> None:
        try:
            while True:
                line = self.lines.get_nowait()
                if line is None:
                    code = self.proc.returncode if self.proc else 1
                    self.append("--- 完了しました ---" if code == 0 else f"--- 失敗しました（終了コード {code}） ---")
                    self.run_btn.configure(state="normal")
                    return
                self.append(line)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--cli"]:
        from .cli import main as cli_main

        return cli_main(argv[1:])
    if sys.platform == "darwin" and tk.TkVersion < 8.6:
        print(
            "警告: Tk 8.5 は最近の macOS では画面が固まることがあります。"
            "python.org 版の Python か `brew install python-tk` を使ってください。",
            file=sys.stderr,
        )
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
