"""rerender_all.py —— 零额度：用现有地球素材按当前流水线重拼全部（不碰豆包）"""
import glob
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = r"E:\DeskTop\地球"
OUT = r"E:\DeskTop\草稿"
sys.path.insert(0, HERE)
import lighting  # noqa: E402

dates = []
for p in sorted(glob.glob(os.path.join(HERE, "v2", "_bak_uni_*_地球相_2048.png"))):
    base = os.path.basename(p)
    d = base.replace("_bak_uni_", "").replace("_地球相_2048.png", "")
    j = os.path.join(HERE, "v2", "_bak_uni_%s_地球相_2048.json" % d)
    utc = None
    phase = None
    if os.path.exists(j):
        try:
            meta = json.load(open(j, encoding="utf-8"))
            utc = meta.get("utc")
            phase = str(meta.get("phase", "")).replace("%", "")
            phase = float(phase) if phase else None
        except Exception:
            pass
    dates.append((d, utc, phase, p))

print("共 %d 个日期\n" % len(dates))
rows = []
for d, utc, phase, src in dates:
    if utc is None:
        print("  %s  缺 utc，跳过" % d)
        continue
    mid = os.path.join(OUT, "_rr_%s.png" % d)
    r = subprocess.run([sys.executable, os.path.join(HERE, "compose_moon.py"), src, mid,
                        "--date", d, "--utc", str(utc), "--width", "1920",
                        "--earth-pct", "0.36", "--moon-gain", "0.65",
                        "--sky-target", "1,1,1", "--earth-gamma", "1.0",
                        "--earth-sat", "1.0"], capture_output=True, text=True)
    info = [l.strip() for l in r.stdout.splitlines()
            if l.startswith(("月面：", "月面质感"))]
    lit = lighting.apply_lighting(Image.open(mid).convert("RGB"), d, utc, verbose=False)
    p = os.path.join(OUT, "优化_%s.png" % d)
    lit.save(p)
    t = np.asarray(lit.convert("L")).astype(np.float32)[1000:]
    t = t[t > 1]
    print("  %s  %-52s 地形中位 %3.0f" % (d, " | ".join(info)[:52], np.median(t)))
    rows.append((phase if phase is not None else 0, d, p))

rows.sort(key=lambda r: r[0])
S = (560, 373)
cols = 4
rn = (len(rows) + cols - 1) // cols
f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 24)
sheet = Image.new("RGB", (S[0] * cols + 8 * (cols - 1), (S[1] + 30) * rn + 8 * (rn - 1)),
                  (8, 8, 8))
d = ImageDraw.Draw(sheet)
for i, (ph, date, p) in enumerate(rows):
    r_, c_ = divmod(i, cols)
    x, y = c_ * (S[0] + 8), r_ * (S[1] + 38)
    sheet.paste(Image.open(p).resize(S, Image.LANCZOS), (x, y + 28))
    d.text((x + 6, y + 2), "%.0f%%  %s" % (ph, date), font=f, fill=(150, 210, 255))
sp = os.path.join(OUT, "优化_总览.png")
sheet.save(sp)
print("\n总览:", sp)
