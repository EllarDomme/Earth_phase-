"""which_base.py —— 反推每张成品的地形到底来自哪张底图"""
import glob
import json
import os

import numpy as np
from PIL import Image

OUT = r"E:\DeskTop\地球\成品"
BASES = r"E:\DeskTop\地球\素材"
BOX = (300, 900, 1500, 1180)      # 地形区域（避开球与天空）


def prep(im):
    a = np.asarray(im.convert("L").crop(BOX)).astype(np.float32)
    a = a - a.mean()
    s = a.std()
    return a / s if s > 1e-6 else a


refs = {}
for n in ("无影", "短影", "中影", "长影"):
    p = os.path.join(BASES, "moon_base_%s.png" % n)
    refs[n] = prep(Image.open(p))

print("%-12s %-6s %s" % ("日期", "相位", "最匹配的底图（相关系数）"))
for p in sorted(glob.glob(os.path.join(OUT, "*_月面_提升_1920x1280.png"))):
    d = os.path.basename(p).split("_")[0]
    j = os.path.join(r"E:\DeskTop\地球\v2", "_bak_uni_%s_地球相_2048.json" % d)
    ph = ""
    if os.path.exists(j):
        try:
            ph = str(json.load(open(j, encoding="utf-8")).get("phase", ""))
        except Exception:
            ph = ""
    a = prep(Image.open(p))
    scores = {n: float((a * r).mean()) for n, r in refs.items()}
    best = max(scores, key=scores.get)
    detail = "  ".join("%s %.3f" % (k, v) for k, v in scores.items())
    print("%-12s %-6s %-4s   %s" % (d, ph, best, detail))
