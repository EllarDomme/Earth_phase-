"""china_pareto.py —— 同一天里“居中 vs 受光”的取舍空间"""
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


date = sys.argv[1] if len(sys.argv) > 1 else "2006-04-05"
rows = []
for i in range(96):
    utc = i * 0.25
    S, V = unit(*E.subsolar_point(date, utc)), unit(*E.sublunar_point(date, utc))
    c = unit(*CHINA)
    vis, lit = dot(c, V), dot(c, S)
    dv = math.degrees(math.acos(max(-1.0, min(1.0, vis))))
    l_ok = sum(1 for la, lo in SAMPLES if dot(unit(la, lo), S) > 0)
    rows.append((utc, vis, lit, dv, l_ok))

print("日期 %s  ——  可行候选（vis>0.15 且 lit>0.15）" % date)
ok = [r for r in rows if r[1] > 0.15 and r[2] > 0.15]
print("  共 %d 个候选" % len(ok))
print()
print("%-7s %-8s %-8s %-10s %-8s" % ("UTC", "可见", "受光", "离中心角度", "受光采样"))
print("--- 现行策略：取最居中 ---")
best_c = min(ok, key=lambda r: r[3])
print("%-7.2f %-8.2f %-8.2f %-10.0f° %-8d" % (best_c[0], best_c[1], best_c[2], best_c[3], best_c[4]))
print("--- 若改成：受光最高的前 3 ---")
for r in sorted(ok, key=lambda r: -r[2])[:3]:
    print("%-7.2f %-8.2f %-8.2f %-10.0f° %-8d" % (r[0], r[1], r[2], r[3], r[4]))
print("--- 若改成：max min(可见,受光) 的前 3 ---")
for r in sorted(ok, key=lambda r: -min(r[1], r[2]))[:3]:
    print("%-7.2f %-8.2f %-8.2f %-10.0f° %-8d" % (r[0], r[1], r[2], r[3], r[4]))
