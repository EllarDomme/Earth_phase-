"""phase_vs_sun.py —— 地相 vs 月面太阳高度：检验"满地 + 长阴影"是否自洽

关键几何：
  观察点在月面（子地球点），地球在头顶；
  太阳在月面天空里绕行，与地球的夹角 = 地球相位角。
  · 地球满相 → 太阳在地球【反方向】→ 太阳在地平线下 → 该地是月夜
  · 地球半相 → 太阳与地球夹角 90° → 太阳正好在地平线 → 长阴影
  · 地球新相 → 太阳与地球同方向 → 正午
"""
import sys

import numpy as np

sys.path.insert(0, r"E:\DeskTop\地球")
import lighting

CASES = [
    ("2009-06-21", 3.25),
    ("2004-11-08", 1.25),
    ("2002-10-01", 0.0),
    ("2021-06-25", 22.75),
]

print("%-12s %-8s %-10s %-10s %s" % ("日期", "地相", "中心cosi", "太阳高度", "月面该是"))
for d, utc in CASES:
    cosi, z, rr = lighting.cosi_map(d, utc, 1920, 1280)
    H, W = cosi.shape
    c = cosi[H // 2, W // 2]                    # 子地球点
    elev = np.degrees(np.arcsin(np.clip(c, -1, 1)))   # 太阳高度角
    # 地球相位的受照比例 ≈ (1 + cos(相位角))/2，而相位角 = 180° - 太阳高度
    frac = (1 - c) / 2 * 100
    if elev > 25:
        what = "白天（短影或几乎无影）"
    elif elev > 0:
        what = "低太阳（长影）"
    else:
        what = "月夜（前景全黑）"
    print("%-12s %5.0f%% %9.2f %9.1f°  %s" % (d, frac, c, elev, what))
