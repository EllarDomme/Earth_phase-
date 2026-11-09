"""texture_fix_test.py —— 三种深色月面质感方案（零额度）"""
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, r"E:\DeskTop\地球")
import lighting  # noqa: E402

PRE = r"E:\DeskTop\地球\v2\_bak_uni_2006-04-05_月面_提升_1920x1280.png"
DATE, UTC = "2006-04-05", 7.75

lit = np.asarray(lighting.apply_lighting(Image.open(PRE).convert("RGB"), DATE, UTC,
                                         verbose=False)).astype(np.float32)
terr = np.zeros(lit.shape[:2], bool)
terr[900:, :] = lit[900:, :].mean(2) > 1


def stats(A, tag):
    t = A[900:, :].mean(2)
    t = t[t > 1]
    med = float(np.median(t))
    from PIL import ImageFilter  # noqa: F401
    bl = np.asarray(Image.fromarray(A[900:, :].mean(2).astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(3))).astype(np.float32)
    hf = float(np.abs(A[900:, :].mean(2) - bl)[A[900:, :].mean(2) > 1].mean())
    lv = len(np.unique(t.astype(np.uint8)))
    print("  %-22s 中位 %5.1f  标准差 %5.1f  色阶 %3d  高频 %5.2f"
          % (tag, med, t.std(), lv, hf))
    return med


def apply_contrast(A, k, pivot=None):
    """围绕中位做对比度拉伸（保持平均亮度不变）"""
    t = A[900:, :].mean(2)
    t = t[t > 1]
    p = float(np.median(t)) if pivot is None else pivot
    B = A.copy()
    B[terr] = np.clip(p + (A[terr] - p) * k, 0, 255)
    return B


print("=== 现状 ===")
m0 = stats(lit, "A 现状")

print("\n=== 方案 B：围绕中位拉对比 ===")
for k in (1.6, 2.0, 2.4):
    stats(apply_contrast(lit, k), "B 对比×%.1f" % k)

print("\n=== 方案 C：先提亮再压回（保均值，扩色阶）===")
for g in (0.80, 0.70):
    t = lit[900:, :].mean(2)
    t = t[t > 1]
    med = float(np.median(t))
    B = lit.copy()
    x = np.clip(B[terr] / 255.0, 0, 1) ** g * 255.0
    # 再把中位拉回原值
    t2 = x.mean(1)
    new_med = float(np.median(t2))
    if new_med > 1:
        x = x * (med / new_med)
    B[terr] = np.clip(x, 0, 255)
    stats(B, "C gamma%.2f+还原" % g)

# 存两张图供肉眼比较
Image.fromarray(np.clip(apply_contrast(lit, 2.0), 0, 255).astype(np.uint8)).save(
    r"E:\DeskTop\草稿\_tex_B20.png")
Image.fromarray(np.clip(lit, 0, 255).astype(np.uint8)).save(
    r"E:\DeskTop\草稿\_tex_A.png")
print("\n已保存 _tex_A.png / _tex_B20.png")
