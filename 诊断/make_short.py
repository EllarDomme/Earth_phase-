"""make_short.py —— 从"无影"生成"短影"

无影 = v2 ^ 0.62
短影 = v2 ^ 0.80  ⇒  短影 = 无影 ^ (0.80/0.62) = 无影 ^ 1.290
"""
import numpy as np
from PIL import Image

AST = r"E:\DeskTop\地球\素材"
NONE = AST + r"\moon_base_无影.png"
OUT = AST + r"\moon_base_短影.png"
V2 = AST + r"\moon_base_v2.png"

A = np.asarray(Image.open(NONE).convert("RGB")).astype(np.float32)
H, W = A.shape[:2]

x = np.clip(A / 255.0, 0, 1)
short = np.clip((x ** (0.80 / 0.62)) * 255.0, 0, 255)

# 天空保持纯黑（用无影图的非黑区域做掩膜）
L = A.mean(2)
terr = L > 3
short = np.where(terr[..., None], short, 0.0)

Image.fromarray(short.astype(np.uint8)).save(OUT)
Image.open(OUT).transpose(Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_短影_mirror.png")


def stats(p):
    B = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    h, w = B.shape
    t = B[int(h * 0.70):, :]
    t = t[t > 3]
    med = np.median(t)
    sh = float((t < med * 0.45).mean() * 100)
    sharp = float(np.abs(np.diff(B, axis=0)).mean() + np.abs(np.diff(B, axis=1)).mean())
    return med, sh, sharp


rows = [("无影", NONE), ("短影（新）", OUT), ("长影 = v2", V2)]
print("%-12s %-10s %-10s %-8s" % ("底图", "中位亮度", "阴影占比", "锐度"))
for name, p in rows:
    med, sh, sp = stats(p)
    print("%-12s %-10.0f %-9.1f%% %-8.2f" % (name, med, sh, sp))

# 三张并排（只看地形）
S = (700, 300)
crop_y = 900
tiles = [Image.open(p).crop((0, crop_y, 1920, 1280)).resize(S, Image.LANCZOS) for _, p in rows]
sheet = Image.new("RGB", (S[0] * 3 + 12, S[1]), (10, 10, 10))
for i, t in enumerate(tiles):
    sheet.paste(t, (i * (S[0] + 6), 0))
sheet.save(r"E:\DeskTop\草稿\无影_短影_长影.png")
print("对比图: 草稿\\无影_短影_长影.png")
