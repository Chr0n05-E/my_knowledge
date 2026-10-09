#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E:\\Knowledge 构建脚本 —— 把一堆 Markdown 笔记变成可浏览的知识图谱。

它做四件事：
  1. 扫描 notes/ 下所有 .md，读取 YAML frontmatter；
  2. 校验：id 与路径是否一致、父节点是否存在、有没有环、叶子笔记有没有写"我的理解"；
  3. 生成 out/KNOWLEDGE-MAP.md —— 缩进大纲，可直接喂给 markmap / Obsidian Markmind / 任何大纲工具；
  4. 生成 out/graph.html —— 单文件交互式知识图谱（左侧可折叠树 + 右侧正文 + 力导向全局图），
     数据全部内嵌，双击即可打开，不需要服务器、不需要联网（数学公式美化需联网加载 KaTeX）。

用法：
    python tools/build.py              # 构建 + 打印报告
    python tools/build.py --strict     # 有警告就失败（适合放进 git hook）
    python tools/build.py --open       # 构建完顺便用默认浏览器打开
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import os
import re
import shutil
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

try:  # 让 Windows 控制台也按 UTF-8 输出，避免中文乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = ROOT / "notes"
OUT_DIR = ROOT / "out"
VIEWER_TEMPLATE = ROOT / "tools" / "viewer" / "index.html"
CONFIG_PATH = ROOT / "kb.config.yml"

# 配置文件缺失/损坏时的兜底（正常情况请在 kb.config.yml 里改）
DEFAULT_CONFIG: dict = {
    "relations": [
        {"id": "parent", "label": "从属", "out_label": "上级", "in_label": "下级",
         "color": "#8c98af", "style": "solid", "directed": True, "tree": True,
         "aliases": ["属于", "父", "上级", "part_of"]},
        {"id": "prerequisite", "label": "前置依赖", "out_label": "前置", "in_label": "被用于",
         "color": "#f0a35e", "style": "dashed", "directed": True,
         "aliases": ["前置", "依赖", "先修", "prerequisite", "requires"]},
        {"id": "extends", "label": "推广 / 特例", "out_label": "推广自", "in_label": "特例",
         "color": "#5ec48a", "style": "dashed", "directed": True,
         "aliases": ["推广", "特例", "泛化", "extends"]},
        {"id": "applies_to", "label": "应用于", "out_label": "应用于", "in_label": "被应用于",
         "color": "#6aa6ff", "style": "dashed", "directed": True,
         "aliases": ["应用", "应用于", "用于", "applies_to"]},
        {"id": "cites", "label": "引用", "out_label": "引用", "in_label": "被引用",
         "color": "#c48ae0", "style": "dotted", "directed": True,
         "aliases": ["引用", "参考", "出处", "cites"]},
        {"id": "contrast", "label": "对比 / 易混", "out_label": "对比", "in_label": "对比",
         "color": "#e0708a", "style": "dotted", "directed": False,
         "aliases": ["对比", "易混", "区别", "contrast"]},
        {"id": "related", "label": "相关", "out_label": "相关", "in_label": "相关",
         "color": "#8b93a5", "style": "dotted", "directed": False,
         "aliases": ["相关", "参见", "另见", "related"]},
    ],
    "required_sections": ["我的理解"],
    "output_html": "out/index.html",
    "tree_sort": "title",
}

REL_STYLE_DEFAULT = "dashed"
_UNKNOWN_REL_LABELS: dict[str, int] = {}   # 正文里出现但配置里没定义的标签 -> 次数


