"""verify_render.py —— 实际合成+打光，量真实亮度，和模型目标对比"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
sys.path.insert(0, HERE)
import lighting  # noqa: E402

CASES = [("2021-06-25", 22.75, 86.0), ("2009-03-14", 0.75, 81.3),
         ("2005-01-01", 1.25, 60.1), ("2021-06-30", 22.75, 29.3),
         ("2021-06-18", 11.25, 18.5), ("2002-10-01", 0.00, 17.7),
         ("2009-06-21", 3.25, 15.5)]

print("%-12s %-8s %-8s %-8s %-8s" % ("日期", "模型目标", "实际均值", "偏差", "判定"))
for date, utc, target in CASES:
    src = os.path.join(HERE, "v2", "_bak_uni_%s_地球相_2048.png" % date)
    mid = os.path.join(r"E:\DeskTop\草稿", "_vr_%s.png" % date)
    r = subprocess.run([sys.executable, os.path.join(HERE, "compose_moon.py"), src, mid,
                        "--date", date, "--utc", str(utc), "--width", "1920",
                        "--earth-pct", "0.36", "--moon-gain", "0.65",
                        "--sky-target", "1,1,1", "--earth-gamma", "1.0",
                        "--earth-sat", "1.0"], capture_output=True, text=True)
    tier_line = [l for l in r.stdout.splitlines() if "目标亮度" in l]
    lit = lighting.apply_lighting(Image.open(mid).convert("RGB"), date, utc, verbose=False)
    A = np.asarray(lit).astype(np.float32)
    # 只算地形（地平线以下、非地球）
    B = np.asarray(Image.open(mid).convert("L")).astype(np.float32)
    t = A[1000:].mean(2)
    t = t[t > 1]
    mb = float(np.median(t))
    dev = mb - target
    ok = "✓" if abs(dev) <= 6 else "⚠"
    print("%-12s %-8.1f %-8.1f %+-8.1f %-8s %s" % (date, target, mb, dev, ok,
                                                   (tier_line[0].strip() if tier_line else "")))
