"""recompose_all.py —— 用 v2 系底图（v2 / 无影）重拼全部日期

统一地貌：所有相位都基于 v2 这片地形，避免换相位时地面跳变。
  < 20%   正午  → 无影（已提亮） × 1.00
  20~35%  中太阳 → v2 + gamma 0.85
  35~50%  低太阳 → v2 × 1.00
  > 55%   月夜  → 无影 × 0.18~0.22（压暗）
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
AST = os.path.join(HERE, "素材")
OUT = r"E:\DeskTop\草稿"
sys.path.insert(0, HERE)
import lighting  # noqa: E402

V2 = os.path.join(AST, "moon_base_v2.png")
NONE = os.path.join(AST, "moon_base_无影.png")

CASES = [
    ("2009-06-21", 3.25, 0.96),
    ("2008-10-26", 3.50, 0.92),
    ("2004-11-08", 1.25, 0.76),
    ("2002-10-01", 0.00, 0.63),
    ("2021-06-18", 11.25, 0.47),
    ("2021-06-30", 22.75, 0.41),
    ("2009-03-14", 0.75, 0.10),
    ("2024-02-21", 9.75, 0.09),
    ("2021-06-25", 22.75, 0.02),
]


def sun_elev(k):
    return 90 - np.degrees(np.arccos(np.clip(1 - 2 * k, -1, 1)))


def plan(h):
    if h > 37:
        return NONE, 1.00, 1.00, "正午：无影"
    if h >= 16:
        return V2, 0.85, 1.00, "中太阳：浅影"
    if h >= 0:
        return V2, 1.00, 1.00 - 0.35 * (1 - min(1, h / 6)), "低太阳：长影"
    t = min(1.0, -h / 60.0)
    return NONE, 1.00, 0.22 - 0.04 * t, "月夜：压暗"


rows = []
for date, utc, k in CASES:
    h = sun_elev(k)
    base, gamma, scale, tag = plan(h)

    src = os.path.join(HERE, "v2", "_bak_uni_%s_地球相_2048.png" % date)
    mid = os.path.join(OUT, "_r_%s.png" % date)
    subprocess.run([sys.executable, os.path.join(HERE, "compose_moon.py"),
                    src, mid, "--base", base, "--date", date, "--utc", str(utc),
                    "--width", "1920", "--earth-pct", "0.36", "--moon-gain", "0.65",
                    "--sky-target", "1,1,1", "--earth-gamma", "1.0", "--earth-sat", "1.0"],
                   capture_output=True)

    lit = lighting.apply_lighting(Image.open(mid).convert("RGB"), date, utc, verbose=False)
    A = np.asarray(lit).astype(np.float32)

    # 地形 = 非纯黑（地球圆盘之外的地面）
    L = A.mean(2)
    x = np.clip(A / 255.0, 0, 1)
    graded = (x ** gamma) * 255.0 * scale
    if h < 0:
        graded = graded + 2.2
        graded[..., 0] *= 0.93
        graded[..., 2] *= 1.04

    # 只对"地平线以下"生效：用 v2 的轮廓
    B = np.asarray(Image.open(V2).convert("L")).astype(np.float32)
    hz = np.full(1920, 1280, dtype=np.int32)
    for xx in range(1920):
        idx = np.where(B[:, xx] > 12)[0]
        hz[xx] = int(idx[0]) if len(idx) else 1280
    kk = 21
    pd = np.pad(hz, (kk // 2, kk // 2), mode="edge")
    hz = np.array([pd[i:i + kk].min() for i in range(1920)], dtype=np.int32)
    yy = np.arange(1280)[:, None]
    tm = (yy > hz[None, :] + 2)[..., None]

    out = np.where(tm, np.clip(graded, 0, 255), A)
    p = os.path.join(OUT, "v2拼_%s_%02.0f%%.png" % (date, k * 100))
    Image.fromarray(out.astype(np.uint8)).save(p)
    print("  %s  相位 %2.0f%%  太阳 %+6.1f°  %-12s  ×%.2f  地形均 %5.1f"
          % (date, k * 100, h, tag, scale, out[tm[..., 0]].mean()))
    rows.append((k, p))

rows.sort(key=lambda r: r[0])
S = (620, 413)
cols = 3
rn = (len(rows) + cols - 1) // cols
sheet = Image.new("RGB", (S[0] * cols + 8 * (cols - 1), S[1] * rn + 8 * (rn - 1)), (8, 8, 8))
for i, (_, p) in enumerate(rows):
    r, c = divmod(i, cols)
    sheet.paste(Image.open(p).resize(S, Image.LANCZOS), (c * (S[0] + 8), r * (S[1] + 8)))
sp = os.path.join(OUT, "v2拼_九张总览.png")
sheet.save(sp)
print("总览:", sp)
