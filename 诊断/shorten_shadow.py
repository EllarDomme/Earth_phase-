"""shorten_shadow.py —— 让 v2 的影子变短（影子从"远端"回缩）

原理：
  太阳升高时，影子不是变浅，而是**从远端往物体根部缩**。
  做法：
    ① 找出影子（比局部中位数明显暗）
    ② 算每个影子像素到"受光面"的距离
    ③ 距离超过 T 的影子像素 → 当作受光面（用邻域亮度填回）
  效果：影子长度缩短，边界仍锐利。
"""
import numpy as np
from PIL import Image, ImageFilter

AST = r"E:\DeskTop\地球\素材"
SRC = AST + r"\moon_base_v2.png"
OUT = AST + r"\moon_base_短影.png"

A = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)
H, W = A.shape[:2]
L = A.mean(2)

# 只在有地形的地方做
terr = L > 3

# ① 局部中位数（大半径模糊近似）
med = np.asarray(Image.fromarray(np.clip(L, 0, 255).astype(np.uint8))
                 .filter(ImageFilter.GaussianBlur(25))).astype(np.float32)
shadow = (L < med * 0.62) & terr
print("影子像素占比 %.1f%%" % (shadow.mean() * 100))

for T in (10, 18, 28):
    # ② 到受光面的距离（迭代膨胀）
    lit = terr & ~shadow
    dist = np.where(shadow, 255, 0).astype(np.int16)
    cur = lit.copy()
    for step in range(1, T + 1):
        grow = cur.copy()
        grow[1:, :] |= cur[:-1, :]
        grow[:-1, :] |= cur[1:, :]
        grow[:, 1:] |= cur[:, :-1]
        grow[:, :-1] |= cur[:, 1:]
        new = grow & ~cur
        dist[new] = step
        cur = grow
    far = shadow & (dist > T)

    # ③ 远端影子填成"受光面"亮度（用中位数近似，再叠一点原细节）
    detail = L - med
    fill = np.clip(med + detail * 0.25, 0, 255)
    ratio = np.where(med > 1, fill / np.maximum(L, 1), 1.0)
    out = A * ratio[..., None]
    out = np.where(far[..., None], out, A)
    out = np.where(terr[..., None], np.clip(out, 0, 255), A)

    p = OUT.replace(".png", "_T%d.png" % T)
    Image.fromarray(out.astype(np.uint8)).save(p)
    L2 = out.mean(2)
    t = L2[terr]
    print("  T=%2d  改写像素 %.1f%%  影子占比 %.1f%%"
          % (T, far.mean() * 100, float((t < np.median(t) * 0.62).mean() * 100)))
    if T == 18:
        Image.fromarray(out.astype(np.uint8)).save(OUT)
        Image.open(OUT).transpose(Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_短影_mirror.png")

print("已保存 短影（T=18）:", OUT)