def load_config(path: Path = CONFIG_PATH) -> dict:
    """读取 kb.config.yml（缺了就用内置默认值，不报错）。"""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))   # 深拷贝
    if not path.exists():
        return cfg
    raw = path.read_text(encoding="utf-8")
    data = None
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(raw)
    except Exception:
        data = None
    if not isinstance(data, dict):
        data = mini_yaml(raw)
    if not isinstance(data, dict):
        print(f"{C_WARN}警告{C_RESET} {path.name} 解析失败，改用内置默认配置")
        return cfg

    rels = data.get("relations")
    if isinstance(rels, list) and rels:
        clean = []
        for r in rels:
            if not isinstance(r, dict) or not r.get("id"):
                continue
            rid = str(r["id"]).strip()
            clean.append({
                "id": rid,
                "label": str(r.get("label") or rid),
                "out_label": str(r.get("out_label") or r.get("label") or rid),
                "in_label": str(r.get("in_label") or r.get("label") or rid),
                "color": str(r.get("color") or "#8b93a5"),
                "style": str(r.get("style") or REL_STYLE_DEFAULT),
                "directed": bool(r.get("directed", True)),
                "arrow_dir": str(r.get("arrow_dir") or "target"),
                "tree": bool(r.get("tree", False)),
                "aliases": [str(a) for a in (r.get("aliases") or [])],
            })
        if clean:
            cfg["relations"] = clean
    for k in ("required_sections",):
        if isinstance(data.get(k), list):
            cfg[k] = [str(x) for x in data[k]]
    for k in ("output_html", "tree_sort"):
        if isinstance(data.get(k), str) and data[k].strip():
            cfg[k] = data[k].strip()
    return cfg


CFG = load_config()
RELATIONS: list = CFG["relations"]
REL_BY_ID: dict = {r["id"]: r for r in RELATIONS}
TREE_REL: str = next((r["id"] for r in RELATIONS if r.get("tree")), "parent")
DEFAULT_REL: str = "related" if "related" in REL_BY_ID else RELATIONS[-1]["id"]


def rel_lookup() -> dict:
    """把一个标签（中文/英文/id/别名）映射到关系 id。"""
    m: dict[str, str] = {}
    for r in RELATIONS:
        for key in (r["id"], r["label"], r.get("out_label", ""), r.get("in_label", ""), *r.get("aliases", [])):
            k = str(key).strip().lower()
            if k:
                m.setdefault(k, r["id"])
    return m


REL_LOOKUP = rel_lookup()

# 叶子笔记（type: concept）必须出现的章节。想放松就在 kb.config.yml 里改。
REQUIRED_SECTIONS: list = CFG["required_sections"]

ASSET_DIR = OUT_DIR / "assets"

FM_RE = re.compile(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.S)
LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]*))?\]\]")
LINK_RE_NO_IMG = re.compile(r"(?<!!)\[\[([^\]|]+?)(?:\|([^\]]*))?\]\]")   # 排除 ![[图片]]
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
IMG_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
IMG_WIKI_RE = re.compile(r"!\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]")
# 正文里形如「- 前置：[[某个概念]]」的行 —— 用来给双链标上关系类型。
# 标签只允许中文/字母/空格/下划线/短横线，且不超过 12 字，避免把普通句子误判成关系行。
BODY_REL_RE = re.compile(
    r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z _\-/]{0,11}?)\s*[:：]\s*(.+)$")
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".avif"}
_IMG_INDEX: dict[str, Path] | None = None


def image_index() -> dict[str, Path]:
    """vault 内所有图片按文件名建索引（Obsidian 的 ![[文件名]] 就是这么解析的）。"""
    global _IMG_INDEX
    if _IMG_INDEX is None:
        idx: dict[str, Path] = {}
        if NOTES_DIR.exists():
            for p in NOTES_DIR.rglob("*"):
                if p.is_file() and p.suffix.lower() in IMG_EXT:
                    idx.setdefault(p.name.lower(), p)
                    idx.setdefault(p.stem.lower(), p)
        _IMG_INDEX = idx
    return _IMG_INDEX

C_RESET, C_DIM, C_WARN, C_ERR, C_OK, C_HEAD = "\033[0m", "\033[2m", "\033[33m", "\033[31m", "\033[32m", "\033[1m"
if os.name == "nt" and not os.environ.get("WT_SESSION"):
    # 老式 conhost 下关掉颜色，避免输出乱码
    C_RESET = C_DIM = C_WARN = C_ERR = C_OK = C_HEAD = ""


