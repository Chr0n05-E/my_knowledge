#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知识库控制台（图形界面）

双击仓库根目录的「启动知识库.bat」即可打开；它等价于命令行里的那些 python 命令：
  · 【构建 / 体检】  = python tools/build.py      （报告直接显示在窗口里）
  · 【新建笔记】     = python tools/new.py ...    （表单填好点一下）
  · 【打开图谱网页】 = 用浏览器打开 out/index.html
  · 【打开 Obsidian】= 定位到对应笔记，直接开始写

只用 Python 标准库（tkinter），不需要安装任何东西。
"""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import quote

import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

# ---------------------------------------------------------------- 基本路径
ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "notes"
BUILD_PY = ROOT / "tools" / "build.py"
NEW_PY = ROOT / "tools" / "new.py"
CONFIG = ROOT / "kb.config.yml"
VAULT_NAME = ROOT.name
PYTHON = sys.executable
# 如果界面是用 pythonw（无控制台）启动的，子进程改用 python.exe，输出管道更稳
if os.name == "nt" and Path(PYTHON).name.lower() == "pythonw.exe":
    _cand = Path(PYTHON).with_name("python.exe")
    if _cand.exists():
        PYTHON = str(_cand)
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

FM_RE = re.compile(r"^---\s*\r?\n(.*?)\r?\n---", re.S)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def output_html() -> Path:
    """从 kb.config.yml 读 output_html；读不到就用默认 out/index.html。"""
    default = ROOT / "out" / "index.html"
    try:
        text = CONFIG.read_text(encoding="utf-8")
    except OSError:
        return default
    m = re.search(r"^output_html\s*:\s*(\S+)", text, re.M)
    return (ROOT / m.group(1).strip().strip("\"'")) if m else default


def slugify(s: str) -> str:
    """把标题变成能当文件名用的 id 末段（中文保留，空格变短横线）。"""
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff\-_]", "", s)
    return s.strip("-")


def scan_notes() -> list[dict]:
    """扫一遍 notes/，返回每条笔记的 id / 标题 / 类型。"""
    items: list[dict] = []
    if not NOTES.exists():
        return items
    for p in sorted(NOTES.rglob("*.md")):
        rel = p.relative_to(NOTES)
        if any(part.startswith(".") for part in rel.parts):   # 跳过 .obsidian / .trash
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        m = FM_RE.match(text)
        fm = m.group(1) if m else ""
        title, ntype = "", ""
        for line in fm.splitlines():
            key, _, val = line.partition(":")
            key, val = key.strip().lower(), val.strip().strip("\"'")
            if key == "title" and val:
                title = val
            elif key == "type" and val:
                ntype = val
        if not title:
            h = H1_RE.search(text)
            title = h.group(1).strip() if h else p.stem
        items.append({
            "id": rel.with_suffix("").as_posix(),
            "title": title,
            "type": ntype or "domain",
            "path": p,
        })
    return items


def run_script(script: Path, args: list[str]) -> tuple[int, str]:
    """在库根目录下跑一个脚本，合并 stdout/stderr 返回。"""
    proc = subprocess.run(
        [PYTHON, str(script), *args],
        cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    return proc.returncode, proc.stdout or ""


# ---------------------------------------------------------------- 界面
class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("知识库控制台")
        self.geometry("1060x700")
        self.minsize(860, 540)
        self.option_add("*Font", ("Microsoft YaHei UI", 10))

        self.q: queue.Queue = queue.Queue()
        self.busy = False
        self.notes: list[dict] = []

        self._build_toolbar()
        self._build_body()
        self._build_status()

        self.refresh()
        self.after(80, self._pump)
        self.log(f"知识库位置：{ROOT}", "dim")
        self.log("点【构建 / 体检】生成网页；点【新建笔记】开始写。\n", "dim")

    # ---------------- 顶部按钮条
    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self, padding=(10, 8, 10, 4))
        bar.pack(fill="x")

        def btn(text, cmd, width=None):
            b = ttk.Button(bar, text=text, command=cmd, width=width)
            b.pack(side="left", padx=(0, 6))
            return b

        self.b_build = btn("构建 / 体检", self.do_build, 12)
        self.b_web = btn("打开图谱网页", self.open_web, 12)
        self.b_obs = btn("打开 Obsidian", self.open_obsidian, 12)
        btn("打开 notes 文件夹", lambda: self._open_path(NOTES), 16)
        btn("刷新列表", self.refresh, 10)

    # ---------------- 主体：左树 + 右表单/报告
    def _build_body(self) -> None:
        pane = ttk.Panedwindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # 左：笔记树
        left = ttk.Frame(pane)
        pane.add(left, weight=1)
        ttk.Label(left, text="笔记（双击 = 在 Obsidian 里打开）").pack(anchor="w", pady=(0, 4))
        self.tree = ttk.Treeview(left, columns=("type",), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="标题")
        self.tree.heading("type", text="类型")
        self.tree.column("#0", width=215, stretch=True)
        self.tree.column("type", width=60, stretch=False, anchor="center")
        self.tree.tag_configure("concept", foreground="#666666")
        vs = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._tree_open)

        # 右：表单 + 报告
        right = ttk.Frame(pane)
        pane.add(right, weight=2)

        form = ttk.LabelFrame(right, text="新建笔记", padding=10)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="标题").grid(row=0, column=0, sticky="w", pady=3)
        self.e_title = ttk.Entry(form)
        self.e_title.grid(row=0, column=1, columnspan=3, sticky="ew", pady=3)
        self.e_title.bind("<KeyRelease>", self._autofill_seg)

        ttk.Label(form, text="父节点").grid(row=1, column=0, sticky="w", pady=3)
        self.cb_parent = ttk.Combobox(form, state="readonly", values=["（顶层，没有上级）"])
        self.cb_parent.current(0)
        self.cb_parent.grid(row=1, column=1, columnspan=3, sticky="ew", pady=3)

        ttk.Label(form, text="类型").grid(row=2, column=0, sticky="w", pady=3)
        self.v_type = tk.StringVar(value="concept")
        ttk.Radiobutton(form, text="概念（叶子，要有「我的理解」）", value="concept",
                        variable=self.v_type).grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(form, text="分支 / 领域", value="domain",
                        variable=self.v_type).grid(row=2, column=2, sticky="w")

        ttk.Label(form, text="标签").grid(row=3, column=0, sticky="w", pady=3)
        self.e_tags = ttk.Entry(form)
        self.e_tags.grid(row=3, column=1, columnspan=3, sticky="ew", pady=3)

        ttk.Label(form, text="文件名").grid(row=4, column=0, sticky="w", pady=3)
        self.e_seg = ttk.Entry(form)
        self.e_seg.grid(row=4, column=1, sticky="ew", pady=3)
        ttk.Label(form, text="（自动填，可改；不能有空格）",
                  foreground="#777777").grid(row=4, column=2, columnspan=2, sticky="w")

        self.v_open_after = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="创建后直接打开这篇笔记", variable=self.v_open_after
                        ).grid(row=5, column=1, sticky="w", pady=(6, 0))
        self.b_create = ttk.Button(form, text="创建笔记", command=self.do_create)
        self.b_create.grid(row=5, column=3, sticky="e", pady=(6, 0))

        rep = ttk.LabelFrame(right, text="报告", padding=(8, 4))
        rep.pack(fill="both", expand=True, pady=(10, 0))
        self.report = ScrolledText(rep, height=14, wrap="none", font=("Consolas", 9),
                                   background="#14161c", foreground="#d8dce6",
                                   insertbackground="#d8dce6", borderwidth=0)
        self.report.pack(fill="both", expand=True)
        self.report.tag_configure("warn", foreground="#e8c15a")
        self.report.tag_configure("err", foreground="#ff7b72")
        self.report.tag_configure("ok", foreground="#6ee7a0")
        self.report.tag_configure("dim", foreground="#8b93a5")
        self.report.configure(state="disabled")

    def _build_status(self) -> None:
        self.status = ttk.Label(self, text="", anchor="w", padding=(12, 4))
        self.status.pack(fill="x")

    # ---------------- 工具方法
    def log(self, text: str, tag: str | None = None) -> None:
        text = ANSI_RE.sub("", text)
        self.report.configure(state="normal")
        for line in text.splitlines(True):
            t = tag
            if t is None:
                s = line.strip()
                if s.startswith("警告") or " 警告 " in line:
                    t = "warn"
                elif s.startswith("错误") or " 错误 " in line:
                    t = "err"
                elif "提示" in line:
                    t = "dim"
                elif "全部通过" in line:
                    t = "ok"
                else:
                    t = None
            self.report.insert("end", line, t or "")
        self.report.see("end")
        self.report.configure(state="disabled")

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.b_build, self.b_create):
            b.configure(state=state)
        self.status.configure(text="正在运行…" if busy else self.status.cget("text"))

    def run_async(self, label: str, script: Path, args: list[str], done=None) -> None:
        if self.busy:
            messagebox.showinfo("稍等", "上一个任务还在跑，稍等一下。")
            return
        self.set_busy(True)
        self.log(f"\n=== {label} ===", "dim")

        def work():
            try:
                code, out = run_script(script, args)
            except Exception as exc:                      # noqa: BLE001
                code, out = 1, f"执行失败：{exc}\n"
            self.q.put(("text", out))
            self.q.put(("done", (code, label, done)))

        threading.Thread(target=work, daemon=True).start()

    def _pump(self) -> None:
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "text":
                    self.log(payload)
                elif kind == "done":
                    code, label, done = payload
                    self.set_busy(False)
                    self.log(f"[{label}] 退出码 {code}\n", "ok" if code == 0 else "err")
                    self.update_status()
                    if done:
                        done(code)
        except queue.Empty:
            pass
        self.after(80, self._pump)

    def _open_path(self, path: Path) -> None:
        try:
            os.startfile(str(path))                       # noqa: S606  (Windows)
        except Exception as exc:                          # noqa: BLE001
            messagebox.showerror("打不开", f"{path}\n{exc}")

    # ---------------- 列表
    def refresh(self) -> None:
        # 按 id 排序：保证父笔记（science.md）排在子笔记（science/…）之前
        self.notes = sorted(scan_notes(), key=lambda it: it["id"])
        self.tree.delete(*self.tree.get_children())
        for it in self.notes:
            parts = it["id"].split("/")
            parent = ""
            for i in range(len(parts)):
                path = "/".join(parts[:i + 1])
                last = (i == len(parts) - 1)
                if not self.tree.exists(path):
                    self.tree.insert(parent, "end", iid=path, open=True,
                                     text=it["title"] if last else parts[i],
                                     values=(it["type"] if last else "",),
                                     tags=("concept",) if (last and it["type"] == "concept") else ())
                elif last:
                    # 该节点先被当成中间目录建出来了，这里补上真实的标题与类型
                    self.tree.item(path, text=it["title"], values=(it["type"],),
                                   tags=("concept",) if it["type"] == "concept" else ())
                parent = path
        domains = [f"{it['id']}　{it['title']}" for it in self.notes if it["type"] == "domain"]
        self.cb_parent.configure(values=["（顶层，没有上级）"] + domains)
        if self.cb_parent.current() < 0:
            self.cb_parent.current(0)
        self.update_status()
        self.log(f"列表已刷新：{len(self.notes)} 条笔记"
                 f"（领域 {sum(1 for i in self.notes if i['type'] == 'domain')} / "
                 f"概念 {sum(1 for i in self.notes if i['type'] == 'concept')}）\n", "dim")

    def update_status(self) -> None:
        stats_path = output_html().parent / "graph.json"
        try:
            d = json.loads(stats_path.read_text(encoding="utf-8"))
            s = d.get("stats", {})
            self.status.configure(
                text=f"节点 {s.get('total', 0)} · 概念 {s.get('concepts', 0)} · "
                     f"关系边 {s.get('edges', 0)}　|　上次构建 {d.get('generatedAt', '?')}")
        except Exception:                                  # noqa: BLE001
            self.status.configure(text="尚未构建（点【构建 / 体检】）")

    def _selected_id(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        iid = sel[0]
        return iid if any(it["id"] == iid for it in self.notes) else None

    def _tree_open(self, _event=None) -> None:
        nid = self._selected_id()
        if nid:
            self.open_obsidian(nid)

    # ---------------- 动作
    def do_build(self) -> None:
        self.run_async("构建 / 体检", BUILD_PY, [], done=lambda _c: self.refresh())

    def open_web(self) -> None:
        html = output_html()
        if not html.exists():
            messagebox.showinfo("还没有网页", "先点【构建 / 体检】生成网页。")
            return
        self._open_path(html)

    def open_obsidian(self, nid: str | None = None) -> None:
        if nid:
            uri = f"obsidian://open?vault={quote(VAULT_NAME)}&file={quote(nid + '.md')}"
        else:
            uri = f"obsidian://open?vault={quote(VAULT_NAME)}"
        try:
            os.startfile(uri)                              # noqa: S606
        except Exception as exc:                           # noqa: BLE001
            messagebox.showerror("打不开 Obsidian",
                                 f"{exc}\n\n如果没装 Obsidian，就先用【打开 notes 文件夹】。")

    def _autofill_seg(self, _event=None) -> None:
        seg = slugify(self.e_title.get())
        cur = self.e_seg.get()
        if not cur or cur == getattr(self, "_last_seg", ""):
            self.e_seg.delete(0, "end")
            self.e_seg.insert(0, seg)
        self._last_seg = seg

    def do_create(self) -> None:
        title = self.e_title.get().strip()
        if not title:
            messagebox.showwarning("缺少标题", "先填标题。")
            return
        seg = self.e_seg.get().strip() or slugify(title)
        if not seg or " " in seg:
            messagebox.showwarning("文件名不合法", "文件名不能为空、不能有空格。")
            return
        parent_raw = self.cb_parent.get()
        parent_id = "" if parent_raw.startswith("（顶层") else parent_raw.split("　")[0].strip()
        nid = f"{parent_id}/{seg}" if parent_id else seg
        ntype = self.v_type.get()
        args = [nid, "--title", title, "--type", ntype]
        tags = self.e_tags.get().strip()
        if tags:
            args += ["--tags", tags]
        created = {"path": NOTES / f"{nid}.md"}

        def after(code: int) -> None:
            if code != 0:
                return
            self.refresh()
            self.log(f"→ 文件：{created['path'].relative_to(ROOT)}", "ok")
            if self.v_open_after.get():
                self.open_obsidian(nid)
            self.e_title.delete(0, "end")
            self.e_seg.delete(0, "end")
            self.e_tags.delete(0, "end")
            self.run_async("构建 / 体检", BUILD_PY, [], done=lambda _c: self.refresh())

        self.run_async(f"新建笔记 {nid}", NEW_PY, args, done=after)


def main() -> None:
    if os.name == "nt":                                    # 高 DPI 下别糊
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:                                  # noqa: BLE001
            pass
    NOTES.mkdir(exist_ok=True)
    App().mainloop()


if __name__ == "__main__":
    main()
