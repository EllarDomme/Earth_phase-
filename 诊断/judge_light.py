"""judge_light_20041108.py —— 客观评价这张的光照"""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
import lighting

P = r"E:\DeskTop\地球\成品\2004-11-08_月面_提升_1920x1280.png"
D, UTC = "2004-11-08", 1.25

A = np.asarray(Image.open(P).convert("RGB")).astype(np.float32)
L = A.mean(2)
H, W = L.shape
cosi, z, rr = lighting.cosi_map(D, UTC, W, H)
ins = rr < 0.97

print("=== ① 亮度随受光角的变化（应该单调下降）===")
prev = None
mono = True
for lo in np.arange(0.0, 0.8, 0.1):
    m = ins & (cosi >= lo) & (cosi < lo + 0.1)
    if m.sum() < 500:
        continue
    v = float(L[m].mean())
    if prev is not None and v > prev + 2:
        mono = False
    print("  cosi %.1f~%.1f  均亮 %5.1f" % (lo, lo + 0.1, v))
    prev = v
print("  单调性：", "✓ 越正对越亮" if mono else "✗ 有反常")

print()
print("=== ② 夜面 / 太空 ===")
night = float(L[ins & (cosi < -0.25)].mean()) if (ins & (cosi < -0.25)).sum() > 200 else float("nan")
sky = float(L[(rr > 1.35) & (np.arange(H)[:, None] < 700)].mean())
print("  夜面 %.1f   太空 %.1f" % (night, sky))

print()
print("=== ③ 晨昏线位置（亮度降到峰值一半的 cosi）===")
peak = float(L[ins].max())
m = ins & (L > peak * 0.5)
print("  亮面(>半峰) 覆盖 cosi 中位 %.2f  最小 %.2f" % (np.median(cosi[m]), cosi[m].min()))
lit_frac = float((ins & (cosi > 0)).sum()) / float(ins.sum())
print("  理论受光面积占比 %.1f%%（相位 76%%）" % (lit_frac * 100))

print()
print("=== ④ 大气弧 ===")
yy, xx = np.mgrid[0:H, 0:W]
az = np.degrees(np.arctan2(-(yy - 396.8), (xx - 960))) % 360
ring = (rr > 1.002) & (rr < 1.014)
for a0 in (330, 0, 30, 60, 240):
    d = np.abs(((az - a0 + 180) % 360) - 180)
    mm = ring & (d < 5)
    if mm.sum() > 15:
        print("  %3d°  cosi %+.2f  弧光亮度 %5.1f" % (a0, cosi[mm].mean(), L[mm].mean()))

print()
print("=== ⑤ 过曝 ===")
print("  盘内 >245 占比 %.2f%%" % ((A[rr < 1].max(1) > 245).mean() * 100))
