"""terrain_texture.py —— 月面质感体检：对比度、色阶数、高频能量"""
import glob
import sys

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
CASES = [("2006-04-05", "52% 月夜"), ("2005-01-01", "25% 短影"),
         ("2021-06-30", "41% 中影"), ("2021-06-25", "2% 正午")]

print("%-12s %-10s %-8s %-8s %-8s %-8s %-8s"
      % ("日期", "档位", "中位", "标准差", "p5~p95", "色阶数", "高频"))
for d, tag in CASES:
    f = None
    for cand in (r"E:\DeskTop\地球\成品\%s_月面_提升_1920x1280.png" % d,
                 r"E:\DeskTop\地球\成品\%s_月面_1920x1280.png" % d):
        import os
        if os.path.exists(cand):
            f = cand
            break
    if not f:
        print("%-12s 缺文件" % d)
        continue
    A = np.asarray(Image.open(f).convert("L")).astype(np.float32)
    ter = A[900:, :].copy()          # 地平线以下
    ter = ter[ter > 1]
    if ter.size < 1000:
        print("%-12s 地形太少" % d)
        continue
    med = float(np.median(ter))
    std = float(ter.std())
    p5, p95 = np.percentile(ter, [5, 95])
    levels = len(np.unique(ter.astype(np.uint8)))
    # 高频能量：与原图减 3px 模糊
    from PIL import ImageFilter
    bl = np.asarray(Image.fromarray(A[900:].astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(3))).astype(np.float32)
    hf = float(np.abs(A[900:] - bl)[A[900:] > 1].mean())
    print("%-12s %-10s %-8.0f %-8.1f %3.0f~%3.0f  %-8d %-8.2f"
          % (d, tag, med, std, p5, p95, levels, hf))
