"""rebuild_none.py —— 重做"无影"底图：用 gamma 压阴影，不用模糊

之前用低频压平 → 锐度 9.84 → 3.47（朦胧）
现在用 gamma 0.60 抬暗部 → 阴影变浅，但边缘锐利
"""
import numpy as np
from PIL import Image

AST = r"E:\DeskTop\地球\素材"
SRC = AST + r"\moon_base_长影.png"
OUT = AST + r"\moon_base_无影.png"

A = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)
H, W = A.shape[:2]

x = np.clip(A / 255.0, 0, 1)
flat = np.clip((x ** 0.60) * 255.0, 0, 255)

# 天空保持纯黑
L = A.mean(2)
hor = np.full(W, H, dtype=np.int32)
for xx in range(W):
    idx = np.where(L[:, xx] > 12)[0]
    hor[xx] = int(idx[0]) if len(idx) else H
k = 21
pad = np.pad(hor, (k // 2, k // 2), mode="edge")
hor = np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)
terr = (np.arange(H)[:, None] > hor[None, :] + 2)[..., None]
flat = np.where(terr, flat, 0.0)

Image.fromarray(flat.astype(np.uint8)).save(OUT)
Image.open(OUT).transpose(Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_无影_mirror.png")


def metrics(p):
    B = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    h, w = B.shape
    t = B[int(h * 0.70):, :]
    t = t[t > 3]
    med = np.median(t)
    shadow = float((t < med * 0.45).mean() * 100)
    sharp = float(np.abs(np.diff(B, axis=0)).mean() + np.abs(np.diff(B, axis=1)).mean())
    return med, shadow, sharp


print("%-8s %-10s %-10s %-8s" % ("底图", "中位亮度", "阴影占比", "锐度"))
for name in ("无影", "长影"):
    med, sh, sp = metrics(AST + r"\moon_base_%s.png" % name)
    print("%-8s %-10.0f %-9.1f%% %-8.2f" % (name, med, sh, sp))
print()
print("（目标：无影的阴影占比明显低于长影，但锐度不下降）")
