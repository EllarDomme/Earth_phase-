"""check_tier.py —— 每个日期用的档位 + 底图实际阴影强度"""
import glob
import json
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
import ephem_hp as E  # noqa: E402

V2 = r"E:\DeskTop\地球\v2"
OUT = r"E:\DeskTop\地球\成品"


def tier_of(h):
    if h < 0:
        return "无影(压暗)"
    if h >= 45:
        return "无影"
    if h >= 22:
        return "短影"
    if h >= 5:
        return "中影"
    return "长影"


print("%-12s %-6s %-8s %-10s %-8s" % ("日期", "相位", "太阳高度", "应有档位", "月面中位"))
for p in sorted(glob.glob(os.path.join(OUT, "*_月面_提升_1920x1280.png"))):
    d = os.path.basename(p).split("_")[0]
    j = os.path.join(V2, "_bak_uni_%s_地球相_2048.json" % d)
    if not os.path.exists(j):
        continue
    meta = json.load(open(j, encoding="utf-8"))
    ph = float(str(meta.get("phase", "")).replace("%", "") or 0)
    utc = meta.get("utc")
    if utc is None:
        continue
    k = ph / 100.0
    h = 90 - math.degrees(math.acos(max(-1, min(1, 1 - 2 * k))))
    A = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    t = A[761:]
    t = t[t > 1]
    med = np.median(t) if t.size else 0
    print("%-12s %-6.0f %-8.1f %-10s %-8.0f" % (d, ph, h, tier_of(h), med))

print("\n=== 四张底图的实际阴影强度（高频标准差，越大阴影越重）===")
for name in ("无影", "短影", "中影", "长影"):
    p = os.path.join(r"E:\DeskTop\地球\素材", "moon_base_%s.png" % name)
    if not os.path.exists(p):
        print("  %-4s 缺文件" % name)
        continue
    A = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    t = A[1000:]
    t = t[t > 1]
    if t.size < 1000:
        continue
    # 一阶差分反映局部明暗落差
    gy, gx = np.gradient(A[1000:])
    g = np.hypot(gx, gy)
    print("  %-4s 中位 %3.0f  梯度均值 %.1f  p95 %.1f  局部对比 %.1f"
          % (name, np.median(t), g.mean(), np.percentile(g, 95),
             np.percentile(t, 95) - np.percentile(t, 5)))