# --------------------------------------------------------------------------
# frontmatter
# --------------------------------------------------------------------------
def mini_yaml(raw: str) -> dict:
    """pyyaml 不可用时的后备解析器，只支持本库用到的 YAML 子集。"""
    out: dict = {}
    key = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^\s+-\s+(.*)$", line)
        if m and key:
            if not isinstance(out.get(key), list):
                out[key] = []
            out[key].append(_scalar(m.group(1)))
            continue
        m = re.match(r"^([^:\s][^:]*?)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1).strip(), m.group(2).strip()
        if val == "":
            out[key] = None
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            out[key] = [_scalar(x) for x in inner.split(",")] if inner else []
        else:
            out[key] = _scalar(val)
    return out


def _scalar(s: str):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    if s in ("null", "~", "None"):
        return None
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    return s


def split_frontmatter(text: str):
    m = FM_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), text[m.end():]
    data = None
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(raw)
    except Exception:
        data = None
    if not isinstance(data, dict):
        data = mini_yaml(raw)
    return data, body


def as_list(v) -> list:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [str(v).strip()]


# --------------------------------------------------------------------------
# Markdown -> HTML（够用的子集，不追求完整 CommonMark）
# --------------------------------------------------------------------------
def md_to_html(md: str, resolve) -> str:
    md = md.replace("\r\n", "\n")
    fences: list[str] = []

    def stash(code_html: str) -> str:
        fences.append(code_html)
        return f"\x00{len(fences) - 1}\x00"

    def fence_sub(m):
        lang = (m.group(1) or "").strip()
        code = htmllib.escape(m.group(2))
        cls = f' class="language-{lang}"' if lang else ""
        return stash(f"<pre><code{cls}>{code}</code></pre>")

    md = re.sub(r"```([^\n`]*)\n(.*?)```", fence_sub, md, flags=re.S)

    out: list[str] = []
    stack: list[tuple[int, str]] = []  # (indent, tag)
    para: list[str] = []

    def flush_para():
        if para:
            out.append("<p>" + inline(" ".join(para), resolve) + "</p>")
            para.clear()

    def close_lists(to_indent: int):
        while stack and stack[-1][0] > to_indent:
            _, tag = stack.pop()
            out.append(f"</li></{tag}>")

    for raw_line in md.split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            flush_para()
            continue
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if m:
            flush_para()
            indent = len(m.group(1).replace("\t", "    "))
            ordered = m.group(2)[0].isdigit()
            tag = "ol" if ordered else "ul"
            item = inline(m.group(3), resolve)
            if not stack or indent > stack[-1][0]:
                out.append(f"<{tag}>")
                stack.append((indent, tag))
                out.append(f"<li>{item}")
            else:
                close_lists(indent)
                if not stack or indent > stack[-1][0]:
                    out.append(f"<{tag}>")
                    stack.append((indent, tag))
                    out.append(f"<li>{item}")
                else:
                    out.append(f"</li><li>{item}")
            continue
        close_lists(-1)
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2), resolve)}</h{lvl}>")
            continue
        if re.match(r"^\s*(---+|\*\*\*+|___+)\s*$", line):
            flush_para()
            out.append("<hr>")
            continue
        if line.lstrip().startswith(">"):
            flush_para()
            out.append("<blockquote><p>" + inline(line.lstrip()[1:].strip(), resolve) + "</p></blockquote>")
            continue
        if re.match(r"^\s*\|.*\|\s*$", line):
            # 表格不做完整解析，按原样等宽显示，提醒使用者别在这里堆表格
            flush_para()
            out.append("<pre class=\"md-table\">" + htmllib.escape(line) + "</pre>")
            continue
        para.append(line.strip())

    flush_para()
    close_lists(-1)
    text = "\n".join(out)
    for i, code in enumerate(fences):
        text = text.replace(f"\x00{i}\x00", code)
    return text


