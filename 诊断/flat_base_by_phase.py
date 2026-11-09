"""flat_base_by_phase.py —— 先做"无影版底图"，再看各地相

无影化思路（低频/高频分离）：
  阴影是**大尺度**的暗区，细节纹理是**小尺度**的。
  ① 大半径模糊得到"反照率底子"（低频）
  ② 原图 − 底子 = 细节（高频）
  ③ 重建：底子 + 细节 × k（k 小 → 大尺度阴影被压掉，细纹还在）
这符合物理：月夜的光源是头顶 1.9° 的地球（大面光源），阴影本来就又短又软。
"""
import os

import numpy as np
from PIL import Image, ImageFilter

HERE = r"E:\DeskTop\地球"
BASE = os.path.join(HERE, "素材", "moon_base_v2.png")
OUT = r"E:\DeskTop\草稿"

A0 = np.asarray(Image.open(BASE).convert("RGB")).astype(np.float32)

# ① 低频（反照率底子）
low = np.asarray(Image.fromarray(np.clip(A0, 0, 255).astype(np.uint8))
                 .filter(ImageFilter.GaussianBlur(45))).astype(np.float32)
detail = A0 - low
flat = low + detail * 0.28
flat = np.clip(flat, 0, 255)
print("无影化：细节保留 28%%，原图动态范围 p95/p5=%.1f → 无影版 %.1f"
      % (np.percentile(A0[A0 > 3], 95) / np.percentile(A0[A0 > 3], 5),
         np.percentile(flat[flat > 3], 95) / np.percentile(flat[flat > 3], 5)))

Image.fromarray(flat.astype(np.uint8)).save(os.path.join(OUT, "无影底图.png"))


def sun_elev(k):
    return 90 - np.degrees(np.arccos(np.clip(1 - 2 * k, -1, 1)))


PHASES = [(0.02, "2%"), (0.25, "25%"), (0.41, "41%"), (0.63, "63%"), (0.92, "92%")]

for k, label in PHASES:
    h = sun_elev(k)
    if h > 20:                       # 正午：亮，平
        out = flat * 1.05
        tag = "正午：亮且平"
    elif h >= 6:                     # 过渡
        out = flat * (0.55 + 0.45 * (h - 6) / 14)
        tag = "过渡"
    elif h >= 0:                     # 落日
        g = 0.15 + (1.0 - 0.15) * (h / 6.0)
        out = flat * g
        tag = "增益 %.2f" % g
    elif h >= -6:
        g = 0.02 + (0.15 - 0.02) * ((h + 6) / 6.0)
        out = flat * g
        tag = "增益 %.3f" % g
    else:                            # 月夜
        t = min(1.0, (-6 - h) / 54.0)
        g = 0.02 * (1 - t) + 0.055 * t
        out = flat * g + 1.7
        out[..., 0] *= 0.92
        out[..., 2] *= 1.03
        tag = "月夜：增益 %.3f" % g
    out = np.clip(out, 0, 255)
    p = os.path.join(OUT, "无影_相位%s.png" % label)
    Image.fromarray(out.astype(np.uint8)).save(p)
    terr = out[900:, :]
    print("  %-5s 太阳 %+6.1f°  %-14s 地形均 %5.1f" % (label, h, tag, terr.mean()))

# 对比条（只看地形）
S = (700, 380)
crop_y = 860
tiles = [Image.open(os.path.join(OUT, "无影_相位%s.png" % l)).crop((0, crop_y, 1920, 1280)).resize(S, Image.LANCZOS)
         for _, l in PHASES]
sheet = Image.new("RGB", (S[0] * len(tiles) + 6 * (len(tiles) - 1), S[1]), (10, 10, 10))
for i, t in enumerate(tiles):
    sheet.paste(t, (i * (S[0] + 6), 0))
sp = os.path.join(OUT, "无影_各地相对比.png")
sheet.save(sp)
print("对比条:", sp, "（左→右：2% 25% 41% 63% 92%）")
