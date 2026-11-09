"""base_by_phase.py —— 只处理「月面底图」本身：不同相位下它该变成什么样

不做合成、不加地球，只看底图在各地相下被调成什么亮度/对比。
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
BASE = os.path.join(HERE, "素材", "moon_base_v2.png")
OUT = os.path.join(HERE, "v2")

PHASES = [0.02, 0.25, 0.41, 0.63, 0.76, 0.92, 1.00]


def sun_elev(k):
    return 90 - np.degrees(np.arccos(np.clip(1 - 2 * k, -1, 1)))


def grade(A, h):
    """按太阳高度调整月面：正午→压对比提亮；低太阳→不变；月夜→压暗+抬暗部"""
    out = A.copy()
    if h > 20:
        # 正午：光从头顶来，阴影浅 → 压对比 + 轻微提亮
        m = A.mean()
        out = m + (A - m) * 0.55
        out = out * 1.08
        tag = "压对比提亮"
    elif h >= 6:
        tag = "保持"
    elif h >= 0:
        t = h / 6.0
        g = 0.15 + (1.0 - 0.15) * t
        out = A * g
        tag = "增益 %.2f" % g
    elif h >= -6:
        t = (h + 6) / 6.0
        g = 0.02 + (0.15 - 0.02) * t
        out = A * g
        tag = "增益 %.3f" % g
    else:
        t = min(1.0, (-6 - h) / 54.0)
        g = 0.02 * (1 - t) + 0.06 * t        # 夜间取 0.06（人眼观感档）
        out = A * g + 1.8
        out[..., 0] *= 0.92
        out[..., 2] *= 1.03
        tag = "增益 %.3f" % g
    return np.clip(out, 0, 255), tag


A0 = np.asarray(Image.open(BASE).convert("RGB")).astype(np.float32)
H, W = A0.shape[:2]
crop = (0, int(H * 0.42), W, H)          # 只看地形部分

tiles = []
for k in PHASES:
    h = sun_elev(k)
    out, tag = grade(A0, h)
    t = out[crop[1]:crop[3]]
    lum = t.mean()
    tiles.append((k, h, tag, lum, np.clip(out, 0, 255).astype(np.uint8)))
    print("相位 %3.0f%%  太阳 %+6.1f°  %-12s 地形均 %5.1f" % (k * 100, h, tag, lum))

S = (520, 300)
sheet = Image.new("RGB", (S[0] * len(tiles) + 6 * (len(tiles) - 1), S[1]), (10, 10, 10))
for i, (k, h, tag, lum, arr) in enumerate(tiles):
    im = Image.fromarray(arr).crop((0, int(H * 0.42), W, H)).resize(S, Image.LANCZOS)
    sheet.paste(im, (i * (S[0] + 6), 0))
sp = os.path.join(OUT, "_base_phase_sheet.png")
sheet.save(sp)
print("对比条:", sp, "（从左到右：2% 25% 41% 63% 76% 92% 100%）")
