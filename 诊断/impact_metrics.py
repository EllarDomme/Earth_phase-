"""impact_metrics.py —— 量化一张成品海报的"视觉权重"，用于评估震撼感"""
import math
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
from layout import disc_geom  # noqa: E402

P = r"E:\DeskTop\地球\成品\2008-10-26_月面_提升_1920x1280.png"
A = np.asarray(Image.open(P).convert("L")).astype(np.float32)
H, W = A.shape
cx, cy, R = disc_geom(W, H)
yy, xx = np.mgrid[0:H, 0:W]
disc = np.hypot(xx - cx, yy - cy) <= R
sky = (~disc) & (yy < 761)
terr = yy >= 761

print("=== 画面占比 ===")
print("  天空 %.1f%%   月面 %.1f%%   地球 %.1f%%"
      % (100 * sky.mean(), 100 * terr.mean(), 100 * disc.mean()))

print("\n=== 亮度层次（0-255）===")
print("  天空 均值 %.2f" % A[sky].mean())
print("  月面 均值 %.1f   中位 %.1f   最亮 %.0f"
      % (A[terr].mean(), np.median(A[terr]), A[terr].max()))
print("  地球 均值 %.1f   最亮 %.0f" % (A[disc].mean(), A[disc].max()))

print("\n=== 对比度 ===")
print("  地球/月面 %.1f 倍" % (A[disc].mean() / max(A[terr].mean(), 0.1)))
print("  地球/天空 %.0f 倍" % (A[disc].mean() / max(A[sky].mean(), 0.01)))
print("  月面/天空 %.1f 倍" % (A[terr].mean() / max(A[sky].mean(), 0.01)))

print("\n=== 大气弧峰值 ===")
best = 0.0
at = 0
for deg in range(0, 360, 3):
    a = math.radians(deg)
    for rr in np.arange(0.95, 1.08, 0.01):
        x, y = int(cx + rr * R * math.cos(a)), int(cy + rr * R * math.sin(a))
        if 0 <= x < W and 0 <= y < H:
            if A[y, x] > best:
                best, at = A[y, x], deg
print("  最亮 %.0f（出现在方位 %d°）" % (best, at))

print("\n=== 月面地形层次 ===")
t = A[terr]
print("  p5 %.0f  中位 %.0f  p95 %.0f   动态范围 %d 级"
      % (np.percentile(t, 5), np.median(t), np.percentile(t, 95),
         int(np.percentile(t, 95) - np.percentile(t, 5))))
