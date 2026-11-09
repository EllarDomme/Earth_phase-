"""contact_sheet.py —— 用当前成品重拼 12 张总览（含相位与月面层次标注）"""
import glob
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = r"E:\DeskTop\地球\成品"
V2 = r"E:\DeskTop\地球\v2"
rows = []
for p in sorted(glob.glob(os.path.join(OUT, "*_月面_提升_1920x1280.png"))):
    d = os.path.basename(p).split("_")[0]
    if d.startswith("_") or d.startswith("20") is False:
        continue
    j = os.path.join(V2, "_bak_uni_%s_地球相_2048.json" % d)
    ph = None
    if os.path.exists(j):
        try:
            ph = float(str(json.load(open(j, encoding="utf-8")).get("phase", "")).replace("%", ""))
        except Exception:
            ph = None
    if ph is None:
        continue
    A = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    t = A[761:]
    t = t[t > 1]
    rng = int(np.percentile(t, 95) - np.percentile(t, 5)) if t.size else 0
    med = int(np.median(t)) if t.size else 0
    rows.append((ph, d, p, med, rng))

rows.sort(key=lambda r: r[0])
S = (520, 347)
cols = 4
rn = (len(rows) + cols - 1) // cols
f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 22)
fs = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 17)
sheet = Image.new("RGB", (S[0] * cols + 8 * (cols - 1), (S[1] + 42) * rn + 8 * (rn - 1)),
                  (8, 8, 8))
d = ImageDraw.Draw(sheet)
for i, (ph, date, p, med, rng) in enumerate(rows):
    r_, c_ = divmod(i, cols)
    x, y = c_ * (S[0] + 8), r_ * (S[1] + 50)
    sheet.paste(Image.open(p).convert("RGB").resize(S, Image.LANCZOS), (x, y + 34))
    d.text((x + 6, y + 2), "%.0f%%  %s" % (ph, date), font=f, fill=(150, 210, 255))
    d.text((x + 6, y + 30), "月面 中位 %d  层次 %d 级" % (med, rng), font=fs, fill=(120, 190, 140))

sp = r"E:\DeskTop\草稿\成品总览_12张.png"
sheet.save(sp)
print("总览已生成：", sp)
print()
print("%-6s %-12s %-8s %-8s" % ("相位", "日期", "中位", "层次"))
for ph, date, p, med, rng in rows:
    print("%-6.0f %-12s %-8d %-8d" % (ph, date, med, rng))
