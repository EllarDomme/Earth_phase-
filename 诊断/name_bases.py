"""name_bases.py —— 三张底图统一命名：无影 / 中影 / 长影

生成规则：
  长影 = 原 moon_base.png（阴影最深）
  中影 = 豆包新做的那张（已补齐到 1920×1280）
  无影 = 从长影做低频压平（动态范围压到 ~2.5）
"""
import os
import shutil

import numpy as np
from PIL import Image, ImageFilter

AST = r"E:\DeskTop\地球\素材"

LONG = os.path.join(AST, "moon_base.png")
MID = os.path.join(AST, "moon_base_mid.png")

# ① 长影
shutil.copy2(LONG, os.path.join(AST, "moon_base_长影.png"))
shutil.copy2(LONG, os.path.join(AST, "moon_base_长影_mirror.png"))
print("长影 → moon_base_长影.png")

# ② 中影（已补齐）
shutil.copy2(MID, os.path.join(AST, "moon_base_中影.png"))
shutil.copy2(MID, os.path.join(AST, "moon_base_中影_mirror.png"))
print("中影 → moon_base_中影.png")

# ③ 无影：从长影压平（保证同一个地形）
A = np.asarray(Image.open(LONG).convert("RGB")).astype(np.float32)
H, W = A.shape[:2]
L = A.mean(2)
hor = np.full(W, H, dtype=np.int32)
for x in range(W):
    idx = np.where(L[:, x] > 12)[0]
    hor[x] = int(idx[0]) if len(idx) else H
k = 21
pad = np.pad(hor, (k // 2, k // 2), mode="edge")
hor = np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)
terr = (np.arange(H)[:, None] > hor[None, :] + 2)[..., None]

low = np.asarray(Image.fromarray(A.astype(np.uint8))
                 .filter(ImageFilter.GaussianBlur(55))).astype(np.float32)
flat = np.where(terr, np.clip(low + (A - low) * 0.35, 0, 255), 0.0)
Image.fromarray(flat.astype(np.uint8)).save(os.path.join(AST, "moon_base_无影.png"))
Image.open(os.path.join(AST, "moon_base_无影.png")).transpose(
    Image.FLIP_LEFT_RIGHT).save(os.path.join(AST, "moon_base_无影_mirror.png"))
print("无影 → moon_base_无影.png（从长影压平）")


def stats(p):
    B = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    h, w = B.shape
    t = B[int(h * 0.62):, :]
    t = t[t > 3]
    p5, p95 = np.percentile(t, [5, 95])
    yy = []
    for x in range(0, w, 40):
        idx = np.where(B[:, x] > 18)[0]
        yy.append(int(idx[0]) if len(idx) else h)
    return p95 / max(p5, 1e-6), int(np.median(yy)), "%.0f" % t.mean()


print()
print("%-8s %-10s %-10s %-8s" % ("底图", "阴影深度", "地平线", "地形均"))
for name in ("无影", "中影", "长影"):
    p = os.path.join(AST, "moon_base_%s.png" % name)
    d, hz, m = stats(p)
    print("%-8s %-10.1f %-10d %-8s" % (name, d, hz, m))
