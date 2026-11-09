"""base_phase_files.py —— 输出不同相位下的月面底图（单张，方便逐张看）"""
import os

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
BASE = os.path.join(HERE, "素材", "moon_base_v2.png")
OUT = r"E:\DeskTop\草稿"

PHASES = [(0.02, "2%"), (0.25, "25%"), (0.41, "41%"), (0.63, "63%"), (0.92, "92%")]


def sun_elev(k):
    return 90 - np.degrees(np.arccos(np.clip(1 - 2 * k, -1, 1)))


def grade(A, h):
    if h > 20:
        m = A.mean()
        return np.clip((m + (A - m) * 0.55) * 1.08, 0, 255), "正午：压对比+提亮"
    if h >= 6:
        return A, "保持"
    if h >= 0:
        g = 0.15 + (1.0 - 0.15) * (h / 6.0)
        return np.clip(A * g, 0, 255), "增益 %.2f" % g
    if h >= -6:
        g = 0.02 + (0.15 - 0.02) * ((h + 6) / 6.0)
        return np.clip(A * g, 0, 255), "增益 %.3f" % g
    t = min(1.0, (-6 - h) / 54.0)
    g = 0.02 * (1 - t) + 0.06 * t
    out = A * g + 1.8
    out[..., 0] *= 0.92
    out[..., 2] *= 1.03
    return np.clip(out, 0, 255), "月夜：增益 %.3f" % g


A0 = np.asarray(Image.open(BASE).convert("RGB")).astype(np.float32)
for k, label in PHASES:
    h = sun_elev(k)
    out, tag = grade(A0, h)
    p = os.path.join(OUT, "底图_相位%s.png" % label)
    Image.fromarray(out.astype(np.uint8)).save(p)
    print("  %-5s 太阳 %+6.1f°  %-16s → %s" % (label, h, tag, p))
