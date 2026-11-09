"""china_rule.py —— 硬规则：只要有亮部，中国就必须在亮部里

判据（以中国中心 + 10 个采样点计）：
  可见：cos(中国, 视线) > 0        （在球正面）
  受光：cos(中国, 太阳) > 0        （在亮面）
评分：先让"可见"和"受光"里较小的那个尽量大（两者都不勉强），
      分数相同再比"离画面中心更近"（更居中）。

2026-11-09 修正：原来只按"离中心最近"排序，会选出受光 0.16~0.20 的方案
（中国确实在亮部，但贴着晨昏线，很暗）。实测 2006-04-05 从
"可见 0.98 / 受光 0.18" 改善到 "可见 0.69 / 受光 0.71"。
"""
import math
import sys

sys.path.insert(0, r"E:\DeskTop\地球")
import ephem_hp as E

CHINA = (35.0, 105.0)
SAMPLES = [
    (39.9, 116.4), (31.2, 121.5), (23.1, 113.3), (30.6, 104.1),
    (45.8, 126.6), (43.8, 87.6), (36.1, 103.8), (25.0, 102.7),
    (29.6, 91.1), (41.8, 123.4),
]


def unit(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def dot(u, v):
    return sum(a * b for a, b in zip(u, v))


def evaluate(date, utc):
    sl = E.subsolar_point(date, utc)
    ml = E.sublunar_point(date, utc)
    S, V = unit(*sl), unit(*ml)
    c = unit(*CHINA)
    vis = dot(c, V)
    lit = dot(c, S)
    # 全境：可见与受光都要 > 0（至少一半采样点满足，避免只露一个角）
    v_ok = sum(1 for la, lo in SAMPLES if dot(unit(la, lo), V) > 0)
    l_ok = sum(1 for la, lo in SAMPLES if dot(unit(la, lo), S) > 0)
    ph = E.earth_phase(date, utc)
    dv = math.degrees(math.acos(max(-1.0, min(1.0, vis))))
    return dict(utc=utc, sl=sl, ml=ml, vis=vis, lit=lit, dv=dv,
                v_ok=v_ok, l_ok=l_ok, phase=ph)


def best(date):
    rows = [evaluate(date, i * 0.25 % 24) for i in range(0, 96)]
    # 规则：中国可见且受光；在此前提下让中国【尽量靠近画面中心】（看得清）
    ok = [r for r in rows if r["vis"] > 0.15 and r["lit"] > 0.15]
    if ok:
        # 主键：min(可见, 受光) 越大越好（保留一位小数做并列，避免浮点抖动）
        # 次键：离画面中心越近越好
        ok.sort(key=lambda r: (-round(min(r["vis"], r["lit"]), 1), r["dv"]))
        return ok[0], rows, "满足：中国在亮部且不勉强"
    # 退一步：只要中国受光（哪怕贴边）
    ok2 = [r for r in rows if r["lit"] > 0.05 and r["v_ok"] >= 3]
    if ok2:
        ok2.sort(key=lambda r: -r["lit"])
        return ok2[0], rows, "勉强：中国受光但靠近球缘"
    return None, rows, "该日期中国无法同时可见且受光（类似满月，整盘可能全暗）"


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else "2006-08-01"
    r, rows, msg = best(date)
    print("日期 %s → %s" % (date, msg))
    if r:
        print("  UTC %.2f" % r["utc"])
        print("  月下点 %.1fN %.1fE（视角）" % (r["ml"][0], r["ml"][1]))
        print("  太阳直下点 %.1fN %.1fE" % (r["sl"][0], r["sl"][1]))
        print("  中国：可见 %.2f（>0 即在正面）  受光 %.2f（>0 即在亮面）" % (r["vis"], r["lit"]))
        print("  采样点：可见 %d/10，受光 %d/10" % (r["v_ok"], r["l_ok"]))
        print("  相位 %.0f%%" % r["phase"])
