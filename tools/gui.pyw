#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知识库控制台（图形界面）

运行 python tools/gui.pyw 即可打开；它等价于命令行里的那些 python 命令：
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
import webbrowser
from pathlib import Path
from urllib.parse import quote

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

# ---------------------------------------------------------------- 基本路径
ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "notes"
BUILD_PY = ROOT / "tools" / "build.py"
NEW_PY = ROOT / "tools" / "new.py"
CONFIG = ROOT / "kb.config.yml"
ICON = ROOT / "tools" / "kb.ico"       # 由 tools/make_icon.py 生成
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
    """把标题变成能当文件名用的 id 末段：空格与连字符统一成下划线，中文保留，大小写保持你输入的样子。"""
    s = re.sub(r"[\s\-]+", "_", s.strip())
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_]", "", s)
    return s.strip("_")


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
    def __init__(self, start_tab: str = "笔记") -> None:
        super().__init__()
        self.title("知识库控制台")
        try:                                    # 窗口与任务栏图标
            if ICON.exists():
                self.iconbitmap(default=str(ICON))
        except Exception:                       # noqa: BLE001
            pass
        self.geometry("1060x700")
        self.minsize(860, 540)
        self.option_add("*Font", ("Microsoft YaHei UI", 10))

        self.q: queue.Queue = queue.Queue()
        self.busy = False
        self.notes: list[dict] = []

        self._build_toolbar()
        self._build_body()
        self._build_status()

        if start_tab == "图谱":
            self.nb.select(1)
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

    # ---------------- 主体：两个标签页（笔记 / 图谱）
    def _build_body(self) -> None:
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        note_tab = ttk.Frame(self.nb)
        self.nb.add(note_tab, text="  笔记  ")
        graph_tab = ttk.Frame(self.nb)
        self.nb.add(graph_tab, text="  图谱  ")
        self._build_note_tab(note_tab)
        self.graph = GraphView(graph_tab, self)
        self.graph.pack(fill="both", expand=True)

    def _build_note_tab(self, parent) -> None:
        pane = ttk.Panedwindow(parent, orient="horizontal")
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
        if getattr(self, "graph", None) is not None:
            self.graph.reload()
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

    def _tree_open(self, event=None) -> None:
        """双击：点在 +/− 上只做展开/收起，不打开笔记；点在文字上才打开。"""
        if event is not None:
            try:
                element = str(self.tree.identify("element", event.x, event.y))
            except tk.TclError:
                element = ""
            if "indicator" in element:
                # 第一次按下时 Tk 自己已经切换过一次；这里什么都不做，
                # 否则"按下切一次 + 双击再切一次"会互相抵消，看起来像没反应
                return
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

    # ---------------- 供图谱页右键菜单调用
    def create_under(self, parent_id: str | None, ntype: str) -> None:
        """在图谱里右键新建：弹对话框（标题与文件名分开填），然后调 new.py + 构建。"""
        dlg = NewNodeDialog(self, parent_id, ntype)
        if not dlg.result:
            return
        r = dlg.result
        nid = f"{parent_id}/{r['seg']}" if parent_id else r["seg"]
        args = [nid, "--title", r["title"], "--type", r["type"]]
        if r["tags"]:
            args += ["--tags", r["tags"]]
        what = "分支" if r["type"] == "domain" else "概念"

        def after(code: int) -> None:
            if code != 0:
                return
            self.refresh()

            def after_build(_code: int) -> None:
                self.refresh()                     # 重新读 out\graph.json，新节点才会出现
                self.nb.select(1)
                self.graph.select(nid)

            self.run_async("构建 / 体检", BUILD_PY, [], done=after_build)

        self.run_async(f"新建{what} {nid}", NEW_PY, args, done=after)

    def locate_in_tree(self, nid: str) -> None:
        self.nb.select(0)
        if self.tree.exists(nid):
            self.tree.selection_set(nid)
            self.tree.focus(nid)
            self.tree.see(nid)

    def open_web_focus(self, nid: str) -> None:
        html = output_html()
        if not html.exists():
            messagebox.showinfo("还没有网页", "先点【构建 / 体检】生成网页。")
            return
        webbrowser.open(f"{html.as_uri()}?focus={quote(nid)}")


