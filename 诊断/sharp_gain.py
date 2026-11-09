"""sharp_gain.py —— 量化"提升"这一步在成品里还剩多少细节"""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
from layout import disc_geom  # noqa: E402

CASES = ["2024-02-21", "2005-01-01", "2008-10-29"]


def hf_energy(f, mask=None):
    A = np.asarray(Image.open(f).convert("L")).astype(np.float32)
    H, W = A.shape
    cx, cy, R = disc_geom(W, H)
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.hypot(xx - cx, yy - cy) / R
    m = rr < 0.95 if mask is None else mask
    # 高频能量：与 3px 模糊的差
    from PIL import ImageFilter
    bl = np.asarray(Image.fromarray(A.astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(3))).astype(np.float32)
    d = np.abs(A - bl)[m]
    return float(d.mean())


print("%-12s %-12s %-12s %-8s" % ("日期", "月面版(盘内)", "提升版(盘内)", "增益"))
for d in CASES:
    a = r"E:\DeskTop\地球\成品\%s_月面_1920x1280.png" % d
    b = r"E:\DeskTop\地球\成品\%s_月面_提升_1920x1280.png" % d
    try:
        ea, eb = hf_energy(a), hf_energy(b)
        print("%-12s %-12.2f %-12.2f %-8.2f×" % (d, ea, eb, eb / max(ea, 1e-6)))
    except Exception as e:
        print("%-12s 跳过（%s）" % (d, str(e)[:30]))

print()
print("说明：盘内直径约 691px。若把「提升」放到 2048 的圆盘上做，")
print("      再缩到 691px 使用，缩放比约 0.34×——高频基本被平均掉。")
