#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把 frontmatter 的 id 与「旧路径引用」对齐到真实文件路径。

典型场景：你在资源管理器或 Obsidian 里把文件夹/文件改了名（例如 computer-science → computer_science）。
Obsidian 只会更新双链，frontmatter 里的 id / parents / relations 仍指向旧路径，
于是构建时出现「frontmatter 的 id 与文件路径不一致」的警告，或者父节点悄悄挂错。

本脚本做两件事：
  1. 每个文件的 id 按它的真实路径重建；
  2. 把所有指向旧路径的引用（frontmatter 里的 parents / relations，以及正文里的 [[双链]]）改写成新路径。
     「旧路径」的判定：原样解析不出来，但把每段的连字符换成下划线后能解析出来。

用法：
    python tools/fix_ids.py             # 只报告要改什么，不写文件（默认）
    python tools/fix_ids.py --apply     # 真正写入
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "notes"

FM_RE = re.compile(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.S)
LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]*))?\]\]")
ID_LINE_RE = re.compile(r"(?m)^(id[ \t]*:[ \t]*)(.*)$")


def real_ids() -> dict[str, Path]:
    ids: dict[str, Path] = {}
    for p in sorted(NOTES.rglob("*.md")):
        rel = p.relative_to(NOTES)
        if any(part.startswith(".") for part in rel.parts):   # 跳过 .obsidian / .trash
            continue
        ids[rel.with_suffix("").as_posix()] = p
    return ids


def to_underscore(ref: str) -> str:
    """把路径里每一段的连字符换成下划线。"""
    return "/".join(seg.replace("-", "_") for seg in ref.strip().strip("/").split("/"))


def make_resolver(ids: dict[str, Path]):
    lower = {k.lower(): k for k in ids}
    tail: dict[str, str] = {}
    for k in ids:
        tail.setdefault(k.rsplit("/", 1)[-1].lower(), k)

    def resolve(ref: str) -> str | None:
        r = ref.strip().strip("/")
        if r in ids:
            return r
        if r.lower() in lower:
            return lower[r.lower()]
        t = r.rsplit("/", 1)[-1].lower()
        return tail.get(t)

    return resolve


def main() -> int:
    ap = argparse.ArgumentParser(description="对齐 frontmatter 的 id 与旧路径引用")
    ap.add_argument("--apply", action="store_true", help="真正写入（默认只报告）")
    args = ap.parse_args()

    if not NOTES.exists():
        sys.exit(f"找不到 {NOTES}")
    ids = real_ids()
    resolve = make_resolver(ids)
    changes_total = 0
    files_changed = 0

    for real_id, path in ids.items():
        text = path.read_text(encoding="utf-8")
        original = text
        m = FM_RE.match(text)
        fm = m.group(1) if m else ""
        notes: list[str] = []

        # ① 收集这个文件里出现的「解析不出来、但换成下划线能解析」的引用
        alias: dict[str, str] = {}

        def consider(ref: str) -> None:
            ref = ref.strip().strip("\"'").strip()
            if not ref or ref in ids:
                return                          # 空引用 / 精确命中 → 不动
            cand = to_underscore(ref)
            if cand != ref and cand in ids:
                alias[ref] = cand               # 只有"换成下划线后精确命中"才迁移
            # 其它情况（含靠末段兜底能解析的）一律不动，避免误改

        # frontmatter 里所有像路径的 token（同时覆盖 parents: [a, b] 与块状 - a 两种写法）
        for tok in re.findall(r"[\w\u4e00-\u9fff][\w\u4e00-\u9fff./-]*", fm):
            consider(tok)
        for target, _disp in LINK_RE.findall(fm):    # frontmatter 里的双链形式
            consider(target)

        # ② id 与路径不一致 → 重建
        if m:
            cur = ID_LINE_RE.search(fm)
            if cur and cur.group(2).strip().strip("\"'") != real_id:
                notes.append(f"id: {cur.group(2).strip()}  →  {real_id}")
                text = text[:m.start(1)] + ID_LINE_RE.sub(
                    lambda mm: mm.group(1) + real_id, fm, count=1) + text[m.end(1):]

        # ③ 旧引用 → 新路径（frontmatter 里整段替换；正文只在 [[...]] 内替换）
        if alias:
            m2 = FM_RE.match(text)
            if m2:
                new_fm = m2.group(1)
                for old, new in sorted(alias.items(), key=lambda kv: -len(kv[0])):
                    pat = re.compile(r"(?<![\w/\-])" + re.escape(old) + r"(?![\w/\-])")
                    if pat.search(new_fm):
                        new_fm = pat.sub(new, new_fm)
                        notes.append(f"frontmatter 引用: {old}  →  {new}")
                text = text[:m2.start(1)] + new_fm + text[m2.end(1):]

            def fix_link(mm: re.Match) -> str:
                tgt, disp = mm.group(1).strip(), mm.group(2)
                new = alias.get(tgt) or alias.get(to_underscore(tgt))
                if new:
                    notes.append(f"正文双链: [[{tgt}]]  →  [[{new}]]")
                    return f"[[{new}|{disp}]]" if disp is not None else f"[[{new}]]"
                return mm.group(0)

            # 只处理 frontmatter 之后的正文部分，避免重复记录
            head = text[:FM_RE.match(text).end()] if FM_RE.match(text) else ""
            body = text[len(head):]
            text = head + LINK_RE.sub(fix_link, body)

        if text != original:
            files_changed += 1
            changes_total += len(notes)
            print(f"\n{real_id}")
            for n in notes:
                print(f"    {n}")
            if args.apply:
                path.write_text(text, encoding="utf-8")

    print()
    if not files_changed:
        print("没有需要改的地方：所有 id 与旧路径引用都已对齐。")
        return 0
    print(f"共 {files_changed} 个文件、{changes_total} 处改动。"
          + ("已写入。" if args.apply else "（这是预演；加 --apply 才会真正写入）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