# ---------------------------------------------------------------- 新建节点对话框
class NewNodeDialog(simpledialog.Dialog):
    """创建节点时用的对话框：**标题**（显示名，中文即可）与**文件名**（id，建议英文）分开填。

    这就是 infosec.md 里 `title: 信息安全` 那种情况——文件名短、标题好看。
    文件名会随标题自动填一次，你改成英文后就不再自动覆盖。
    """

    def __init__(self, parent, parent_id: str | None, ntype: str):
        self.parent_id = parent_id
        self.ntype = ntype
        self.result: dict | None = None
        super().__init__(parent, title="新建" + ("分支" if ntype == "domain" else "概念"))

    def body(self, master):
        ttk.Label(master, text="挂在").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(master, text=self.parent_id or "（顶层，没有上级）",
                  foreground="#666666").grid(row=0, column=1, sticky="w", pady=2)

        ttk.Label(master, text="标题").grid(row=1, column=0, sticky="w", pady=2)
        self.e_title = ttk.Entry(master, width=40)
        self.e_title.grid(row=1, column=1, pady=2)
        self.e_title.bind("<KeyRelease>", self._sync_seg)

        ttk.Label(master, text="文件名").grid(row=2, column=0, sticky="w", pady=2)
        self.e_seg = ttk.Entry(master, width=40)
        self.e_seg.grid(row=2, column=1, pady=2)
        ttk.Label(master, text="短名，用下划线分词（如 data_structure）；大小写随你",
                  foreground="#888888").grid(row=3, column=1, sticky="w")

        ttk.Label(master, text="标签").grid(row=4, column=0, sticky="w", pady=2)
        self.e_tags = ttk.Entry(master, width=40)
        self.e_tags.grid(row=4, column=1, pady=2)
        ttk.Label(master, text="逗号分隔，可留空",
                  foreground="#888888").grid(row=5, column=1, sticky="w")

        ttk.Label(master, text="类型").grid(row=6, column=0, sticky="nw", pady=2)
        self.v_type = tk.StringVar(value=self.ntype)
        ttk.Radiobutton(master, text="概念（叶子，要有「我的理解」）",
                        value="concept", variable=self.v_type).grid(row=6, column=1, sticky="w")
        ttk.Radiobutton(master, text="分支 / 领域（下辖其他笔记）",
                        value="domain", variable=self.v_type).grid(row=7, column=1, sticky="w")
        return self.e_title

    def buttonbox(self) -> None:
        """默认按钮是英文 OK/Cancel（Tk 没带中文消息目录），这里换成中文。"""
        box = ttk.Frame(self)
        ttk.Button(box, text="创建", width=10, command=self.ok,
                   default="active").pack(side="left", padx=(0, 8), pady=6)
        ttk.Button(box, text="取消", width=10, command=self.cancel).pack(side="left", pady=6)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack(pady=(4, 8))

    def _sync_seg(self, _event=None) -> None:
        seg = slugify(self.e_title.get())
        cur = self.e_seg.get()
        if not cur or cur == getattr(self, "_last_seg", ""):
            self.e_seg.delete(0, "end")
            self.e_seg.insert(0, seg)
        self._last_seg = seg

    def validate(self) -> bool:
        title = self.e_title.get().strip()
        seg = self.e_seg.get().strip() or slugify(title)
        if not title:
            messagebox.showwarning("缺少标题", "「标题」是这篇笔记在网页/图谱里显示的名字，请填一个。",
                                   parent=self)
            return False
        if not seg or " " in seg or "/" in seg or "\\" in seg:
            messagebox.showwarning("文件名不合法",
                                   "「文件名」会成为节点 id，不能为空、不能有空格或斜杠。",
                                   parent=self)
            return False
        self.e_seg.delete(0, "end")
        self.e_seg.insert(0, seg)
        return True

    def apply(self) -> None:
        self.result = {
            "title": self.e_title.get().strip(),
            "seg": self.e_seg.get().strip(),
            "type": self.v_type.get(),
            "tags": self.e_tags.get().strip(),
        }


