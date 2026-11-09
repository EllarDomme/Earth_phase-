"""test_pair_check.py —— 验证「成品对照」这条能抓住漏打光"""
import glob
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
from layout import disc_geom  # noqa: E402

V2 = r"E:\DeskTop\地球\v2"
FIN = r"E:\DeskTop\地球\成品"


def corr(a_p, b_p):
    A = np.asarray(Image.open(a_p).convert("L")).astype(np.float32)
    B = np.asarray(Image.open(b_p).convert("L")).astype(np.float32)
    H, W = A.shape
    cx, cy, R = disc_geom(W, H)
    yy, xx = np.mgrid[0:H, 0:W]
    m = np.hypot(xx - cx, yy - cy) < R * 0.95
    return float(np.corrcoef(A[m], B[m])[0, 1])


print("=== 正常对：成品 月面 vs 提升 ===")
mins = []
for f in sorted(glob.glob(os.path.join(FIN, "*_月面_提升_1920x1280.png"))):
    base = f.replace("_月面_提升_", "_月面_")
    if os.path.exists(base):
        c = corr(base, f)
        mins.append(c)
        print("  %-12s %.3f" % (os.path.basename(f)[:10], c))
if mins:
    print("  最低 %.3f" % min(mins))

print()
print("=== 模拟故障：用打光前备份冒充「漏打光」的成品 ===")
worst = 1.0
for f in sorted(glob.glob(os.path.join(V2, "_bak_uni_*_月面_1920x1280.png"))):
    d = os.path.basename(f).replace("_bak_uni_", "").replace("_月面_1920x1280.png", "")
    lit = os.path.join(FIN, "%s_月面_1920x1280.png" % d)
    if os.path.exists(lit):
        c = corr(f, lit)
        worst = min(worst, c)
        print("  %-12s 未打光 vs 已打光 → %.3f" % (d, c))
print("  最低 %.3f" % worst)
print()
print("结论：阈值 0.90 %s 区分（正常最低 %.2f vs 故障最低 %.2f）"
      % ("能" if worst < min(mins) - 0.05 else "不能", min(mins), worst))
