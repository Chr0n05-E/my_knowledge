#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成知识库控制台的图标：tools/kb.ico

图案 = 深色圆角底 + 一个四节点的知识图谱（和网页/GUI 里用的配色一致）。
先画 1024×1024 再缩小，边缘才干净。

**为什么要自己拼 ICO**：Pillow 存出来的每一帧都是 PNG 压缩格式，而 Windows 读取
快捷方式图标时用的 ExtractIconEx 只认小尺寸的 BMP/DIB 帧，遇到 PNG 帧会退回默认白纸图标。
所以这里手写 ICO：16–128 用 BMP/DIB 帧，256 那帧按惯例用 PNG。

运行：python tools/make_icon.py [--preview 输出.png]
依赖：Pillow
"""
from __future__ import annotations

import argparse
import struct
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

SIZES = [16, 24, 32, 48, 64, 128]     # 这些用 BMP/DIB 帧（快捷方式图标靠它们）
PNG_SIZE = 256                        # 这一帧按惯例用 PNG

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


def dib_frame(im: Image.Image) -> bytes:
    """把一张 RGBA 图变成 ICO 里的 BMP/DIB 帧（BITMAPINFOHEADER + BGRA 倒序 + AND 掩码）。"""
    im = im.convert("RGBA")
    w, h = im.size
    px = im.tobytes()                                   # 自上而下、每像素 4 字节
    rows = [px[y * w * 4:(y + 1) * w * 4] for y in range(h)]
    xor = b"".join(reversed(rows))                      # DIB 是自下而上存的
    and_row = ((w + 31) // 32) * 4                      # AND 掩码每行按 4 字节对齐
    and_mask = b"\x00" * (and_row * h)                  # 透明度交给 alpha 通道
    header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0,
                         len(xor) + len(and_mask), 0, 0, 0, 0)
    return header + xor + and_mask


def build_ico(images: list[tuple[int, bytes, bool]]) -> bytes:
    """images: [(尺寸, 数据, 是否是 PNG)]，按尺寸升序。"""
    count = len(images)
    offset = 6 + 16 * count
    entries, blobs = [], []
    for size, data, _is_png in images:
        entries.append(struct.pack("<BBBBHHII",
                                   size if size < 256 else 0,
                                   size if size < 256 else 0,
                                   0, 0, 1, 32, len(data), offset))
        blobs.append(data)
        offset += len(data)
    out = struct.pack("<HHH", 0, 1, count) + b"".join(entries) + b"".join(blobs)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 tools/kb.ico")
    ap.add_argument("--preview", help="同时导出一张 PNG 预览（用于查看效果）")
    args = ap.parse_args()

    base = draw()
    frames: list[tuple[int, bytes, bool]] = []
    for size in SIZES:
        small = base.resize((size, size), Image.LANCZOS)
        frames.append((size, dib_frame(small), False))
    big = base.resize((PNG_SIZE, PNG_SIZE), Image.LANCZOS)
    import io
    buf = io.BytesIO()
    big.save(buf, format="PNG")
    frames.append((PNG_SIZE, buf.getvalue(), True))

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_bytes(build_ico(frames))
    print(f"已生成 {DEST.relative_to(ROOT)}  ({DEST.stat().st_size} bytes, "
          f"{len(SIZES)} 个 BMP 帧 + 1 个 PNG 帧)")

    if args.preview:
        Path(args.preview).parent.mkdir(parents=True, exist_ok=True)
        big.save(args.preview, format="PNG")
        print(f"预览已导出 {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