# ---------------------------------------------------------------- 图谱页
class GraphView(ttk.Frame):
    """把 out/graph.json 画成可交互的图。

    左键点节点 = 选中；左键双击 = 在 Obsidian 里打开；右键节点 = 新建分支 / 概念；
    拖动空白处平移；滚轮缩放。
    """

    PALETTE = ["#6aa6ff", "#f0a35e", "#5ec48a", "#c48ae0", "#e0708a",
               "#5ec4c4", "#c4b45e", "#8a9ae0", "#e0955e", "#7ad0a0"]

    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app
        self.data: dict | None = None
        self.by_id: dict[str, dict] = {}
        self.rel_by_id: dict[str, dict] = {}
        self.top_color: dict[str, str] = {}
        self.pos: dict[str, tuple[float, float]] = {}
        self._items: dict[int, str] = {}
        self.selected: str | None = None
        self.focus_id: str | None = None
        self.k = 1.0                 # 缩放
        self.tx = 0.0                # 平移：屏幕坐标 = 布局坐标 × k + (tx, ty)
        self.ty = 0.0
        self._needs_fit = True
        self._panning = False
        self._last = (0, 0)
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        bar = ttk.Frame(self, padding=(6, 6, 6, 0))
        bar.pack(fill="x")
        ttk.Button(bar, text="重新布局", command=self.relayout).pack(side="left", padx=2)
        ttk.Button(bar, text="适应窗口", command=self.fit).pack(side="left", padx=2)
        ttk.Button(bar, text="＋", width=3, command=lambda: self.zoom(1.25)).pack(side="left", padx=2)
        ttk.Button(bar, text="－", width=3, command=lambda: self.zoom(0.8)).pack(side="left", padx=2)
        self.v_focus = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="只看选中节点的邻居", variable=self.v_focus,
                        command=self.redraw).pack(side="left", padx=(10, 0))
        ttk.Label(bar, text="方向").pack(side="left", padx=(10, 2))
        self.v_dir = tk.StringVar(value="横")
        for txt, val in (("横向", "横"), ("纵向", "纵")):
            ttk.Radiobutton(bar, text=txt, value=val, variable=self.v_dir,
                            command=self.relayout).pack(side="left")
        ttk.Button(bar, text="网页版", command=self.app.open_web).pack(side="right", padx=2)
        ttk.Button(bar, text="刷新", command=self.reload).pack(side="right", padx=2)

        self.canvas = tk.Canvas(self, background="#12141a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=(4, 2))
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Double-1>", self._on_double)
        self.canvas.bind("<Button-3>", self._on_right)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Configure>", self._on_resize)

        self.info = ttk.Label(self, anchor="w", padding=(8, 1),
                              text="右键点节点 = 新建分支 / 概念　·　拖动空白处平移　·　滚轮缩放")
        self.info.pack(fill="x")
        self.legend = ttk.Frame(self, padding=(8, 0, 8, 4))
        self.legend.pack(fill="x")

    # ---------------- 数据
    def reload(self) -> None:
        try:
            self.data = json.loads((output_html().parent / "graph.json").read_text(encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            self.data = None
        self.by_id = {n["id"]: n for n in (self.data or {}).get("nodes", [])}
        self.rel_by_id = {r["id"]: r for r in (self.data or {}).get("relations", [])}
        self.top_color = {r: self.PALETTE[i % len(self.PALETTE)]
                          for i, r in enumerate((self.data or {}).get("roots", []))}
        self.selected = None
        self.focus_id = None
        self.v_focus.set(False)
        self.relayout()

    # ---------------- 层次布局（父在左，子在右；纵向可切换）
    def relayout(self) -> None:
        if not self.data or not self.by_id:
            self.redraw()
            return
        kids = {nid: [c for c in (n.get("children") or []) if c in self.by_id]
                for nid, n in self.by_id.items()}
        depth: dict[str, int] = {}
        leaves: list[str] = []

        def walk(nid: str, d: int, seen: set) -> None:
            if nid in seen:
                return
            seen.add(nid)
            depth[nid] = d
            if not kids.get(nid):
                leaves.append(nid)
            for c in kids.get(nid, []):
                walk(c, d + 1, seen)

        seen: set = set()
        for r in self.data.get("roots", []):
            if r in self.by_id:
                walk(r, 0, seen)
        for nid in self.by_id:                              # 兜底：没连上树的孤立节点
            walk(nid, 0, seen)

        slot = {nid: float(i) for i, nid in enumerate(leaves)}
        ycache: dict[str, float] = {}

        def yslot(nid: str) -> float:
            if nid not in ycache:
                ks = kids.get(nid) or []
                ycache[nid] = slot.get(nid, 0.0) if not ks else sum(yslot(c) for c in ks) / len(ks)
            return ycache[nid]

        for nid in self.by_id:
            yslot(nid)
        if self.v_dir.get() == "横":
            self.pos = {nid: (60.0 + depth.get(nid, 0) * 205.0, 40.0 + ycache[nid] * 40.0)
                        for nid in self.by_id}
        else:
            self.pos = {nid: (60.0 + ycache[nid] * 150.0, 40.0 + depth.get(nid, 0) * 86.0)
                        for nid in self.by_id}
        self.redraw()
        self._needs_fit = True
        self.fit()

    # ---------------- 绘制（视图变换：屏幕坐标 = 布局坐标 × k + (tx, ty)）
    def _sx(self, x: float) -> float:
        return x * self.k + self.tx

    def _sy(self, y: float) -> float:
        return y * self.k + self.ty

    def redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        self._items = {}
        if not self.data or not self.by_id:
            c.create_text(20, 20, anchor="nw", fill="#8b93a5",
                          text="还没有图谱数据。先去「笔记」页点【构建 / 体检】。")
            self._update_legend()
            return
        k = self.k
        vis = set(self.by_id)
        if self.focus_id and self.v_focus.get():
            vis = {self.focus_id}
            for e in self.data["edges"]:
                if e["source"] == self.focus_id:
                    vis.add(e["target"])
                elif e["target"] == self.focus_id:
                    vis.add(e["source"])
        tree_rel = self.data.get("treeRel", "parent")
        for e in self.data["edges"]:
            if e["source"] not in vis or e["target"] not in vis:
                continue
            x1, y1 = self.pos.get(e["source"], (0.0, 0.0))
            x2, y2 = self.pos.get(e["target"], (0.0, 0.0))
            r = self.rel_by_id.get(e["rel"], {})
            style = r.get("style", "dashed")
            dash = () if style == "solid" else ((6, 4) if style == "dashed" else (2, 4))
            c.create_line(self._sx(x1), self._sy(y1), self._sx(x2), self._sy(y2),
                          fill=r.get("color", "#8b93a5"), dash=dash,
                          width=max(1, int((2 if e["rel"] == tree_rel else 1) * min(k, 2))))
        label_font = ("Microsoft YaHei UI", max(7, int(9 * min(k, 1.8))))
        for nid in vis:
            n = self.by_id[nid]
            px, py = self.pos.get(nid, (0.0, 0.0))
            x, y = self._sx(px), self._sy(py)
            dom = n.get("type") == "domain"
            rad = max(3.0, (9 if dom else 6) * min(k, 2.0))
            color = self.top_color.get(n.get("top", ""), "#8b93a5")
            sel = (nid == self.selected)
            self._items[c.create_oval(x - rad, y - rad, x + rad, y + rad, fill=color,
                                      outline="#ffffff" if sel else color,
                                      width=3 if sel else 1)] = nid
            self._items[c.create_text(x + rad + 5, y, text=n["title"], anchor="w",
                                      font=label_font,
                                      fill="#e6e9f0" if dom else "#b9c0cf")] = nid
        self._update_legend()

    def _update_legend(self) -> None:
        for w in self.legend.winfo_children():
            w.destroy()
        if not self.data:
            return
        counts: dict[str, int] = {}
        for e in self.data["edges"]:
            counts[e["rel"]] = counts.get(e["rel"], 0) + 1
        for r in self.data.get("relations", []):
            if counts.get(r["id"]):
                tk.Label(self.legend, text=f"● {r['label']} {counts[r['id']]}",
                         foreground=r.get("color", "#8b93a5")).pack(side="left", padx=6)

    # ---------------- 交互
    def _node_at(self, event) -> str | None:
        for item in self.canvas.find_overlapping(event.x - 3, event.y - 3, event.x + 3, event.y + 3):
            if item in self._items:
                return self._items[item]
        return None

    def _on_click(self, event) -> None:
        nid = self._node_at(event)
        self._panning = nid is None
        self._last = (event.x, event.y)
        self.selected = nid
        self.redraw()
        self._show_info(nid)

    def _on_drag(self, event) -> None:
        if not self._panning:
            return
        dx, dy = event.x - self._last[0], event.y - self._last[1]
        self._last = (event.x, event.y)
        self.tx += dx
        self.ty += dy
        self.canvas.move("all", dx, dy)          # 直接搬动画布更快，同时同步 tx/ty

    def _on_double(self, event) -> None:
        nid = self._node_at(event)
        if nid:
            self.app.open_obsidian(nid)

    def _on_wheel(self, event) -> None:
        self.zoom(1.15 if event.delta > 0 else 1 / 1.15, event.x, event.y)

    def zoom(self, f: float, cx: float | None = None, cy: float | None = None) -> None:
        """以 (cx, cy) 为锚点缩放；不传就按画布中心。缩放后不改变你所看的位置。"""
        target = max(0.15, min(4.0, self.k * f))
        f = target / self.k
        if abs(f - 1.0) < 1e-6:
            return
        cx = self.canvas.winfo_width() / 2 if cx is None else cx
        cy = self.canvas.winfo_height() / 2 if cy is None else cy
        self.tx = cx - (cx - self.tx) * f
        self.ty = cy - (cy - self.ty) * f
        self.k = target
        self.redraw()

    def fit(self) -> None:
        """把整张图放进画布中央。"""
        self.canvas.update_idletasks()
        if not self.pos:
            self.redraw()
            return
        xs = [p[0] for p in self.pos.values()]
        ys = [p[1] for p in self.pos.values()]
        w = max(1.0, max(xs) - min(xs))
        h = max(1.0, max(ys) - min(ys))
        W = max(80, self.canvas.winfo_width())
        H = max(80, self.canvas.winfo_height())
        self.k = max(0.15, min(1.8, min((W - 80) / (w + 200), (H - 80) / (h + 70))))
        self.tx = W / 2 - (min(xs) + max(xs)) / 2 * self.k
        self.ty = H / 2 - (min(ys) + max(ys)) / 2 * self.k
        self.redraw()

    def _on_resize(self, _event=None) -> None:
        # 画布第一次拿到真实尺寸时自动适应一次；之后用户自己平移/缩放过就不打扰他
        if getattr(self, "_needs_fit", False):
            self._needs_fit = False
            self.after(20, self.fit)

    def _center_on(self, nid: str) -> None:
        p = self.pos.get(nid)
        if not p:
            return
        self.tx = self.canvas.winfo_width() / 2 - p[0] * self.k
        self.ty = self.canvas.winfo_height() / 2 - p[1] * self.k
        self.redraw()

    def select(self, nid: str) -> None:
        if nid not in self.by_id:
            return
        self.selected = nid
        self.redraw()
        self._center_on(nid)
        self._show_info(nid)

    def focus(self, nid: str | None) -> None:
        self.focus_id = nid
        self.v_focus.set(bool(nid))
        if nid:
            self.selected = nid
        self.redraw()
        if nid:
            self._center_on(nid)
        self._show_info(nid)

    def _copy(self, nid: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(nid)
        self.info.configure(text=f"已复制 id：{nid}")

    def _show_info(self, nid: str | None) -> None:
        if not nid or nid not in self.by_id:
            self.info.configure(
                text="右键点节点 = 新建分支 / 概念　·　左键双击 = 在 Obsidian 打开　·　拖动空白处平移　·　滚轮缩放")
            return
        n = self.by_id[nid]
        ups = [self.by_id[p]["title"] for p in (n.get("parents") or []) if p in self.by_id]
        downs = [self.by_id[c]["title"] for c in (n.get("children") or []) if c in self.by_id]
        tree_rel = (self.data or {}).get("treeRel", "parent")
        rel_txt = "、".join(f"{self.rel_by_id.get(e['rel'], {}).get('label', e['rel'])}"
                            for e in self.data["edges"]
                            if e["source"] == nid and e["rel"] != tree_rel) or "—"
        self.info.configure(
            text=f"{n['title']}（{n.get('type')}）　上级：{'、'.join(ups) or '—'}　"
                 f"下级：{'、'.join(downs) or '—'}　其他关系：{rel_txt}　id：{nid}")

    # ---------------- 右键菜单
    def _node_menu(self, nid: str) -> tk.Menu:
        n = self.by_id[nid]
        m = tk.Menu(self, tearoff=0)
        m.add_command(label=f"{n['title']}", state="disabled")
        m.add_separator()
        m.add_command(label="在此节点下新建分支…",
                      command=lambda: self.app.create_under(nid, "domain"))
        m.add_command(label="在此节点下新建概念…",
                      command=lambda: self.app.create_under(nid, "concept"))
        m.add_separator()
        m.add_command(label="在 Obsidian 里打开", command=lambda: self.app.open_obsidian(nid))
        m.add_command(label="在「笔记」列表里定位", command=lambda: self.app.locate_in_tree(nid))
        m.add_command(label="只看它和邻居", command=lambda: self.focus(nid))
        if self.focus_id:
            m.add_command(label="取消聚焦", command=lambda: self.focus(None))
        m.add_separator()
        m.add_command(label="复制节点 id", command=lambda: self._copy(nid))
        m.add_command(label="在网页版里打开（聚焦它）",
                      command=lambda: self.app.open_web_focus(nid))
        return m

    def _canvas_menu(self) -> tk.Menu:
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="新建顶层领域…", command=lambda: self.app.create_under(None, "domain"))
        m.add_separator()
        m.add_command(label="重新布局", command=self.relayout)
        m.add_command(label="适应窗口", command=self.fit)
        m.add_command(label="刷新数据", command=self.reload)
        return m

    def _on_right(self, event) -> None:
        nid = self._node_at(event)
        menu = self._node_menu(nid) if nid else self._canvas_menu()
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass


def main() -> None:
    if os.name == "nt":                                    # 高 DPI 下别糊
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:                                  # noqa: BLE001
            pass
    NOTES.mkdir(exist_ok=True)
    tab = "笔记"
    if "--tab" in sys.argv:
        i = sys.argv.index("--tab")
        if i + 1 < len(sys.argv) and sys.argv[i + 1].lower().startswith("g"):
            tab = "图谱"
    App(start_tab=tab).mainloop()


if __name__ == "__main__":
    main()
