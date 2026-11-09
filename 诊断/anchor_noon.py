"""anchor_noon.py —— 比较三种策略：受光最优 / 受光够好+贴近正午 / 旧的最居中"""
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


def cands(date):
    out = []
    for i in range(96):
        u = i * 0.25
        S, V = unit(*E.subsolar_point(date, u)), unit(*E.sublunar_point(date, u))
        c = unit(*CHINA)
        vis, lit = dot(c, V), dot(c, S)
        if vis > 0.15 and lit > 0.15:
            out.append(dict(utc=u, vis=vis, lit=lit, m=min(vis, lit),
                            ph=E.earth_phase(date, u),
                            dv=math.degrees(math.acos(max(-1, min(1, vis))))))
    return out


def near_noon(c):
    u = c["utc"]
    return min(abs(u - 12.0), 24 - abs(u - 12.0))


DATES = ["2006-04-05", "2005-01-01", "2024-02-21", "2021-06-30",
         "2002-10-01", "2009-06-21", "2013-06-15", "2023-02-25", "2026-11-01"]

print("%-12s %-24s %-24s %-24s" % ("日期", "A 受光最优", "D 受光≥0.35 且贴正午", "差值"))
for d in DATES:
    cs = cands(d)
    if not cs:
        print("%-12s 无候选" % d)
        continue
    a = max(cs, key=lambda c: (c["m"], -c["dv"]))
    d35 = [c for c in cs if c["m"] >= 0.35]
    dsel = min(d35, key=near_noon) if d35 else a
    print("%-12s %-24s %-24s %-24s"
          % (d,
             "%.2f/%.2f @%5.2fh %.0f%%" % (a["vis"], a["lit"], a["utc"], a["ph"]),
             "%.2f/%.2f @%5.2fh %.0f%%" % (dsel["vis"], dsel["lit"], dsel["utc"], dsel["ph"]),
             "受光 %+.2f  相位 %+.0f 点" % (dsel["lit"] - a["lit"], dsel["ph"] - a["ph"])))
