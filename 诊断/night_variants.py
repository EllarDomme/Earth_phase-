"""night_variants.py —— 同一个 92% 相位，三档月面亮度对比"""
import os
import sys

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
sys.path.insert(0, HERE)
import lighting  # noqa: E402

MID = os.path.join(HERE, "v2", "_demo_2008-10-26_c.png")   # 已合成未打光
OUT = os.path.join(HERE, "v2")

im = Image.open(MID).convert("RGB")
lit = lighting.apply_lighting(im, "2008-10-26", 3.5, verbose=False)
A = np.asarray(lit).astype(np.float32)
H, W = A.shape[:2]

# ★ 地平线必须从【底图】取：合成图里有地球，直接找亮像素会把地球当成地面
BASE = os.path.join(HERE, "素材", "moon_base_v2.png")
LB = np.asarray(Image.open(BASE).convert("L")).astype(np.float32)
HB, WB = LB.shape
hor = np.full(WB, HB, dtype=np.int32)
for x in range(WB):
    idx = np.where(LB[:, x] > 12)[0]
    hor[x] = int(idx[0]) if len(idx) else HB
k = 21
pad = np.pad(hor, (k // 2, k // 2), mode="edge")
hor = np.array([pad[i:i + k].min() for i in range(WB)], dtype=np.int32)
yy = np.arange(H)[:, None]
terr = (yy > hor[None, :] + 2)[..., None]

VARIANTS = [
    ("严格物理（1/10000）", 0.006, 1.2),
    ("折中（约 1/170）", 0.06, 1.8),
    ("轻度压暗（约 1/25）", 0.25, 2.0),
]
outs = []
for name, g, floor in VARIANTS:
    out = A * g + floor
    out[..., 0] *= 0.92
    out[..., 2] *= 1.03
    out = np.where(terr, np.clip(out, 0, 255), A)
    t = out[terr[..., 0]].mean(1)
    print("  %-18s 增益 %.3f  地形均 %5.1f  p95 %5.1f" % (name, g, t.mean(), np.percentile(t, 95)))
    p = os.path.join(OUT, "_night_%s.png" % ("strict" if g < 0.01 else ("mid" if g < 0.1 else "soft")))
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(p)
    outs.append((name, p))

S = (620, 413)
sheet = Image.new("RGB", (S[0] * len(outs) + 8 * (len(outs) - 1), S[1]), (8, 8, 8))
for i, (_, p) in enumerate(outs):
    sheet.paste(Image.open(p).resize(S, Image.LANCZOS), (i * (S[0] + 8), 0))
sp = os.path.join(OUT, "_night_sheet.png")
sheet.save(sp)
print("对比条:", sp)
