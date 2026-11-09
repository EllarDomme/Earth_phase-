"""china_compare.py —— 旧排序 vs 新排序：选出的 UTC / 中国 / 相位"""
import math
import sys

sys.path.insert(0, r"E:\DeskTop\地球")
import ephem_hp as E  # noqa: E402

CHINA = (35.0, 105.0)
SAMPLES = [(39.9, 116.4), (31.2, 121.5), (23.1, 113.3), (30.6, 104.1),
           (45.8, 126.6), (43.8, 87.6), (36.1, 103.8), (25.0, 102.7),
           (29.6, 91.1), (41.8, 123.4)]


def unit(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def dot(u, v):
    return sum(a * b for a, b in zip(u, v))


def rows_of(date):
    out = []
    for i in range(96):
        utc = i * 0.25
        S, V = unit(*E.subsolar_point(date, utc)), unit(*E.sublunar_point(date, utc))
        c = unit(*CHINA)
        vis, lit = dot(c, V), dot(c, S)
        dv = math.degrees(math.acos(max(-1.0, min(1.0, vis))))
        l_ok = sum(1 for la, lo in SAMPLES if dot(unit(la, lo), S) > 0)
        v_ok = sum(1 for la, lo in SAMPLES if dot(unit(la, lo), V) > 0)
        out.append(dict(utc=utc, vis=vis, lit=lit, dv=dv, l_ok=l_ok, v_ok=v_ok,
                        phase=E.earth_phase(date, utc)))
    return out


def pick(rows, mode):
    ok = [r for r in rows if r["vis"] > 0.15 and r["lit"] > 0.15]
    if not ok:
        return None
    if mode == "old":
        ok.sort(key=lambda r: r["dv"])
    else:
        ok.sort(key=lambda r: (-round(min(r["vis"], r["lit"]), 1), r["dv"]))
    return ok[0]


DATES = ["2006-04-05", "2005-01-01", "2024-02-21", "2021-06-30",
         "2021-06-25", "2009-06-21", "2002-10-01"]

print("%-12s %-26s %-26s" % ("日期", "旧：最居中", "新：兼顾"))
print("%-12s %-8s %-6s %-6s %-4s %-8s %-6s %-6s %-4s"
      % ("", "UTC/相位", "可见", "受光", "距心", "UTC/相位", "可见", "受光", "距心"))
for d in DATES:
    rs = rows_of(d)
    o, n = pick(rs, "old"), pick(rs, "new")
    def fmt(r):
        if not r:
            return "无候选", "", "", ""
        return ("%5.2f/%3.0f%%" % (r["utc"], r["phase"] * 100), "%.2f" % r["vis"],
                "%.2f" % r["lit"], "%.0f°" % r["dv"])
    fo, fn = fmt(o), fmt(n)
    print("%-12s %-8s %-6s %-6s %-4s %-8s %-6s %-6s %-4s"
          % (d, fo[0], fo[1], fo[2], fo[3], fn[0], fn[1], fn[2], fn[3]))
