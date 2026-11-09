"""shorten_shadow3.py —— 影子回缩（参数已调好）

影子掩膜：L < 局部中位数×0.85 （模糊半径 40）→ 约占 11.6%
回缩：距受光面 > T 的影子像素，填成局部中位数亮度（保留少量细节）
"""
import numpy as np
from PIL import Image, ImageFilter

AST = r"E:\DeskTop\地球\素材"
SRC = AST + r"\moon_base_v2.png"
OUT = AST + r"\moon_base_短影.png"

A = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)
H, W = A.shape[:2]
L = A.mean(2)
terr = L > 3

med = np.asarray(Image.fromarray(np.clip(L, 0, 255).astype(np.uint8))
                 .filter(ImageFilter.GaussianBlur(40))).astype(np.float32)
shadow = (L < med * 0.85) & terr
print("影子占比 %.1f%%" % (shadow.mean() * 100))

# 到受光面的距离
dist = np.zeros((H, W), dtype=np.int16)
cur = terr & ~shadow
for step in range(1, 61):
    grow = cur.copy()
    grow[1:, :] |= cur[:-1, :]
    grow[:-1, :] |= cur[1:, :]
    grow[:, 1:] |= cur[:, :-1]
    grow[:, :-1] |= cur[:, 1:]
    new = grow & ~cur
    dist[new] = step
    cur = grow
    if cur.all():
        break

# 填充亮度：局部中位数 + 少量原细节
fill = np.clip(med + (L - med) * 0.30, 0, 255)
ratio = np.where(L > 1, fill / np.maximum(L, 1.0), 1.0)

for T in (20, 35, 50):
    # 回缩量：超过 T 的全填，T-6~T 之间羽化
    w = np.clip((dist - (T - 6)) / 6.0, 0, 1) * shadow
    out = A * (1 - w[..., None]) + (A * ratio[..., None]) * w[..., None]
    out = np.where(terr[..., None], np.clip(out, 0, 255), 0)
    p = OUT.replace(".png", "_T%d.png" % T)
    Image.fromarray(out.astype(np.uint8)).save(p)
    L2 = out.mean(2)[terr]
    print("  T=%2d  改写 %.1f%%  中位 %.0f  暗部占比 %.1f%%"
          % (T, (w > 0.01).mean() * 100, np.median(L2),
             float((L2 < np.median(L2) * 0.62).mean() * 100)))
    if T == 35:
        Image.fromarray(out.astype(np.uint8)).save(OUT)
        Image.open(OUT).transpose(Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_短影_mirror.png")

print("已保存 短影（T=35）:", OUT)
