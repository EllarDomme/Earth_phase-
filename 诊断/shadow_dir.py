"""shadow_dir.py —— 量出影子的延伸方向（修正版：位移写法，避免形状不匹配）"""
import numpy as np
from PIL import Image, ImageFilter

AST = r"E:\DeskTop\地球\素材"


def shift(a, dy, dx, fill=-1):
    out = np.full_like(a, fill)
    H, W = a.shape[:2]
    ys = slice(max(0, dy), H + min(0, dy))
    yd = slice(max(0, -dy), H + min(0, -dy))
    xs = slice(max(0, dx), W + min(0, dx))
    xd = slice(max(0, -dx), W + min(0, -dx))
    out[yd, xd] = a[ys, xs]
    return out


def analyze(path, name):
    A = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    H, W = A.shape[:2]
    L = A.mean(2)
    terr = L > 3
    med = np.asarray(Image.fromarray(np.clip(L, 0, 255).astype(np.uint8))
                     .filter(ImageFilter.GaussianBlur(40))).astype(np.float32)
    shadow = (L < med * 0.85) & terr

    lit = terr & ~shadow
    oy = np.where(lit, np.arange(H)[:, None], -1).astype(np.int32)
    ox = np.where(lit, np.arange(W)[None, :], -1).astype(np.int32)
    known = lit.copy()

    for _ in range(240):
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            src_known = shift(known.astype(np.uint8), -dy, -dx, 0).astype(bool)
            new = src_known & ~known
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
    ry, rx = ry / rn, rx / rn
    ang = np.degrees(np.arctan2(-ry, -rx))
    print("%-6s 受光方向(dx=%+.2f,dy=%+.2f)  影子延伸(dx=%+.2f,dy=%+.2f)  角度 %.0f°  影子占比 %.1f%%"
          % (name, rx, ry, -rx, -ry, ang, shadow.mean() * 100))
    return -rx, -ry


analyze(AST + r"\moon_base_长影.png", "长影")
analyze(AST + r"\moon_base_v2.png", "v2")
