"""lighting_curve.py —— 用纯色圆盘测打光响应曲线，找非单调凹陷"""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
import lighting  # noqa: E402
from layout import disc_geom  # noqa: E402

DATE, UTC = "2006-04-05", 7.75
W, H = 1920, 1280
cx, cy, R = disc_geom(W, H)

# 造一张纯色圆盘海报（天空黑，盘内均匀 200）
A = np.zeros((H, W, 3), np.float32)
yy, xx = np.mgrid[0:H, 0:W]
inside = np.hypot(xx - cx, yy - cy) <= R
A[inside] = 200.0
img = Image.fromarray(A.astype(np.uint8))

out = np.asarray(lighting.apply_lighting(img, DATE, UTC, verbose=False).convert("L")).astype(np.float32)

# 沿水平中线扫过盘内
y = cy
print("沿 y=%.0f 横扫（纯色盘 → 亮度只反映光照）" % y)
row = out[int(y), int(cx - R):int(cx + R)]
n = len(row)
xs = np.linspace(-1, 1, n)
prev = None
dips = []
for i in range(2, n - 2):
    if row[i] < row[i - 1] - 1 and row[i] < row[i + 1] - 1 and row[i] < 60:
        dips.append((i, row[i]))
# 打印靠近中心的一段（晨昏线所在）
c = n // 2
print("  相对x    亮度")
for i in range(c - 40, c + 40, 2):
    mark = ""
    if 2 < i < n - 2 and row[i] < row[i - 1] - 0.8 and row[i] < row[i + 1] - 0.8:
        mark = "  ← 凹陷"
    print("  %+6.2f  %6.1f%s" % (xs[i], row[i], mark))
print()
print("检测到凹陷数量:", len(dips))
if dips:
    print("  位置（相对）:", [("%+.2f" % xs[i]) for i, _ in dips[:10]])
