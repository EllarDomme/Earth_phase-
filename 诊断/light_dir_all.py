"""light_dir_all.py —— 四张底图的光照方向是否一致（镜像判断依赖它）"""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
AST = r"E:\DeskTop\地球\素材"


def dir_of(path):
    A = np.asarray(Image.open(path).convert("L")).astype(np.float32)
    H, W = A.shape
    terr = A > 3
    med = np.asarray(Image.fromarray(np.clip(A, 0, 255).astype(np.uint8))
                     .filter(__import__("PIL.ImageFilter", fromlist=["x"]).GaussianBlur(40))).astype(np.float32)
    shadow = (A < med * 0.85) & terr
    lit = terr & ~shadow

    oy = np.where(lit, np.arange(H)[:, None], -1).astype(np.int32)
    ox = np.where(lit, np.arange(W)[None, :], -1).astype(np.int32)
    known = lit.copy()

    def shift(a, dy, dx, fill=-1):
        out = np.full_like(a, fill)
        ys = slice(max(0, dy), H + min(0, dy))
        yd = slice(max(0, -dy), H + min(0, -dy))
        xs = slice(max(0, dx), W + min(0, dx))
        xd = slice(max(0, -dx), W + min(0, -dx))
        out[yd, xd] = a[ys, xs]
        return out

    for _ in range(200):
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            near = shift(known.astype(np.uint8), -dy, -dx, 0).astype(bool)
            new = near & ~known
            if new.any():
                sy = shift(oy, -dy, -dx, 0)
                sx = shift(ox, -dy, -dx, 0)
                oy[new] = sy[new]
                ox[new] = sx[new]
                known |= new
        if known.all():
            break

    yy, xx = np.mgrid[0:H, 0:W]
    dys = (oy - yy)[shadow].astype(np.float32)
    dxs = (ox - xx)[shadow].astype(np.float32)
    n = np.hypot(dys, dxs) + 1e-6
    ry, rx = float((dys / n).mean()), float((dxs / n).mean())
    rn = np.hypot(ry, rx) + 1e-9
    ang = np.degrees(np.arctan2(-(ry / rn), -(rx / rn)))   # 影子延伸方向
    return ang, shadow.mean() * 100


print("%-6s %-12s %-12s" % ("底图", "影子延伸角", "影子占比"))
for n in ("无影", "短影", "中影", "长影"):
    for suf in ("", "_mirror"):
        ang, sh = dir_of(AST + r"\moon_base_%s%s.png" % (n, suf))
        print("%-6s %-12.0f° %-12.1f%%" % (n + suf, ang, sh))
