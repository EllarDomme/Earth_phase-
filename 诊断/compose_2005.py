"""compose_2005_short.py —— 24% 相位用「短影」底图重拼（0 次豆包）

pipeline 用的是默认底图（长影），按相位 24% 应该用短影。
这里把同一张清洗好的地球换成短影底图，再打光，做对比。
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

DATE, UTC = "2005-01-01", 1.25
SRC = os.path.join(HERE, "v2", "_bak_uni_%s_地球相_2048.png" % DATE)

results = []
for name in ("短影", "中影", "长影"):
    base = os.path.join(AST, "moon_base_%s.png" % name)
    mid = os.path.join(OUT, "_2005_%s.png" % name)
    subprocess.run([sys.executable, os.path.join(HERE, "compose_moon.py"),
                    SRC, mid, "--base", base, "--date", DATE, "--utc", str(UTC),
                    "--width", "1920", "--earth-pct", "0.36", "--moon-gain", "0.65",
                    "--sky-target", "1,1,1", "--earth-gamma", "1.0", "--earth-sat", "1.0"],
                   capture_output=True)
    lit = lighting.apply_lighting(Image.open(mid).convert("RGB"), DATE, UTC, verbose=False)
    p = os.path.join(OUT, "2005-01-01_%s.png" % name)
    lit.save(p)
    A = np.asarray(lit.convert("L")).astype(np.float32)
    t = A[900:]
    t = t[t > 3]
    print("  %-4s 地形中位 %3.0f  影子占比 %4.1f%%" % (name, np.median(t),
          float((t < np.median(t) * 0.85).mean() * 100)))
    results.append((name, p))

from PIL import ImageDraw, ImageFont  # noqa: E402
f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 30)
S = (760, 507)
c = Image.new("RGB", (S[0] * 3 + 16, S[1] + 46), (12, 12, 12))
d = ImageDraw.Draw(c)
for i, (name, p) in enumerate(results):
    x = i * (S[0] + 8)
    c.paste(Image.open(p).resize(S, Image.LANCZOS), (x, 40))
    d.text((x + 8, 6), name, font=f, fill=(160, 220, 255))
sp = os.path.join(OUT, "2005-01-01_三底图.png")
c.save(sp)
print("对比:", sp)
