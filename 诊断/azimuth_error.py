"""azimuth_error.py —— 每个日期，月面光照方向能被镜像修正到什么程度"""
import math
import sys

import numpy as np

sys.path.insert(0, r"E:\DeskTop\地球")
import ephem_hp as E  # noqa: E402

HERE = r"E:\DeskTop\地球"
MOON_LIGHT_DEG = 0.0     # 底图的光照方向（实测：光从右来）


def unit(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return np.array([math.cos(la) * math.cos(lo),
                     math.cos(la) * math.sin(lo), math.sin(la)])


def sun_dir(date, utc):
    lat0, lon0 = E.sublunar_point(date, utc)
    S = unit(*E.subsolar_point(date, utc))
    V = unit(lat0, lon0)
    ex = np.cross([0, 0, 1.0], V)
    ex /= np.linalg.norm(ex)
    ey = np.cross(V, ex)
    return math.degrees(math.atan2(float(S @ ey), float(S @ ex))) % 360


CASES = [("2021-06-25", 22.75), ("2024-02-21", 9.75), ("2009-03-14", 0.75),
         ("2005-01-01", 1.25), ("2021-06-30", 22.75), ("2021-06-18", 11.25),
         ("2002-10-01", 0.00), ("2004-11-08", 1.25), ("2008-10-26", 3.50),
         ("2009-06-21", 3.25)]

print("%-12s %-9s %-9s %-9s %-9s %-8s" % ("日期", "亮面角", "选用的", "误差", "另一选项", "判定"))
worst = 0
for date, utc in CASES:
    s = sun_dir(date, utc)
    d = abs(s - MOON_LIGHT_DEG) % 360
    d = min(d, 360 - d)
    mirror = d > 90
    used_err = (360 - d) if mirror else d       # 镜像后底图光照转过 180°
    other_err = d if mirror else (360 - d)
    worst = max(worst, min(used_err, other_err))
    print("%-12s %-9.0f° %-9s %-9.0f° %-9.0f° %s"
          % (date, s, "镜像" if mirror else "原图", used_err, other_err,
             "✓" if used_err <= 45 else ("△" if used_err <= 90 else "✗")))

print()
print("最坏误差（无论选哪张）：%.0f° —— 因为只有「原图 / 水平镜像」两种，相差 180°" % worst)
print("理论上限：任何方向都能把误差压到 ≤90°")
