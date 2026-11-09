"""cmp_boostfirst.py —— 新流程 vs 旧流程 vs 两张之间"""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
from layout import disc_geom  # noqa: E402

OLD_N = r"E:\DeskTop\草稿\_cmp_2005\旧_月面.png"
OLD_B = r"E:\DeskTop\草稿\_cmp_2005\旧_提升.png"
NEW_N = r"E:\DeskTop\地球\成品\2005-01-01_月面_1920x1280.png"
NEW_B = r"E:\DeskTop\地球\成品\2005-01-01_月面_提升_1920x1280.png"


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float32)


def masks(shape):
    H, W = shape[:2]
    cx, cy, R = disc_geom(W, H)
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.hypot(xx - cx, yy - cy) / R
    return rr > 1.15, rr < 0.95


def cmp(a_path, b_path, label):
    A, B = load(a_path), load(b_path)
    far, inner = masks(A.shape)
    d = np.abs(A - B).max(2)
    print("%-34s 盘外(月面/天空) 最大 %5.1f   盘内(地球) 最大 %5.0f"
          % (label, d[far].max(), d[inner].max()))
    return d[far].max(), d[inner].max()


print("=== 关键对照 ===")
cmp(OLD_N, NEW_N, "旧月面 vs 新月面")
cmp(NEW_N, NEW_B, "新月面 vs 新提升")

print()
print("=== 天空检查（圆盘外 15% 以远、地平线以上）===")
for tag, p in (("新月面", NEW_N), ("新提升", NEW_B)):
    A = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    H, W = A.shape
    far, _ = masks(A.shape)
    sky = far & (np.arange(H)[:, None] < 700)
    v = A[sky]
    print("  %-8s 均值 %.2f  p99 %.1f  最大 %.0f" % (tag, v.mean(), np.percentile(v, 99), v.max()))

print()
print("=== 提升效果（盘内高频能量）===")
from PIL import ImageFilter  # noqa: E402


def hf(p):
    A = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    _, inner = masks(A.shape)
    bl = np.asarray(Image.fromarray(A.astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(3))).astype(np.float32)
    return float(np.abs(A - bl)[inner].mean())


e_n, e_b = hf(NEW_N), hf(NEW_B)
print("  新月面 %.2f → 新提升 %.2f  （%.2f×）" % (e_n, e_b, e_b / max(e_n, 1e-6)))
