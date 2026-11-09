"""compare_four_bases.py —— 同一张地球，四张底图各拼一张，直接比出差异"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = r"E:\DeskTop\地球"
AST = os.path.join(HERE, "素材")
OUT = r"E:\DeskTop\草稿"
sys.path.insert(0, HERE)
import lighting  # noqa: E402

DATE, UTC = "2021-06-30", 22.75
BASES = [("无影", "moon_base_无影.png"), ("短影", "moon_base_短影.png"),
         ("中影", "moon_base_中影.png"), ("长影", "moon_base_长影.png")]

tiles = []
for name, fn in BASES:
    base = os.path.join(AST, fn)
    mid = os.path.join(OUT, "_cb_%s.png" % name)
    subprocess.run([sys.executable, os.path.join(HERE, "compose_moon.py"),
                    os.path.join(HERE, "v2", "_bak_uni_%s_地球相_2048.png" % DATE),
                    mid, "--base", base, "--date", DATE, "--utc", str(UTC),
                    "--width", "1920", "--earth-pct", "0.36", "--moon-gain", "0.65",
                    "--sky-target", "1,1,1", "--earth-gamma", "1.0", "--earth-sat", "1.0"],
                   capture_output=True)
    lit = lighting.apply_lighting(Image.open(mid).convert("RGB"), DATE, UTC, verbose=False)
    p = os.path.join(OUT, "四底图_%s.png" % name)
    lit.save(p)
    A = np.asarray(lit.convert("L")).astype(np.float32)
    t = A[900:]
    t = t[t > 3]
    print("  %-4s 地形中位 %3.0f  影子占比 %4.1f%%" % (name, np.median(t),
          float((t < np.median(t) * 0.85).mean() * 100)))
    tiles.append((name, p))

f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 30)
S = (700, 467)
c = Image.new("RGB", (S[0] * 2 + 12, (S[1] + 46) * 2 + 8), (12, 12, 12))
d = ImageDraw.Draw(c)
for i, (name, p) in enumerate(tiles):
    r, cc = divmod(i, 2)
    x, y = cc * (S[0] + 12), r * (S[1] + 46) + 40
    c.paste(Image.open(p).resize(S, Image.LANCZOS), (x, y))
    d.text((x + 8, y - 36), name, font=f, fill=(160, 220, 255))
sp = os.path.join(OUT, "四底图对比.png")
c.save(sp)
print("对比图:", sp)
