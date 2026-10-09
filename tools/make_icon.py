#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成知识库控制台的图标：tools/kb.ico

图案 = 深色圆角底 + 一个四节点的知识图谱（和网页/GUI 里用的配色一致）。
先画 1024×1024 再缩小，边缘才干净；同时写出 16/24/32/48/64/128/256 多档尺寸。

运行：python tools/make_icon.py
依赖：Pillow（conda 自带 python 若没有，用 python -m pip install pillow）
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "tools" / "kb.ico"

S = 1024                     # 画布边长（最后缩到 256）
BG = (18, 20, 26, 255)       # 和网页背景一致的深色
BORDER = (42, 47, 59, 255)
EDGE = (140, 152, 175, 255)
BLUE = (106, 166, 255)
ORANGE = (240, 163, 94)
GREEN = (94, 196, 138)
PURPLE = (196, 138, 224)

# 相对坐标：上、左、右、下 四个节点，连成一个"图"
NODES = [(0.50, 0.22, BLUE), (0.22, 0.60, ORANGE),
         (0.78, 0.60, GREEN), (0.50, 0.86, PURPLE)]
LINKS = [(0, 1), (0, 2), (1, 3), (2, 3), (1, 2)]


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22),
                        fill=BG, outline=BORDER, width=int(S * 0.018))

    def xy(i: int) -> tuple[float, float]:
        return NODES[i][0] * S, NODES[i][1] * S

    for a, b in LINKS:                                # 先画连线，节点压在上面
        d.line([xy(a), xy(b)], fill=EDGE, width=int(S * 0.035), joint="curve")
    for i, (_x, _y, color) in enumerate(NODES):       # 再画节点
        x, y = xy(i)
        r = S * (0.105 if i == 0 else 0.085)
        d.ellipse([x - r, y - r, x + r, y + r], fill=color + (255,),
                  outline=BG, width=int(S * 0.014))
    return img


def main() -> int:
    icon = draw().resize((256, 256), Image.LANCZOS)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    icon.save(DEST, format="ICO",
              sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)])
    print(f"已生成 {DEST.relative_to(ROOT)}  ({DEST.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
