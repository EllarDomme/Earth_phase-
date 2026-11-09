"""window_tradeoff.py —— 把 UTC 限制在 12:00±3h，看中国受光损失多少"""
import math
import sys

sys.path.insert(0, r"E:\DeskTop\地球")
import ephem_hp as E  # noqa: E402

CHINA = (35.0, 105.0)


def unit(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def dot(u, v):
    return sum(a * b for a, b in zip(u, v))


def score(date, utc):
    S, V = unit(*E.subsolar_point(date, utc)), unit(*E.sublunar_point(date, utc))
    c = unit(*CHINA)
    return dot(c, V), dot(c, S), E.earth_phase(date, utc)


DATES = ["2006-04-05", "2005-01-01", "2024-02-21", "2021-06-30",
         "2002-10-01", "2009-06-21", "2013-06-15", "2023-02-25"]

print("%-12s %-22s %-22s %-22s" % ("日期", "A 全局最佳", "B 12:00±3h", "C 旧选点±3h"))
for d in DATES:
    allc = []
    for i in range(96):
        u = i * 0.25
        vis, lit, ph = score(d, u)
        if vis > 0.15 and lit > 0.15:
            allc.append((min(vis, lit), u, vis, lit, ph))
    if not allc:
        print("%-12s 无候选" % d)
        continue
    a = max(allc)
    win = [c for c in allc if min(abs(c[1] - 12.0), 24 - abs(c[1] - 12.0)) <= 3]
    b = max(win) if win else None
    old = max(allc, key=lambda c: -c[1])  # 略：旧规则用最居中，这里仅示意
    def f(c):
        if not c:
            return "无"
        return "%.2f/%.2f @%.2fh(%.0f%%)" % (c[2], c[3], c[1], c[4])
    print("%-12s %-22s %-22s" % (d, f(a), f(b)))
