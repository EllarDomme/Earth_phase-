"""batch_nc40.py —— 其余月夜图按 4.0 更新（零额度，只动地形）

原理：地形与地球圆盘互不影响，且 compose 不做缩放，
所以"围绕地形中位把偏离量 ×(4.0/1.6)" == 用新默认值重拼。
这样能保住提升版的圆盘（boosted disc 已被清理，无法重拼）。
"""
import glob
import os

import numpy as np
from PIL import Image

OUT = r"E:\DeskTop\地球\成品"
K = 4.0 / 1.6          # 2.5
DATES = ["2002-10-01", "2004-11-08", "2006-04-05", "2008-10-29", "2009-06-21"]

print("%-12s %-10s %-16s %-16s" % ("日期", "张数", "改前范围", "改后范围"))
for d in DATES:
    files = sorted(glob.glob(os.path.join(OUT, "%s_月面_*1920x1280.png" % d)))
    if not files:
        print("%-12s 缺文件" % d)
        continue
    ranges = []
    for f in files:
        A = np.asarray(Image.open(f).convert("RGB")).astype(np.float32)
        lum = A.mean(2)
        yy = np.arange(A.shape[0])[:, None] * np.ones((1, A.shape[1]))
        terr = (yy >= 761) & (lum > 1)
        if not terr.any():
            continue
        t0 = lum[terr]
        p5a, p95a = np.percentile(t0, [5, 95])
        med = float(np.median(t0))
        A[terr] = np.clip(med + (A[terr] - med) * K, 0, 255)
        Image.fromarray(np.clip(A, 0, 255).astype(np.uint8)).save(f)
        lum2 = A.mean(2)[terr]
        p5b, p95b = np.percentile(lum2, [5, 95])
        ranges.append((p95a - p5a, p95b - p5b, med, np.median(lum2)))
    if ranges:
        a = np.mean([r[0] for r in ranges])
        b = np.mean([r[1] for r in ranges])
        m0 = np.mean([r[2] for r in ranges])
        m1 = np.mean([r[3] for r in ranges])
        print("%-12s %-10d %-16s %-16s  中位 %.0f→%.0f"
              % (d, len(files), "%.0f 级" % a, "%.0f 级" % b, m0, m1))
