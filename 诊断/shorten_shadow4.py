"""shorten_shadow4.py —— 用形态学收缩让影子变短

① 抓影子掩膜（比局部中位数暗 15%）
② 闭运算去掉噪点（先膨胀再收缩）
③ 用圆形结构元做腐蚀 → 影子整体缩一圈（等于影子变短变窄）
④ 被移掉的影子像素填成"受光面"亮度
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


def dilate(m, r):
    for _ in range(r):
        g = m.copy()
        g[1:, :] |= m[:-1, :]
        g[:-1, :] |= m[1:, :]
        g[:, 1:] |= m[:, :-1]
        g[:, :-1] |= m[:, 1:]
        m = g
    return m


def erode(m, r):
    return ~dilate(~m, r)


# ② 闭运算：先膨胀 3 再腐蚀 3，把散点连成块
solid = erode(dilate(shadow, 3), 3)
print("原始影子 %.1f%%  闭运算后 %.1f%%" % (shadow.mean() * 100, solid.mean() * 100))

fill = np.clip(med + (L - med) * 0.30, 0, 255)
ratio = np.where(L > 1, fill / np.maximum(L, 1.0), 1.0)

for R in (8, 14, 20):
    shrunken = erode(solid, R)
    removed = solid & ~shrunken          # 被收掉的影子
    out = A * ratio[..., None] * removed[..., None] + A * (~removed)[..., None]
    out = np.where(terr[..., None], np.clip(out, 0, 255), 0)
    p = OUT.replace(".png", "_R%d.png" % R)
    Image.fromarray(out.astype(np.uint8)).save(p)
    L2 = out.mean(2)[terr]
    print("  收缩 %2dpx  影子 %.1f%% → %.1f%%  中位 %.0f"
          % (R, solid.mean() * 100, shrunken.mean() * 100, np.median(L2)))
    if R == 14:
        Image.fromarray(out.astype(np.uint8)).save(OUT)
        Image.open(OUT).transpose(Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_短影_mirror.png")

print("已保存 短影（收缩 14px）:", OUT)
