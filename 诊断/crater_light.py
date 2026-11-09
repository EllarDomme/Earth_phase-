"""crater_light.py —— 用大坑亮斑定光照方向（碗形坑：亮壁在太阳对面）"""
import numpy as np
from PIL import Image

AST = r"E:\DeskTop\地球\素材"
BOX = (330, 1010, 1060, 1280)     # 大坑区域


def crater_dir(path):
    B = np.asarray(Image.open(path).convert("L")).astype(np.float32)
    X0, Y0, X1, Y1 = BOX
    sub = B[Y0:Y1, X0:X1]
    h, w = sub.shape
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w * 0.45, h * 0.55
    r = np.hypot((xx - cx) / (w * 0.42), (yy - cy) / (h * 0.55))
    inner = (r > 0.45) & (r < 0.95)
    if inner.sum() < 500:
        return None
    bright = sub > np.percentile(sub[inner], 92)
    by = (yy[bright & inner] - cy).mean()
    bx = (xx[bright & inner] - cx).mean()
    n = np.hypot(bx, by) + 1e-6
    # 亮壁方向
    bright_ang = np.degrees(np.arctan2(-by / n, bx / n))
    # 太阳方向 = 亮壁的反方向
    sun_ang = (bright_ang + 180) % 360
    if sun_ang > 180:
        sun_ang -= 360
    return bright_ang, sun_ang


print("%-14s %-12s %-14s" % ("底图", "亮壁方向", "推定太阳方向"))
for nm in ("无影", "短影", "中影", "长影"):
    for suf in ("", "_mirror"):
        r = crater_dir(AST + r"\moon_base_%s%s.png" % (nm, suf))
        if r is None:
            print("%-14s 区域无坑" % (nm + suf))
            continue
        ba, sa = r
        print("%-14s %-12.0f° %-14.0f°" % (nm + suf, ba, sa))
print()
print("（角度约定：0=右, 90=上, 负数=下）")
