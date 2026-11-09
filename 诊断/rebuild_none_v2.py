"""rebuild_none_from_v2.py —— 无影底图改为从 v2 提亮（不再用长影）

理由：v2 是新的干净底图（阴影占比 ~7.8），长影更重。
提亮用 gamma（改色调曲线，不动结构），保证锐利不朦胧。
"""
import numpy as np
from PIL import Image

AST = r"E:\DeskTop\地球\素材"
SRC = AST + r"\moon_base_v2.png"
OUT = AST + r"\moon_base_无影.png"

A = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)
H, W = A.shape[:2]

x = np.clip(A / 255.0, 0, 1)
flat = np.clip((x ** 0.62) * 255.0, 0, 255)

# 天空保持纯黑
L = A.mean(2)
terr = L > 3
flat = np.where(terr[..., None], flat, 0.0)

Image.fromarray(flat.astype(np.uint8)).save(OUT)
Image.open(OUT).transpose(Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_无影_mirror.png")


def stats(p):
    B = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    h, w = B.shape
    t = B[int(h * 0.70):, :]
    t = t[t > 3]
    med = np.median(t)
    sh = float((t < med * 0.45).mean() * 100)
    sharp = float(np.abs(np.diff(B, axis=0)).mean() + np.abs(np.diff(B, axis=1)).mean())
    return med, sh, sharp


print("%-14s %-10s %-10s %-8s" % ("底图", "中位亮度", "阴影占比", "锐度"))
for name, p in (("v2（基准）", SRC), ("无影（新）", OUT)):
    med, sh, sp = stats(p)
    print("%-14s %-10.0f %-9.1f%% %-8.2f" % (name, med, sh, sp))
