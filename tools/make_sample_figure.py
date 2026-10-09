#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 notes/aesthetics/calligraphy/attachments/zhongfeng_vs_pianfeng.png——
一张用来说明「中锋 / 偏锋」墨色分布的示意图（顺便当图片管线的示例：build.py 会把它拷进 out/assets/）。

做法：不叠画线条（会叠成死黑），而是用 numpy 直接算每条笔画横截面的墨量分布。
中锋 = 以笔画中心为峰的高斯；偏锋 = 峰偏到一侧再加一点向另一侧拖尾。
运行：python tools/make_sample_figure.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "notes" / "aesthetics" / "calligraphy" / "attachments" / "zhongfeng_vs_pianfeng.png"

W, H = 960, 430
BG = np.array([250.0, 249.0, 246.0])


def font(size: int):
    for name in ("msyh.ttc", "simhei.ttf", "simsun.ttc", "NotoSansCJK-Regular.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def profile(y0: int, y1: int, kind: str) -> np.ndarray:
    """返回该笔画带内每一行的墨量 0..1。"""
    ys = np.arange(y0, y1, dtype=float)
    h = float(y1 - y0)
    if kind == "center":
        sigma = h / 4.4
        d = np.exp(-((ys - (y0 + h / 2)) ** 2) / (2 * sigma ** 2))
    else:  # 偏锋：主峰贴近下缘 + 向上的一层薄拖尾
        d = np.exp(-((ys - (y0 + h * 0.84)) ** 2) / (2 * (h / 6.0) ** 2))
        d += 0.22 * np.exp(-((ys - (y0 + h * 0.5)) ** 2) / (2 * (h / 2.4) ** 2))
    return np.clip(d, 0.0, 1.0)


def paint(arr: np.ndarray, x0: int, x1: int, y0: int, y1: int, kind: str, ink: float = 0.96):
    d = profile(y0, y1, kind)[:, None, None]
    band = arr[y0:y1, x0:x1, :]
    arr[y0:y1, x0:x1, :] = band * (1.0 - d * ink)      # 墨量越高峰值越靠近黑


arr = np.tile(BG, (H, W, 1))
# 纸纹：极轻的横向明暗，避免死板的纯色
noise = 1.0 + (np.random.default_rng(7).random((H, 1)) - 0.5) * 0.012
arr *= noise[:, :, None]
arr = np.clip(arr, 0, 255)

X0, X1 = 60, 900
paint(arr, X0, X1, 96, 168, "center")     # 中锋
paint(arr, X0, X1, 288, 360, "pianfeng")  # 偏锋

# 笔画上下轮廓辅助线
for y in (96, 168, 288, 360):
    arr[y - 1:y + 1, X0:X1, :] = np.array([186.0, 184.0, 180.0])

img = Image.fromarray(arr.astype(np.uint8), "RGB")
draw = ImageDraw.Draw(img)
ink = (30, 28, 26)
gray = (122, 120, 116)
f_title, f_small = font(29), font(18)

draw.text((48, 22), "中锋：墨从笔画中心向两侧对称洇开", font=f_title, fill=ink)
draw.text((60, 182), "两侧轮廓内墨色基本对称 · 中心留住更浓的「中线」", font=f_small, fill=gray)
draw.text((48, 212), "偏锋：重心偏在一侧，一侧死黑、一侧发虚", font=f_title, fill=ink)
draw.text((60, 374), "同样宽度下信息量更低：一侧堆积，一侧空", font=f_small, fill=gray)

DEST.parent.mkdir(parents=True, exist_ok=True)
img.save(DEST, quality=95)
print(f"已生成 {DEST.relative_to(ROOT)}  ({DEST.stat().st_size} bytes)")
