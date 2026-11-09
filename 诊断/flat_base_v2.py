"""flat_base_v2.py —— 生成干净的无影底图，并按相位组合出各档

规则：
  相位 < 30%（正午）→ 无影版 + 亮
  相位 35%~50%（低太阳）→ 原版（保留长影）
  相位 > 55%（月夜）→ 无影版 + 压暗（地球照是头顶大面光源，无硬影）
"""
import os

import numpy as np
from PIL import Image, ImageFilter

HERE = r"E:\DeskTop\地球"
BASE = os.path.join(HERE, "素材", "moon_base_v2.png")
OUT = r"E:\DeskTop\草稿"

A0 = np.asarray(Image.open(BASE).convert("RGB")).astype(np.float32)
H, W = A0.shape[:2]
L = A0.mean(2)

# ① 地平线（从底图取）
hor = np.full(W, H, dtype=np.int32)
for x in range(W):
    idx = np.where(L[:, x] > 12)[0]
    hor[x] = int(idx[0]) if len(idx) else H
k = 21
pad = np.pad(hor, (k // 2, k // 2), mode="edge")
hor = np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)
terr = (np.arange(H)[:, None] > hor[None, :] + 2)[..., None]

# ② 无影化（只在盘内做，天空保持纯黑）
low = np.asarray(Image.fromarray(np.clip(A0, 0, 255).astype(np.uint8))
                 .filter(ImageFilter.GaussianBlur(45))).astype(np.float32)
detail = A0 - low
flat = np.where(terr, np.clip(low + detail * 0.28, 0, 255), 0.0)
Image.fromarray(flat.astype(np.uint8)).save(os.path.join(OUT, "无影底图.png"))

def rng(a):
    v = a[a > 3]
    return np.percentile(v, 95) / max(np.percentile(v, 5), 1e-6)

print("动态范围：原版 %.1f → 无影版 %.1f" % (rng(A0), rng(flat)))


def sun_elev(kk):
    return 90 - np.degrees(np.arccos(np.clip(1 - 2 * kk, -1, 1)))


def build(kk):
    h = sun_elev(kk)
    if h > 20:                      # 正午：无影版，亮
        out = flat * 1.02
        src, tag = "无影版", "正午：亮且平"
    elif h >= 6:                    # 低太阳：原版，保留长影
        out = A0 * 1.0
        src, tag = "原版", "低太阳：长影"
    elif h >= 0:
        g = 0.15 + 0.85 * (h / 6.0)
        out = A0 * g
        src, tag = "原版", "落日：增益 %.2f" % g
    elif h >= -6:
        g = 0.02 + 0.13 * ((h + 6) / 6.0)
        out = flat * g
        src, tag = "无影版", "暮光：增益 %.3f" % g
    else:                           # 月夜：无影版，压到很暗
        t = min(1.0, (-6 - h) / 54.0)
        g = 0.02 * (1 - t) + 0.055 * t
        out = flat * g + 1.7
        out[..., 0] *= 0.92
        out[..., 2] *= 1.03
        src, tag = "无影版", "月夜：增益 %.3f" % g
    out = np.where(terr, np.clip(out, 0, 255), A0 * 0)   # 天空纯黑
    return out, h, src, tag


for kk, label in [(0.02, "2%"), (0.25, "25%"), (0.41, "41%"),
                  (0.63, "63%"), (0.76, "76%"), (0.92, "92%")]:
    out, h, src, tag = build(kk)
    p = os.path.join(OUT, "月面_相位%s.png" % label)
    Image.fromarray(out.astype(np.uint8)).save(p)
    print("  %-5s 太阳 %+6.1f°  用%s  %-16s 地形均 %5.1f"
          % (label, h, src, tag, out[900:].mean()))
print("输出目录:", OUT)
