"""all_phase_demo.py —— 用现有素材，按相位自动选底图 + 调月面，全部重拼

规则：
  h > +37°   → 无影 + gamma 0.62 ×1.06        (相位 < 20%)
  h +16~37°  → 中影 + gamma 0.95 ×1.00        (20%~35%)
  h 0~+16°   → 长影 + 不动                     (35%~50%)
  h < 0      → 无影 + gamma 0.80 ×0.22→0.18   (月夜)
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

CASES = [
    ("2009-06-21", 3.25, 0.96),
    ("2004-11-08", 1.25, 0.76),
    ("2002-10-01", 0.00, 0.63),
    ("2021-06-18", 11.25, 0.47),
    ("2021-06-30", 22.75, 0.41),
    ("2009-03-14", 0.75, 0.10),
    ("2024-02-21", 9.75, 0.09),
    ("2021-06-25", 22.75, 0.02),
]

BASES = {n: os.path.join(AST, "moon_base_%s.png" % n) for n in ("无影", "中影", "长影")}


def sun_elev(k):
    return 90 - np.degrees(np.arccos(np.clip(1 - 2 * k, -1, 1)))


_hor_cache = {}


def horizon(base):
    if base in _hor_cache:
        return _hor_cache[base]
    A = np.asarray(Image.open(base).convert("L")).astype(np.float32)
    H, W = A.shape
    hor = np.full(W, H, dtype=np.int32)
    for x in range(W):
        idx = np.where(A[:, x] > 12)[0]
        hor[x] = int(idx[0]) if len(idx) else H
    k = 21
    pad = np.pad(hor, (k // 2, k // 2), mode="edge")
    hor = np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)
    _hor_cache[base] = hor
    return hor


def plan(h):
    if h > 37:
        return "无影", 0.62, 1.06, "正午：极短影"
    if h >= 16:
        return "中影", 0.95, 1.00, "中影"
    if h >= 0:
        return "长影", 1.00, 1.00 - 0.35 * (1 - min(1, h / 6)), "长影"
    t = min(1.0, -h / 60.0)
    return "无影", 0.80, 0.22 - 0.04 * t, "月夜：压暗"


rows = []
for date, utc, k in CASES:
    h = sun_elev(k)
    bname, gamma, scale, tag = plan(h)
    base = BASES[bname]

    src = os.path.join(HERE, "v2", "_bak_uni_%s_地球相_2048.png" % date)
    mid = os.path.join(OUT, "_p_%s.png" % date)
    subprocess.run([sys.executable, os.path.join(HERE, "compose_moon.py"),
                    src, mid, "--base", base, "--date", date, "--utc", str(utc),
                    "--width", "1920", "--earth-pct", "0.36", "--moon-gain", "0.65",
                    "--sky-target", "1,1,1", "--earth-gamma", "1.0", "--earth-sat", "1.0"],
                   capture_output=True)

    im = Image.open(mid).convert("RGB")
    lit = lighting.apply_lighting(im, date, utc, verbose=False)
    A = np.asarray(lit).astype(np.float32)
    hor = horizon(base)
    yy = np.arange(A.shape[0])[:, None]
    tm = (yy > hor[None, :] + 2)[..., None]

    x = np.clip(A / 255.0, 0, 1)
    graded = (x ** gamma) * 255.0 * scale
    if h < 0:
        graded = graded + 2.2
        graded[..., 0] *= 0.93
        graded[..., 2] *= 1.04
    out = np.where(tm, np.clip(graded, 0, 255), A)

    p = os.path.join(OUT, "拼图_%s_%02.0f%%.png" % (date, k * 100))
    Image.fromarray(out.astype(np.uint8)).save(p)
    t = out[tm[..., 0]].mean()
    print("  %s  相位 %2.0f%%  太阳 %+6.1f°  用%s  gamma %.2f ×%.2f  地形均 %5.1f"
          % (date, k * 100, h, bname, gamma, scale, t))
    rows.append((k, p, bname))

# 3x3 拼图（按相位从低到高）
rows.sort(key=lambda r: r[0])
S = (620, 413)
cols, rowsn = 3, (len(rows) + 2) // 3
sheet = Image.new("RGB", (S[0] * cols + 8 * (cols - 1), S[1] * rowsn + 8 * (rowsn - 1)), (8, 8, 8))
for i, (_, p, _b) in enumerate(rows):
    r, c = divmod(i, cols)
    sheet.paste(Image.open(p).resize(S, Image.LANCZOS), (c * (S[0] + 8), r * (S[1] + 8)))
sp = os.path.join(OUT, "拼图_九张总览.png")
sheet.save(sp)
print("总览:", sp)
