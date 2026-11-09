"""shorten_dir.py —— 沿影子延伸方向回缩（只削尖端，不动根部）

实测：v2 的影子延伸方向 (dx=-0.28, dy=-0.96)，即朝左上方
回缩 k 像素 = 只保留"往尖端方向再走 k 步仍是影子"的像素
"""
import numpy as np
from PIL import Image, ImageFilter

AST = r"E:\DeskTop\地球\素材"
SRC = AST + r"\moon_base_v2.png"
OUT = AST + r"\moon_base_短影.png"

DX, DY = -0.28, -0.96          # 影子延伸方向（朝左上）

A = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)
H, W = A.shape[:2]
L = A.mean(2)
terr = L > 3

med = np.asarray(Image.fromarray(np.clip(L, 0, 255).astype(np.uint8))
                 .filter(ImageFilter.GaussianBlur(40))).astype(np.float32)
shadow = (L < med * 0.85) & terr


def shift(a, dy, dx, fill=0):
    out = np.full_like(a, fill)
    ys = slice(max(0, dy), H + min(0, dy))
    yd = slice(max(0, -dy), H + min(0, -dy))
    xs = slice(max(0, dx), W + min(0, dx))
    xd = slice(max(0, -dx), W + min(0, -dx))
    out[yd, xd] = a[ys, xs]
    return out


fill = np.clip(med + (L - med) * 0.30, 0, 255)
ratio = np.where(L > 1, fill / np.maximum(L, 1.0), 1.0)

print("%-10s %-10s %-10s" % ("回缩量", "影子占比", "改写像素"))
for k in (12, 22, 32):
    sy, sx = int(round(k * DY)), int(round(k * DX))
    keep = shadow & shift(shadow, sy, sx, 0)      # 往尖端走 k 步仍是影子才保留
    removed = shadow & ~keep
    out = np.where(removed[..., None], A * ratio[..., None], A)
    out = np.where(terr[..., None], np.clip(out, 0, 255), 0)

    if k == 22:
        # 把结果再算一次影子占比
        L2 = out.mean(2)
        med2 = np.asarray(Image.fromarray(np.clip(L2, 0, 255).astype(np.uint8))
                          .filter(ImageFilter.GaussianBlur(40))).astype(np.float32)
        sh2 = (L2 < med2 * 0.85) & (L2 > 3)
        print("%-10s %-10.2f%% %-10.1f%%" % ("k=%d" % k, sh2.mean() * 100, removed.mean() * 100))
        Image.fromarray(out.astype(np.uint8)).save(OUT)
        Image.open(OUT).transpose(Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_短影_mirror.png")
    else:
        print("%-10s %-10s %-10.1f%%" % ("k=%d" % k, "-", removed.mean() * 100))
    Image.fromarray(out.astype(np.uint8)).save(OUT.replace(".png", "_k%d.png" % k))

print("已保存 短影（k=22）:", OUT)
