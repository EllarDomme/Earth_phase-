"""azimuth_error2.py —— 修正版：镜像后底图光照 = 180°，误差按角距离算"""
import math
import sys

import numpy as np

sys.path.insert(0, r"E:\DeskTop\地球")
import ephem_hp as E  # noqa: E402

BASE_DEG = 0.0      # 原图：光从右来
MIRROR_DEG = 180.0  # 镜像后：光从左来


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


def adist(a, b):
    d = abs((a - b) % 360)
    return min(d, 360 - d)


CASES = [("2021-06-25", 22.75), ("2024-02-21", 9.75), ("2009-03-14", 0.75),
         ("2005-01-01", 1.25), ("2021-06-30", 22.75), ("2021-06-18", 11.25),
         ("2002-10-01", 0.00), ("2004-11-08", 1.25), ("2008-10-26", 3.50),
         ("2009-06-21", 3.25)]

print("%-12s %-8s %-7s %-7s %-7s %-7s" % ("日期", "亮面角", "原图误差", "镜像误差", "选用", "剩余误差"))
errs = []
for date, utc in CASES:
    s = sun_dir(date, utc)
    e0 = adist(s, BASE_DEG)
    e1 = adist(s, MIRROR_DEG)
    use = "镜像" if e1 < e0 else "原图"
    err = min(e0, e1)
    errs.append(err)
    print("%-12s %-8.0f° %-7.0f° %-7.0f° %-7s %-7.0f°" % (date, s, e0, e1, use, err))

print()
print("剩余误差：中位 %.0f°  最大 %.0f°  平均 %.0f°"
      % (np.median(errs), max(errs), np.mean(errs)))
print("理论上限 90°（只有两个朝向，间隔 180°）")
