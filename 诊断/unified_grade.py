"""unified_grade.py —— 统一用 gamma 处理月面（不再用模糊压平）

规则：
  太阳高度 h 决定两件事：① 阴影要多浅（gamma）② 整体多亮（scale）
    h > +20°  正午 : gamma 0.62（阴影压到最浅）+ 提亮 1.06
    +6~+20°   白天 : gamma 1.00（不动）+ 1.00
      0~+6°   落日 : gamma 0.85 + 亮度 1.0→0.25
      h < 0°  月夜 : gamma 0.80 + 亮度 0.22→0.18（越深夜越暗）
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
OUT = r"E:\DeskTop\草稿"
BASE = os.path.join(HERE, "素材", "moon_base_v2.png")
sys.path.insert(0, HERE)
import lighting  # noqa: E402

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


def sun_elev(kk):
    return 90 - np.degrees(np.arccos(np.clip(1 - 2 * kk, -1, 1)))


def params(h):
    if h > 20:
        return 0.62, 1.06, "正午：阴影压最浅 + 提亮"
    if h >= 6:
        return 1.00, 1.00, "白天：保持"
    if h >= 0:
        return 0.88, 1.0 - 0.75 * (1 - h / 6.0), "落日"
    t = min(1.0, -h / 60.0)
    return 0.80, 0.22 - 0.04 * t, "月夜"


CASES = [("2021-06-25", 22.75, 0.02), ("2021-06-30", 22.75, 0.41),
         ("2002-10-01", 0.00, 0.63), ("2008-10-26", 3.50, 0.92)]

rows = []
for date, utc, kk in CASES:
    h = sun_elev(kk)
    gamma, scale, tag = params(h)

    src = os.path.join(HERE, "v2", "_bak_uni_%s_地球相_2048.png" % date)
    mid = os.path.join(OUT, "_u_%s.png" % date)
    subprocess.run([sys.executable, os.path.join(HERE, "compose_moon.py"),
                    src, mid, "--base", BASE, "--date", date, "--utc", str(utc),
                    "--width", "1920", "--earth-pct", "0.36", "--moon-gain", "0.65",
                    "--sky-target", "1,1,1", "--earth-gamma", "1.0", "--earth-sat", "1.0"],
                   capture_output=True)

    im = Image.open(mid).convert("RGB")
    lit = lighting.apply_lighting(im, date, utc, verbose=False)
    A = np.asarray(lit).astype(np.float32)
    yy = np.arange(A.shape[0])[:, None]
    tm = (yy > hor[None, :] + 2)[..., None]

    # 只对地形做 gamma + 缩放
    x = np.clip(A / 255.0, 0, 1)
    graded = (x ** gamma) * 255.0 * scale
    if h < 0:
        graded = graded + 2.2
        graded[..., 0] *= 0.93
        graded[..., 2] *= 1.04
    out = np.where(tm, np.clip(graded, 0, 255), A)

    p = os.path.join(OUT, "统一_相位%02.0f.png" % (kk * 100))
    Image.fromarray(out.astype(np.uint8)).save(p)
    t = out[tm[..., 0]].mean()
    g = out[tm[..., 0]].mean(1)
    depth = np.percentile(g, 95) / max(np.percentile(g, 5), 1e-6)
    print("  %s  相位 %2.0f%%  太阳 %+6.1f°  gamma %.2f × %.2f  地形均 %5.1f  阴影深度 %.1f  %s"
          % (date, kk * 100, h, gamma, scale, t, depth, tag))
    rows.append(p)

S = (700, 467)
sheet = Image.new("RGB", (S[0] * len(rows) + 8 * (len(rows) - 1), S[1]), (8, 8, 8))
for i, p in enumerate(rows):
    sheet.paste(Image.open(p).resize(S, Image.LANCZOS), (i * (S[0] + 8), 0))
sp = os.path.join(OUT, "统一gamma_四相位.png")
sheet.save(sp)
print("对比条:", sp)
