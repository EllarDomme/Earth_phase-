"""render_all.py —— 完全走自动路径重出 10 张（0 次豆包）

不给 --base：底图分档 + 亮度 + 镜像 全部由 compose_moon 自己决定。
本脚本只负责调用 + 最后打光 + 拼总览。
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = r"E:\DeskTop\地球"
OUT = r"E:\DeskTop\草稿"
sys.path.insert(0, HERE)
import lighting  # noqa: E402

CASES = [
    ("2009-06-21", 3.25), ("2008-10-26", 3.50), ("2004-11-08", 1.25),
    ("2002-10-01", 0.00), ("2021-06-18", 11.25), ("2021-06-30", 22.75),
    ("2005-01-01", 1.25), ("2009-03-14", 0.75), ("2024-02-21", 9.75),
    ("2021-06-25", 22.75),
]

rows = []
for date, utc in CASES:
    src = os.path.join(HERE, "v2", "_bak_uni_%s_地球相_2048.png" % date)
    if not os.path.exists(src):
        print("  缺素材:", date)
        continue
    mid = os.path.join(OUT, "_ra_%s.png" % date)
    r = subprocess.run([sys.executable, os.path.join(HERE, "compose_moon.py"), src, mid,
                        "--date", date, "--utc", str(utc), "--width", "1920",
                        "--earth-pct", "0.36", "--moon-gain", "0.65",
                        "--sky-target", "1,1,1", "--earth-gamma", "1.0",
                        "--earth-sat", "1.0"], capture_output=True, text=True)
    tier = [l.strip() for l in r.stdout.splitlines() if "月面：" in l]
    mir = [l.strip() for l in r.stdout.splitlines() if "底图选择" in l]
    lit = lighting.apply_lighting(Image.open(mid).convert("RGB"), date, utc, verbose=False)
    p = os.path.join(OUT, "定稿_%s.png" % date)
    lit.save(p)
    A = np.asarray(lit.convert("L")).astype(np.float32)
    t = A[1000:]
    t = t[t > 1]
    print("  %s  %s  %s  地形中位 %.0f"
          % (date, (tier[0].replace("月面：", "") if tier else "?"),
             (mir[0].split("，")[-1] if mir else ""), np.median(t)))
    rows.append((date, p))

# 按相位从低到高排
order = {"2021-06-25": 2, "2024-02-21": 9, "2009-03-14": 10, "2005-01-01": 24,
         "2021-06-30": 41, "2021-06-18": 47, "2002-10-01": 63, "2004-11-08": 76,
         "2008-10-26": 92, "2009-06-21": 96}
rows.sort(key=lambda r: order.get(r[0], 0))

S = (620, 413)
cols = 3
rn = (len(rows) + cols - 1) // cols
sheet = Image.new("RGB", (S[0] * cols + 8 * (cols - 1), S[1] * rn + 8 * (rn - 1)), (8, 8, 8))
f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 26)
for i, (date, p) in enumerate(rows):
    r_, c_ = divmod(i, cols)
    x, y = c_ * (S[0] + 8), r_ * (S[1] + 8)
    sheet.paste(Image.open(p).resize(S, Image.LANCZOS), (x, y))
    ImageDraw.Draw(sheet).text((x + 8, y + 6), "%d%%" % order[date],
                               font=f, fill=(150, 210, 255))
sp = os.path.join(OUT, "定稿_总览.png")
sheet.save(sp)
print("总览:", sp)
