"""regen_night_contrast.py —— 对已有的月夜成品套用 ×1.6 地形对比（零额度）

等价性说明：合成阶段不缩放底图（1920→1920），"围绕中位拉伸"是仿射变换，
所以对成品地形做同样变换 == 合成时做。天空(0)不在掩膜内，盘内不动。
"""
import numpy as np
from PIL import Image

K = 1.6
FILES = [r"E:\DeskTop\地球\成品\2006-04-05_月面_1920x1280.png",
         r"E:\DeskTop\地球\成品\2006-04-05_月面_提升_1920x1280.png"]

for f in FILES:
    A = np.asarray(Image.open(f).convert("RGB")).astype(np.float32)
    lum = A.mean(2)
    # 地形：非天空（天空已被刷成 ~0）且不在圆盘内
    H, W = lum.shape
    cx, cy, R = 960, 397, 346
    yy, xx = np.mgrid[0:H, 0:W]
    disc = np.hypot(xx - cx, yy - cy) < R * 1.02
    terr = (lum > 1) & (~disc)
    med = float(np.median(lum[terr]))
    before = (float(np.median(lum[terr])), float(lum[terr].std()),
              len(np.unique(lum[terr].astype(np.uint8))))
    A[terr] = np.clip(med + (A[terr] - med) * K, 0, 255)
    Image.fromarray(np.clip(A, 0, 255).astype(np.uint8)).save(f)
    lum2 = A.mean(2)[terr]
    after = (float(np.median(lum2)), float(lum2.std()),
             len(np.unique(lum2.astype(np.uint8))))
    print("%-22s 中位 %.0f→%.0f  标准差 %.1f→%.1f  色阶 %d→%d"
          % (f.split("\\")[-1][:20], before[0], after[0], before[1], after[1],
             before[2], after[2]))

# 复查：天空与盘内没被改动
for f in FILES:
    A = np.asarray(Image.open(f).convert("L")).astype(np.float32)
    sky = A[:600, :400]
    print("  %-20s 左上天空 均值 %.2f 最大 %.0f"
          % (f.split("\\")[-1][:18], sky.mean(), sky.max()))
