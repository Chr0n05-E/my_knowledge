#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新建一条笔记（放在正确的目录位置，frontmatter 自动填好）。

用法：
    python tools/new.py math/algebra/group_theory --title 群论
    python tools/new.py aesthetics/calligraphy/feibai --title 飞白 --type concept
    python tools/new.py science/chemistry --title 化学 --type domain
    python tools/new.py math/algebra/linear_map --title 线性映射 --parent math/algebra --parent engineering/computer_science

约定：id 就是相对 notes/ 的路径（不含 .md），所以 id 天然就是层级结构。
     命名用下划线分词就行（如 data_structure）；大小写随你，中文 id 也可以。
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "notes"
TEMPLATES = ROOT / "templates"

try:  # Windows 控制台按 UTF-8 输出，避免中文乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def main() -> int:
    ap = argparse.ArgumentParser(description="新建知识库笔记")
    ap.add_argument("id", help="节点 id，例如 math/algebra/group_theory（小写英文 + 下划线）")
    ap.add_argument("--title", help="标题，默认取 id 最后一段")
    ap.add_argument("--type", default=None, choices=["concept", "domain"], help="节点类型")
    ap.add_argument("--parent", action="append", default=[], help="额外父节点 id（可重复）")
    ap.add_argument("--status", default="seed", choices=["seed", "growing", "evergreen"])
    ap.add_argument("--tags", default="", help="逗号分隔")
    ap.add_argument("--force", action="store_true", help="已存在就覆盖")
    args = ap.parse_args()

    nid = args.id.strip().strip("/").replace("\\", "/")
    if not re.fullmatch(r"[\w\-./\u4e00-\u9fff]+", nid) or nid.startswith("."):
        sys.exit(f"id 不合法：{nid}")
    title = args.title or nid.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")
    ntype = args.type or ("domain" if "/" not in nid else "concept")

    target = NOTES / f"{nid}.md"
    if target.exists() and not args.force:
        sys.exit(f"已经存在了：{target.relative_to(ROOT)}（要覆盖加 --force）")

    default_parent = nid.rsplit("/", 1)[0] if "/" in nid else ""
    parents = []
    for p in ([default_parent] if default_parent else []) + args.parent:
        p = p.strip().strip("/")
        if p and p not in parents:
            parents.append(p)

    tpl_name = "domain.md" if ntype == "domain" else "concept.md"
    tpl = (TEMPLATES / tpl_name).read_text(encoding="utf-8")
    today = date.today().isoformat()
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    body = tpl
    body = re.sub(r"^---\s*$.*?^---[ \t]*$", "", body, count=1, flags=re.S | re.M)  # 去掉模板 frontmatter
    fm = [
        "---",
        f"id: {nid}",
        f"title: {title}",
        f"type: {ntype}",
        "parents: [" + ", ".join(parents) + "]",
        "aliases: []",
        "tags: [" + ", ".join(tags) + "]",
        f"status: {args.status}",
        f"created: {today}",
        f"updated: {today}",
        "---",
        "",
    ]
    text = "\n".join(fm) + body.lstrip("\n")
    text = text.replace("# 概念名称", f"# {title}").replace("# 分支名称", f"# {title}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"已创建 {target.relative_to(ROOT)}")
    print(f"  层级：{'/'.join(parents + [title]) if parents else title}")
    print("  写完后跑一次 python tools/build.py 刷新图谱。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
