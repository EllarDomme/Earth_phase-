"""grad_dir.py —— 用"平均亮度梯度"测光照方向，并自检镜像是否翻转

物理依据：斜射光下，朝向太阳的坡面更亮 → 亮度沿"指向太阳"的方向递增
          → 平均梯度方向 ≈ 指向太阳的方向。
自检：镜像版必须给出反向的 x 分量，否则测法本身有问题。
"""
import numpy as np
from PIL import Image

AST = r"E:\DeskTop\地球\素材"


def grad_dir(path):
    A = np.asarray(Image.open(path).convert("L")).astype(np.float32)
    H, W = A.shape
    terr = A > 3
    # 地形区（下半部，避开天空）
    m = terr.copy()
    m[: int(H * 0.62)] = False
    gy, gx = np.gradient(A)
    # 只用有效区域
    gx = gx[m]
    gy = gy[m]
    # 去掉极端值
    k = np.percentile(np.hypot(gx, gy), 99)
    sel = np.hypot(gx, gy) < k
    mx, my = float(gx[sel].mean()), float(gy[sel].mean())
    ang = np.degrees(np.arctan2(-my, mx))     # 0=右, 90=上
    return ang, mx, my


print("%-14s %-10s %-12s %-12s" % ("底图", "指向太阳角", "mean(dx)", "mean(dy)"))
for n in ("无影", "短影", "中影", "长影"):
    for suf in ("", "_mirror"):
        ang, mx, my = grad_dir(AST + r"\moon_base_%s%s.png" % (n, suf))
        print("%-14s %-10.0f° %+12.3f %+12.3f" % (n + suf, ang, mx, my))
