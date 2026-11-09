"""final_phase_demo.py —— 改进版：无影底图 + 按相位调月面，输出完整成品对比

改进点：
  ① 无影化：更大的模糊半径、保留更多细节（35%），避免"塑料感"
  ② 夜间：用 gamma 抬中间调，而不是简单的线性乘法，保留一点层次
  ③ 完整合成（含地球），直接看成品效果
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = r"E:\DeskTop\地球"
OUT = r"E:\DeskTop\草稿"
BASE = os.path.join(HERE, "素材", "moon_base_v2.png")
sys.path.insert(0, HERE)
import lighting  # noqa: E402

# ── ① 无影底图（改进版）
A0 = np.asarray(Image.open(BASE).convert("RGB")).astype(np.float32)
H, W = A0.shape[:2]
L0 = A0.mean(2)
hor = np.full(W, H, dtype=np.int32)
for x in range(W):
    idx = np.where(L0[:, x] > 12)[0]
    hor[x] = int(idx[0]) if len(idx) else H
k = 21
pad = np.pad(hor, (k // 2, k // 2), mode="edge")
hor = np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)
terr = (np.arange(H)[:, None] > hor[None, :] + 2)[..., None]

low = np.asarray(Image.fromarray(A0.astype(np.uint8))
                 .filter(ImageFilter.GaussianBlur(55))).astype(np.float32)
detail = A0 - low
flat = np.where(terr, np.clip(low + detail * 0.35, 0, 255), 0.0)
FLAT = os.path.join(OUT, "_flat_base.png")
Image.fromarray(flat.astype(np.uint8)).save(FLAT)


def rng(a):
    v = a[a > 3]
    return np.percentile(v, 95) / max(np.percentile(v, 5), 1e-6)


print("无影化：动态范围 %.1f → %.1f" % (rng(A0), rng(flat)))


def sun_elev(kk):
    return 90 - np.degrees(np.arccos(np.clip(1 - 2 * kk, -1, 1)))


CASES = [
    ("2021-06-25", 22.75, 0.02),
    ("2021-06-30", 22.75, 0.41),
    ("2002-10-01", 0.00, 0.63),
    ("2008-10-26", 3.50, 0.92),
]

rows = []
for date, utc, kk in CASES:
    h = sun_elev(kk)
    night = h < 0
    base = FLAT if (h > 20 or night) else BASE

    src = os.path.join(HERE, "v2", "_bak_uni_%s_地球相_2048.png" % date)
    mid = os.path.join(OUT, "_cmp_%s.png" % date)
    subprocess.run([sys.executable, os.path.join(HERE, "compose_moon.py"),
                    src, mid, "--base", base, "--date", date, "--utc", str(utc),
                    "--width", "1920", "--earth-pct", "0.36", "--moon-gain", "0.65",
                    "--sky-target", "1,1,1", "--earth-gamma", "1.0", "--earth-sat", "1.0"],
                   capture_output=True)

    im = Image.open(mid).convert("RGB")
    lit = lighting.apply_lighting(im, date, utc, verbose=False)
    A = np.asarray(lit).astype(np.float32)
    yy = np.arange(A.shape[0])[:, None]
    tm = (yy > hor[None, :] + 2)[..., None]

    if h > 20:                        # 正午
        g, tag = 1.0, "正午(无影版)"
        out = A
    elif h >= 6:                      # 低太阳
        g, tag = 1.0, "低太阳(原版长影)"
        out = A
    elif h >= 0:
        g = 0.15 + 0.85 * (h / 6.0)
        tag = "落日 %.2f" % g
        out = np.where(tm, A * g, A)
    else:                             # 月夜：无影版 + 0.22 + gamma 抬暗部
        g = 0.22
        t = min(1.0, (-h) / 60.0)
        gg = 0.22 - 0.04 * t          # 越深夜越暗一点点（0.22→0.18）
        out = np.where(tm, (A / 255.0) ** 0.92 * 255.0 * gg + 2.5, A)
        out[..., 0] *= 0.93
        out[..., 2] *= 1.04
        tag = "月夜 %.2f" % gg

    out = np.clip(out, 0, 255)
    p = os.path.join(OUT, "成品_相位%02.0f.png" % (kk * 100))
    Image.fromarray(out.astype(np.uint8)).save(p)
    t = out[tm[..., 0]].mean()
    print("  %s  相位 %2.0f%%  太阳 %+6.1f°  %-16s 地形均 %5.1f"
          % (date, kk * 100, h, tag, t))
    rows.append((kk, p, tag))

S = (700, 467)
sheet = Image.new("RGB", (S[0] * len(rows) + 8 * (len(rows) - 1), S[1]), (8, 8, 8))
for i, (_, p, _t) in enumerate(rows):
    sheet.paste(Image.open(p).resize(S, Image.LANCZOS), (i * (S[0] + 8), 0))
sp = os.path.join(OUT, "成品四相位对比.png")
sheet.save(sp)
print("对比条:", sp, "（左→右：2% / 41% / 63% / 92%）")
