"""terrain_layers_test.py —— 月面层次三方案（零额度）

物理依据：高相位时月面只有地球反照，光源方向≈相机方向 → 正面光、无阴影，
但反照率（月海 vs 溅射物）差异完整保留。所以正确做法是"保中位、扩反照率"，
而不是"整体压暗"。
"""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
import lighting  # noqa: E402

OUT = r"E:\DeskTop\草稿"


def stats(A, tag):
    t = A[900:, :].mean(2)
    t = t[t > 1]
    if t.size == 0:
        print("  %-26s 无地形" % tag)
        return
    p5, p95 = np.percentile(t, [5, 95])
    print("  %-26s 中位 %4.0f   p5~p95 %2.0f~%3.0f   范围 %2d 级"
          % (tag, np.median(t), p5, p95, int(p95 - p5)))


def apply_terrain(A, k):
    """围绕地形中位扩对比（保中位）"""
    B = A.copy()
    lum = B[900:, :].mean(2)
    m = lum > 1
    idx = np.zeros(lum.shape, bool)
    idx[:] = m
    sub = B[900:, :][idx]
    med = float(np.median(sub.mean(1)))
    B[900:, :][idx] = np.clip(med + (sub - med) * k, 0, 255)
    return B


# ① 现状：直接把现有成品读进来
P1 = r"E:\DeskTop\地球\成品\2008-10-26_月面_提升_1920x1280.png"
V1 = np.asarray(Image.open(P1).convert("RGB")).astype(np.float32)
stats(V1, "① 现状")
Image.fromarray(V1.astype(np.uint8)).save(OUT + r"\_L1.png")

# ② 保中位 + 反照率对比 ×2.4
V2 = apply_terrain(V1, 2.4)
stats(V2, "② 保中位·对比×2.4")
Image.fromarray(V2.astype(np.uint8)).save(OUT + r"\_L2.png")

# ②b 更强 ·3.0
V2b = apply_terrain(V1, 3.0)
stats(V2b, "②b 保中位·对比×3.0")
Image.fromarray(V2b.astype(np.uint8)).save(OUT + r"\_L2b.png")

# ③ 对照组：长影日期（真实有影子）
P3 = r"E:\DeskTop\地球\v2\_bak_uni_2021-06-18_月面_提升_1920x1280.png"
try:
    V3 = np.asarray(Image.open(P3).convert("RGB")).astype(np.float32)
    stats(V3, "③ 长影日期 2021-06-18")
    Image.fromarray(V3.astype(np.uint8)).save(OUT + r"\_L3.png")
except Exception as e:
    print("  ③ 跳过：", e)

print("\n三张已存到 草稿\\_L1.png / _L2.png / _L3.png")