def inline(text: str, resolve) -> str:
    codes: list[str] = []

    def keep(m):
        codes.append(m.group(1))
        return f"\x01{len(codes) - 1}\x01"

    text = re.sub(r"`([^`]+)`", keep, text)
    text = htmllib.escape(text, quote=False)

    # 图片必须排在普通链接前面，否则会被 [text](url) 规则先吃掉
    text = IMG_MD_RE.sub(
        lambda m: f'<img src="{htmllib.escape(m.group(2), quote=True)}" '
                  f'alt="{htmllib.escape(m.group(1), quote=True)}" loading="lazy">', text)

    def wikilink(m):
        target = m.group(1).strip()
        disp = (m.group(2) or target).strip() or target
        tid = resolve(target)
        if tid:
            return f'<a class="wl" href="#" data-target="{htmllib.escape(tid, quote=True)}">{htmllib.escape(disp)}</a>'
        return f'<span class="wl-missing" title="没有找到这个节点">{htmllib.escape(disp)}</span>'

    text = LINK_RE_NO_IMG.sub(wikilink, text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noreferrer">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)

    def restore(m):
        return "<code>" + htmllib.escape(codes[int(m.group(1))]) + "</code>"

    return re.sub("\x01(\\d+)\x01", restore, text)


def plain_text(md: str) -> str:
    t = re.sub(r"```.*?```", " ", md, flags=re.S)
    t = re.sub(r"\[\[([^\]|]+?)(?:\|([^\]]*))?\]\]", lambda m: (m.group(2) or m.group(1)), t)
    t = re.sub(r"[#>*`_\-\[\]()]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# --------------------------------------------------------------------------
# 加载
# --------------------------------------------------------------------------
def collect_assets(n: dict, warnings: list[str]) -> str:
    """把笔记里引用到的本地图片拷进 out/assets/，并把正文里的路径改写成 out 内的相对路径。

    支持两种写法：Markdown 的 ![](相对路径) 与 wiki 的 ![[文件名]]（Obsidian 常用）。
    查找顺序：笔记所在目录 -> 库根目录 -> notes/。
    """
    note_dir = (ROOT / n["file"]).parent

    def copy_img(ref: str) -> str:
        ref = ref.strip().strip("<>").strip()
        if re.match(r"^(https?:|data:)", ref, re.I):
            return ref
        cands = [note_dir / ref, ROOT / ref, NOTES_DIR / ref]
        by_name = image_index().get(Path(ref).name.lower())
        if by_name:
            cands.append(by_name)
        for cand in cands:
            try:
                if not cand.is_file():
                    continue
                ASSET_DIR.mkdir(parents=True, exist_ok=True)
                dest = ASSET_DIR / cand.name
                k = 1
                while dest.exists() and dest.read_bytes() != cand.read_bytes():
                    dest = ASSET_DIR / f"{cand.stem}-{k}{cand.suffix}"
                    k += 1
                if not dest.exists():
                    shutil.copy2(cand, dest)
                return f"assets/{dest.name}"
            except OSError:
                continue
        warnings.append(f"{n['id']}: 图片「{ref}」找不到（笔记目录、库根目录、notes/ 都试过了）")
        return ref

    body = n["body_md"]
    body = IMG_WIKI_RE.sub(
        lambda m: f"![{Path(m.group(1)).stem}]({copy_img(m.group(1))})", body)
    body = IMG_MD_RE.sub(lambda m: f"![{m.group(1)}]({copy_img(m.group(2))})", body)
    return body


def load_nodes(warnings: list[str]) -> dict:
    nodes: dict[str, dict] = {}
    if not NOTES_DIR.exists():
        sys.exit(f"找不到笔记目录：{NOTES_DIR}")

    for path in sorted(NOTES_DIR.rglob("*.md")):
        rel = path.relative_to(NOTES_DIR).with_suffix("")
        nid = rel.as_posix()
        text = path.read_text(encoding="utf-8")
        fm, body = split_frontmatter(text)

        fm_id = str(fm.get("id") or "").strip().strip("/")
        if fm_id and fm_id != nid:
            warnings.append(f"frontmatter 的 id「{fm_id}」与文件路径「{nid}」不一致（以路径为准）")

        m = H1_RE.search(body)
        title = str(fm.get("title") or (m.group(1) if m else rel.name)).strip()
        if not title:
            title = rel.name

        body_clean = body
        if m and m.group(1).strip() == title:
            body_clean = body[:m.start()] + body[m.end():]

        # 解析用的文本要先把代码块与行内代码去掉：
        # 否则文档里"举例怎么写双链"的那行会被当成真的链接，凭空多出一条边
        body_scan = re.sub(r"```.*?```", " ", body_clean, flags=re.S)
        body_scan = re.sub(r"`[^`\n]*`", " ", body_scan)

        sections = [s.strip() for s in re.findall(r"^#{2,3}\s+(.+?)\s*$", body_scan, re.M)]
        ntype = str(fm.get("type") or ("domain" if "." not in rel.name else "concept")).strip()
        links_raw = [(t.strip(), (d or t).strip()) for t, d in LINK_RE_NO_IMG.findall(body_scan)]

        # ① frontmatter 里显式写的关系：
        #    relations:
        #      前置依赖: [math/algebra, 群论]
        fm_rels: list[tuple[str, str]] = []
        fm_rel_block = fm.get("relations")
        if isinstance(fm_rel_block, dict):
            for k, v in fm_rel_block.items():
                rid = REL_LOOKUP.get(str(k).strip().lower())
                if not rid:
                    _UNKNOWN_REL_LABELS[str(k)] = _UNKNOWN_REL_LABELS.get(str(k), 0) + 1
                    rid = DEFAULT_REL
                for t in as_list(v):
                    fm_rels.append((rid, t))
        elif isinstance(fm_rel_block, list):   # 只写目标、不写类型时一律算"相关"
            for t in as_list(fm_rel_block):
                fm_rels.append((DEFAULT_REL, t))

        # ② 正文里形如「- 前置：[[群论]]」「对比：[[偏锋]]」的行
        body_rels: list[tuple[str, str]] = []
        for line in body_scan.splitlines():
            m2 = BODY_REL_RE.match(line)
            if not m2:
                continue
            label = m2.group(1).strip()
            targets = [t.strip() for t, _d in LINK_RE_NO_IMG.findall(m2.group(2))]
            if not targets:
                continue
            rid = REL_LOOKUP.get(label.lower())
            if not rid:
                # 只在这一行"除了双链几乎没别的内容"时提醒，避免把正文里的普通句子误判成关系声明
                bare = re.sub(r"[\s，。、；：:;,.\-—（）()\[\]「」\"'`*]", "",
                              LINK_RE_NO_IMG.sub("", m2.group(2)))
                if len(bare) <= 8:
                    _UNKNOWN_REL_LABELS[label] = _UNKNOWN_REL_LABELS.get(label, 0) + 1
                continue
            for t in targets:
                body_rels.append((rid, t))

        nodes[nid] = {
            "id": nid,
            "title": title,
            "type": ntype,
            "status": str(fm.get("status") or "seed"),
            "tags": as_list(fm.get("tags")),
            "aliases": as_list(fm.get("aliases")),
            "created": str(fm.get("created") or ""),
            "updated": str(fm.get("updated") or ""),
            "fm_parents": as_list(fm.get("parents")),
            "fm_rels": fm_rels,
            "body_rels": body_rels,
            "path_parent": nid.rsplit("/", 1)[0] if "/" in nid else None,
            "sections": sections,
            "body_md": body_clean.lstrip("\n"),
            "links_raw": links_raw,
            "file": str(path.relative_to(ROOT)),
        }

    # 索引：id / 标题 / 别名 -> id
    index: dict[str, str] = {}
    for nid, n in nodes.items():
        index.setdefault(nid.lower(), nid)
        index.setdefault(n["title"].lower(), nid)
        index.setdefault(nid.rsplit("/", 1)[-1].lower(), nid)
        for a in n["aliases"]:
            index.setdefault(a.lower(), nid)

    for nid, n in nodes.items():
        if nid.lower() in index and index[nid.lower()] != nid:
            warnings.append(f"id 冲突：「{nid}」与「{index[nid.lower()]}」")
    return nodes, index


def make_resolver(nodes: dict, index: dict):
    def resolve(target: str) -> str | None:
        t = target.strip().strip("/")
        for key in (t.lower(), t.replace("\\", "/").lower()):
            if key in index:
                return index[key]
        # 允许只写末段（例如 [[中锋]] 之外的 [[zhongfeng]]）
        tail = t.rsplit("/", 1)[-1].lower()
        return index.get(tail)
    return resolve


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------
def validate(nodes: dict, index: dict, resolve, warnings: list[str], errors: list[str]):
    for nid, n in nodes.items():
        # 父节点
        parents = [resolve(p) for p in n["fm_parents"]]
        n["missing_parents"] = [p for p, r in zip(n["fm_parents"], parents) if not r]
        parents = [p for p in parents if p]
        pp = n["path_parent"]
        if pp and pp not in nodes:
            warnings.append(f"{nid}: 目录里的上级「{pp}」没有对应笔记（建议创建 notes/{pp}.md）")
            parents.append(pp)
        if pp and pp not in parents:
            parents.insert(0, pp)
        n["parents"] = parents
        n["primary_parent"] = pp if pp else (parents[0] if parents else None)

        # 叶子笔记的必需章节
        if n["type"] == "concept":
            missing = [s for s in REQUIRED_SECTIONS if not any(s in x for x in n["sections"])]
            if missing:
                warnings.append(f"{nid}: 缺少章节 {missing}（叶子节点本该是你自己的理解）")
        if n["type"] == "concept" and not n["parents"]:
            warnings.append(f"{nid}: 没有任何父节点，会浮在图谱外面")
        if not n["body_md"].strip():
            warnings.append(f"{nid}: 正文是空的")

        # 出链 + 类型化关系
        n["links"] = []
        for target, _disp in n["links_raw"]:
            r = resolve(target)
            if r and r != nid:
                n["links"].append(r)
            elif not r:
                warnings.append(f"{nid}: 链接 [[{target}]] 指向不存在的节点（先建空笔记也算）")
        n["links"] = sorted(set(n["links"]))

        n["rels"] = []           # [(关系id, 目标id)]
        for rid, raw in n["fm_rels"] + n["body_rels"]:
            r = resolve(raw)
            if r and r != nid:
                n["rels"].append((rid, r))
            elif not r:
                rel_name = REL_BY_ID.get(rid, {}).get("label", rid)
                warnings.append(f"{nid}: 关系「{rel_name}」指向不存在的节点「{raw}」")
        # 没被标注过的双链，统一算作「相关」
        for r in n["links"]:
            if any(r == t for _rid, t in n["rels"]):
                continue
            n["rels"].append((DEFAULT_REL, r))
        # 去重（同一个 关系+目标 只留一条），并保持配置里的顺序
        order = {r["id"]: i for i, r in enumerate(RELATIONS)}
        n["rels"] = sorted(set(n["rels"]), key=lambda x: (order.get(x[0], 99), x[1]))

    # 环检测
    state: dict[str, int] = {}

    def dfs(nid: str, chain: list[str]):
        state[nid] = 1
        for p in nodes[nid]["parents"]:
            if p not in nodes:
                continue
            if state.get(p) == 1:
                errors.append("父子关系成环：" + " -> ".join(chain + [nid, p]))
                continue
            if state.get(p) is None:
                dfs(p, chain + [nid])
        state[nid] = 2

    for nid in nodes:
        if state.get(nid) is None:
            dfs(nid, [])

    # 标题撞车
    seen: dict[str, str] = {}
    for nid, n in nodes.items():
        k = n["title"].lower()
        if k in seen:
            warnings.append(f"标题重复：「{n['title']}」出现在 {seen[k]} 与 {nid}（双链会优先指向先加载的）")
        else:
            seen[k] = nid


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------
def build_tree(nodes: dict) -> list:
    children: dict[str, list[str]] = {}
    for nid, n in nodes.items():
        p = n["primary_parent"]
        if p:
            children.setdefault(p, []).append(nid)
    sort_key = CFG.get("tree_sort", "title")
    if sort_key == "created":
        key = lambda x: (nodes[x]["created"], nodes[x]["title"])
    elif sort_key == "updated":
        key = lambda x: (nodes[x]["updated"], nodes[x]["title"])
    elif sort_key == "id":
        key = lambda x: x
    else:
        key = lambda x: nodes[x]["title"]
    for lst in children.values():
        lst.sort(key=key)
    return children


def render_outline(nodes: dict, children: dict) -> str:
    lines = ["# 知识库", ""]
    roots = sorted([nid for nid, n in nodes.items() if not n["primary_parent"]],
                   key=lambda x: nodes[x]["title"])

    def walk(nid: str, depth: int):
        n = nodes[nid]
        pad = "  " * depth
        label = n["title"]
        extra = [p for p in n["parents"] if p != n["primary_parent"] and p in nodes]
        if extra:
            label += "（也属于 " + "、".join(nodes[p]["title"] for p in extra) + "）"
        if n["type"] == "concept":
            label = f"{label}  `{n['id']}`"
        lines.append(f"{pad}- {label}")
        for c in children.get(nid, []):
            walk(c, depth + 1)

    for r in roots:
        walk(r, 0)
    lines.append("")
    lines.append(f"<!-- 由 tools/build.py 生成于 {datetime.now():%Y-%m-%d %H:%M}；"
                 f"共 {len(nodes)} 个节点。可直接拖进 https://markmap.js.org/repl 或 Obsidian Markmind。 -->")
    return "\n".join(lines) + "\n"


def build_payload(nodes: dict, children: dict, resolve, warnings: list[str]) -> dict:
    top_level = {nid for nid, n in nodes.items() if not n["primary_parent"]}

    def top_of(nid: str) -> str:
        seen = set()
        cur = nid
        while True:
            if cur in top_level or cur in seen:
                return cur
            p = nodes[cur]["primary_parent"]
            if not p or p not in nodes:
                return cur
            seen.add(cur)
            cur = p

    out_nodes = []
    for nid, n in nodes.items():
        body_md = collect_assets(n, warnings)
        body_html = md_to_html(body_md, resolve)
        out_nodes.append({
            "id": nid,
            "title": n["title"],
            "type": n["type"],
            "status": n["status"],
            "tags": n["tags"],
            "aliases": n["aliases"],
            "created": n["created"],
            "updated": n["updated"],
            "parents": n["parents"],
            "primaryParent": n["primary_parent"],
            "top": top_of(nid),
            "children": children.get(nid, []),
            "links": n["links"],
            "rels": [{"rel": rid, "target": t} for rid, t in n["rels"]],
            "sections": n["sections"],
            "html": body_html,
            "excerpt": plain_text(n["body_md"])[:180],
            "file": n["file"],
        })

    edges = []
    seen_edges: set[tuple[str, str, str]] = set()
    tree_pairs: set[frozenset] = set()

    def add_edge(src: str, dst: str, rid: str, **extra):
        key = (src, dst, rid)
        if key in seen_edges or src == dst:
            return
        seen_edges.add(key)
        edges.append({"source": src, "target": dst, "rel": rid, **extra})

    for n in out_nodes:
        for p in n["parents"]:
            if p in nodes:
                # 从属关系：source=父节点，target=子节点（箭头顺着层级往下：科学 → 计算机科学）
                add_edge(p, n["id"], TREE_REL, tree=(p == n["primaryParent"]))
                tree_pairs.add(frozenset((n["id"], p)))
    for n in out_nodes:
        for r in n["rels"]:
            # 领域笔记里的「地图」列表会把子节点再列一遍，和从属边重复，这里去掉
            if r["rel"] == DEFAULT_REL and frozenset((n["id"], r["target"])) in tree_pairs:
                continue
            add_edge(n["id"], r["target"], r["rel"])

    tops = sorted(top_level, key=lambda x: nodes[x]["title"])
    rel_counts = {r["id"]: 0 for r in RELATIONS}
    for e in edges:
        rel_counts[e["rel"]] = rel_counts.get(e["rel"], 0) + 1
    return {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "roots": [r for r in tops],
        "nodes": out_nodes,
        "edges": edges,
        "relations": RELATIONS,
        "treeRel": TREE_REL,
        "stats": {
            "total": len(out_nodes),
            "concepts": sum(1 for n in out_nodes if n["type"] == "concept"),
            "domains": sum(1 for n in out_nodes if n["type"] == "domain"),
            "links": sum(1 for e in edges if e["rel"] != TREE_REL),
            "edges": len(edges),
            "byRel": rel_counts,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="构建知识库图谱")
    ap.add_argument("--strict", action="store_true", help="把警告当作错误")
    ap.add_argument("--open", action="store_true", help="构建后用浏览器打开图谱")
    args = ap.parse_args()

    warnings: list[str] = []
    errors: list[str] = []

    nodes, index = load_nodes(warnings)
    if not nodes:
        sys.exit("notes/ 里还没有任何笔记。")
    resolve = make_resolver(nodes, index)
    validate(nodes, index, resolve, warnings, errors)
    children = build_tree(nodes)

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "KNOWLEDGE-MAP.md").write_text(render_outline(nodes, children), encoding="utf-8")

    payload = build_payload(nodes, children, resolve, warnings)
    (OUT_DIR / "graph.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if not VIEWER_TEMPLATE.exists():
        errors.append(f"缺少查看器模板：{VIEWER_TEMPLATE}")
    else:
        tpl = VIEWER_TEMPLATE.read_text(encoding="utf-8")
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        html = (tpl.replace("__KB_DATA__", data)
                   .replace("__KB_BUILT__", payload["generatedAt"])
                   .replace("__KB_STATS__", json.dumps(payload["stats"], ensure_ascii=False)))
        html_path = (ROOT / CFG["output_html"]).resolve()
        if ROOT not in html_path.parents:
            errors.append(f"配置里的 output_html 必须在知识库目录内：{CFG['output_html']}")
            html_path = OUT_DIR / "index.html"
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")

        # 老版本产物叫 graph.html，留着会让人搞不清该打开哪个；确认路径无误后清掉
        stale = (OUT_DIR / "graph.html").resolve()
        if stale != html_path and stale.is_file() and stale.parent == OUT_DIR.resolve():
            stale.unlink()

    # ---- 报告 ----
    print(f"{C_HEAD}知识库构建报告{C_RESET}  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"  节点 {len(nodes)} 个（领域 {payload['stats']['domains']} / 概念 {payload['stats']['concepts']}）"
          f"，关系边 {payload['stats']['edges']} 条")
    by_rel = payload["stats"]["byRel"]
    rel_bits = "、".join(f"{REL_BY_ID[rid]['label']} {cnt}"
                        for rid, cnt in by_rel.items() if cnt and rid in REL_BY_ID)
    if rel_bits:
        print(f"  关系分布：{rel_bits}")
    print(f"  输出：{(OUT_DIR / 'KNOWLEDGE-MAP.md').relative_to(ROOT)}")
    print(f"        {(OUT_DIR / 'graph.json').relative_to(ROOT)}")
    if not errors:
        print(f"        {html_path.relative_to(ROOT)}   ← 用浏览器打开这个")
    for label, cnt in sorted(_UNKNOWN_REL_LABELS.items(), key=lambda x: -x[1]):
        print(f"  {C_DIM}提示{C_RESET} 正文里的关系标签「{label}」没在 kb.config.yml 里定义"
              f"（{cnt} 次，已按「{REL_BY_ID[DEFAULT_REL]['label']}」处理）")
    for w in warnings:
        print(f"  {C_WARN}警告{C_RESET} {w}")
    for e in errors:
        print(f"  {C_ERR}错误{C_RESET} {e}")
    if not warnings and not errors:
        print(f"  {C_OK}全部通过：没有警告，也没有错误。{C_RESET}")
    else:
        print(f"  {C_DIM}（警告 {len(warnings)}，错误 {len(errors)}）{C_RESET}")

    if args.open and not errors and html_path.exists():
        webbrowser.open(html_path.as_uri())
    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
