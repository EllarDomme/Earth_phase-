"""test_compose2.py —— 四档全用上：无影 / 短影 / 中影 / 长影

相位分区（按太阳高度推）：
  h > +37°   (相位 <20%)    → 无影
  +16~+37°   (20%~35%)      → 短影
  +6~+16°    (35%~45%)      → 中影
  -6~+6°     (45%~55%)      → 长影
  h < -6°    (>55%)         → 无影 + 压暗
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
    ("2008-10-26", 3.50, 0.92),
    ("2004-11-08", 1.25, 0.76),
    ("2002-10-01", 0.00, 0.63),
    ("2021-06-18", 11.25, 0.47),
    ("2021-06-30", 22.75, 0.41),
    ("2005-01-01", 1.25, 0.24),
    ("2009-03-14", 0.75, 0.10),
    ("2024-02-21", 9.75, 0.09),
    ("2021-06-25", 22.75, 0.02),
]


def sun_elev(k):
    return 90 - np.degrees(np.arccos(np.clip(1 - 2 * k, -1, 1)))


def plan(h):
    if h > 37:
        return "无影", 1.00, "正午"
    if h >= 16:
        return "短影", 1.00, "短影"
    if h >= 6:
        return "中影", 1.00, "中影"
    if h >= -6:
        return "长影", 1.00 - 0.25 * (1 - min(1, max(0, h) / 6)), "长影"
    t = min(1.0, -h / 60.0)
    return "无影", 0.22 - 0.04 * t, "月夜"


rows = []
for date, utc, k in CASES:
    h = sun_elev(k)
    bname, scale, tag = plan(h)
    base = os.path.join(AST, "moon_base_%s.png" % bname)

    src = os.path.join(HERE, "v2", "_bak_uni_%s_地球相_2048.png" % date)
    if not os.path.exists(src):
        print("  缺素材:", date)
        continue
    mid = os.path.join(OUT, "_t2_%s.png" % date)
    subprocess.run([sys.executable, os.path.join(HERE, "compose_moon.py"),
                    src, mid, "--base", base, "--date", date, "--utc", str(utc),
                    "--width", "1920", "--earth-pct", "0.36", "--moon-gain", "0.65",
                    "--sky-target", "1,1,1", "--earth-gamma", "1.0", "--earth-sat", "1.0"],
                   capture_output=True)

    lit = lighting.apply_lighting(Image.open(mid).convert("RGB"), date, utc, verbose=False)
    A = np.asarray(lit).astype(np.float32)

    B = np.asarray(Image.open(base).convert("L")).astype(np.float32)
    hz = np.full(1920, 1280, dtype=np.int32)
    for x in range(1920):
        idx = np.where(B[:, x] > 12)[0]
        hz[x] = int(idx[0]) if len(idx) else 1280
    kk = 21
    pd = np.pad(hz, (kk // 2, kk // 2), mode="edge")
    hz = np.array([pd[i:i + kk].min() for i in range(1920)], dtype=np.int32)
    tm = (np.arange(1280)[:, None] > hz[None, :] + 2)[..., None]

    graded = A * scale if scale != 1.0 else A
    if h < 0:
        graded = graded + 2.2
        graded[..., 0] *= 0.93
        graded[..., 2] *= 1.04
    out = np.where(tm, np.clip(graded, 0, 255), A)

    p = os.path.join(OUT, "试验_%s_%02.0f%%.png" % (date, k * 100))
    Image.fromarray(out.astype(np.uint8)).save(p)
    print("  %s  相位 %2.0f%%  太阳 %+6.1f°  底图 %s  ×%.2f  地形均 %5.1f"
          % (date, k * 100, h, bname, scale, out[tm[..., 0]].mean()))
    rows.append((k, p, bname))

rows.sort(key=lambda r: r[0])
S = (620, 413)
cols = 3
rn = (len(rows) + cols - 1) // cols
sheet = Image.new("RGB", (S[0] * cols + 8 * (cols - 1), S[1] * rn + 8 * (rn - 1)), (8, 8, 8))
for i, (_, p, _b) in enumerate(rows):
    r, c = divmod(i, cols)
    sheet.paste(Image.open(p).resize(S, Image.LANCZOS), (c * (S[0] + 8), r * (S[1] + 8)))
sp = os.path.join(OUT, "试验_总览.png")
sheet.save(sp)

from collections import Counter  # noqa: E402
print()
print("各底图使用次数:", dict(Counter(b for _, _, b in rows)))
print("总览:", sp)
