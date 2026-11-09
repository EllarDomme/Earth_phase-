"""noon_fix.py —— 2% 相位（正午）的三种做法对比

A. 原版（长影，方向错但锐利）
B. 我之前的"低频压平"（无影但朦胧 ← 问题所在）
C. 改进：gamma 抬暗部（阴影变浅、边缘仍锐）
"""
import os

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
BASE = os.path.join(HERE, "素材", "moon_base_v2.png")
OUT = r"E:\DeskTop\草稿"

A = np.asarray(Image.open(BASE).convert("RGB")).astype(np.float32)
H, W = A.shape[:2]

# A：原版
a = A.copy()

# B：低频压平（旧的错误做法）
from PIL import ImageFilter
low = np.asarray(Image.fromarray(A.astype(np.uint8))
                 .filter(ImageFilter.GaussianBlur(55))).astype(np.float32)
b = np.clip(low + (A - low) * 0.35, 0, 255)

# C：gamma 抬暗部（保留锐度）
x = np.clip(A / 255.0, 0, 1)
c = np.clip((x ** 0.62) * 255.0 * 1.06, 0, 255)

crop = (0, 780, W, 1280)     # 只看前景地形
S = (760, 198)
tiles = []
for name, img in (("A 原版（长影）", a), ("B 低频压平（朦胧）", b), ("C gamma抬暗部（推荐）", c)):
    t = Image.fromarray(img.astype(np.uint8)).crop(crop).resize(S, Image.LANCZOS)
    tiles.append((name, t))
    Image.fromarray(img.astype(np.uint8)).save(os.path.join(OUT, "正午_%s.png" % name[0]))

sheet = Image.new("RGB", (S[0], S[1] * 3 + 12), (10, 10, 10))
for i, (name, t) in enumerate(tiles):
    sheet.paste(t, (0, i * (S[1] + 6)))
sp = os.path.join(OUT, "正午三种做法.png")
sheet.save(sp)


def sharpness(img):
    g = np.asarray(Image.fromarray(img.astype(np.uint8)).convert("L")).astype(np.float32)
    return float(np.abs(np.diff(g, axis=0)).mean() + np.abs(np.diff(g, axis=1)).mean())


def shadow_depth(img):
    g = np.asarray(Image.fromarray(img.astype(np.uint8)).convert("L")).astype(np.float32)[780:]
    v = g[g > 3]
    return float(np.percentile(v, 95) / max(np.percentile(v, 5), 1e-6))


for name, img in (("A 原版", a), ("B 低频压平", b), ("C gamma", c)):
    print("  %-10s 阴影深度(p95/p5) %5.1f   锐度 %5.2f" % (name, shadow_depth(img), sharpness(img)))
print("对比图:", sp)
