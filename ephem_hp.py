"""ephem_hp.py —— 高精度日月位置（Meeus《天文算法》第 25/47 章）

用途：算月下点、太阳星下点、地球相位。
精度：月球黄经/黄纬约 10 角秒（0.003°），太阳约 0.01°。
对比：原先的简化公式（L' + 6.289 sin M）误差可达 0.5°。

用法：
    from ephem_hp import sublunar_point, subsolar_point, earth_phase
    lat, lon, phase = sublunar_point("2020-04-05", 4.0)
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

RAD = math.pi / 180.0

# ── 月球周期项（Meeus 表 47.A / 47.B）────────────────────────────────
# (D, M, M', F, Σl 系数, Σr 系数)   单位 1e-6 度 / 1e-3 km
_TERMS_LON = [
    (0, 0, 1, 0, 6288774, -20905355), (2, 0, -1, 0, 1274027, -3699111),
    (2, 0, 0, 0, 658314, -2955968),   (0, 0, 2, 0, 213618, -569925),
    (0, 1, 0, 0, -185116, 48888),     (0, 0, 0, 2, -114332, -3149),
    (2, 0, -2, 0, 58793, 246158),     (2, -1, -1, 0, 57066, -152138),
    (2, 0, 1, 0, 53322, -170733),     (2, -1, 0, 0, 45758, -204586),
    (0, 1, -1, 0, -40923, -129620),   (1, 0, 0, 0, -34720, 108743),
    (0, 1, 1, 0, -30383, 104755),     (2, 0, 0, -2, 15327, 10321),
    (0, 0, 1, 2, -12528, 0),          (0, 0, 1, -2, 10980, 79661),
    (4, 0, -1, 0, 10675, -34782),     (0, 0, 3, 0, 10034, -23210),
    (4, 0, -2, 0, 8548, -21636),      (2, 1, -1, 0, -7888, 24208),
    (2, 1, 0, 0, -6766, 30824),       (1, 0, -1, 0, -5163, -8379),
    (1, 1, 0, 0, 4987, -16675),       (2, -1, 1, 0, 4036, -12831),
    (2, 0, 2, 0, 3994, -10445),       (4, 0, 0, 0, 3861, -11650),
    (2, 0, -3, 0, 3665, 14403),       (0, 1, -2, 0, -2689, -7003),
    (2, 0, -1, 2, -2602, 0),          (2, -1, -2, 0, 2390, 10056),
    (1, 0, 1, 0, -2348, 6322),        (2, -2, 0, 0, 2236, -9884),
    (0, 1, 2, 0, -2120, 5751),        (0, 2, 0, 0, -2069, 0),
    (2, -2, -1, 0, 2048, -4950),      (2, 0, 1, -2, -1773, 4130),
    (2, 0, 0, 2, -1595, 0),           (4, -1, -1, 0, 1215, -3958),
    (0, 0, 2, 2, -1110, 0),           (3, 0, -1, 0, -892, 3258),
    (2, 1, 1, 0, -810, 2616),         (4, -1, -2, 0, 759, -1897),
    (0, 2, -1, 0, -713, -2117),       (2, 2, -1, 0, -700, 2354),
    (2, 1, -2, 0, 691, 0),            (2, -1, 0, -2, 596, 0),
    (4, 0, 1, 0, 549, -1423),         (0, 0, 4, 0, 537, -1117),
    (4, -1, 0, 0, 520, -1571),        (1, 0, -2, 0, -487, -1739),
    (2, 1, 0, -2, -399, 0),           (0, 0, 2, -2, -381, -4421),
    (1, 1, 1, 0, 351, 0),             (3, 0, -2, 0, -340, 0),
    (4, 0, -3, 0, 330, 0),            (2, -1, 2, 0, 327, 0),
    (0, 2, 1, 0, -323, 1165),         (1, 1, -1, 0, 299, 0),
    (2, 0, 3, 0, 294, 0),             (2, 0, -1, -2, 0, 8752),
]

_TERMS_LAT = [
    (0, 0, 0, 1, 5128122), (0, 0, 1, 1, 280602), (0, 0, 1, -1, 277693),
    (2, 0, 0, -1, 173237), (2, 0, -1, 1, 55413), (2, 0, -1, -1, 46271),
    (2, 0, 0, 1, 32573),   (0, 0, 2, 1, 17198),  (2, 0, 1, -1, 9266),
    (0, 0, 2, -1, 8822),   (2, -1, 0, -1, 8216), (2, 0, -2, -1, 4324),
    (2, 0, 1, 1, 4200),    (2, 1, 0, -1, -3359), (2, -1, -1, 1, 2463),
    (2, -1, 0, 1, 2211),   (2, -1, -1, -1, 2065), (0, 1, -1, -1, -1870),
    (4, 0, -1, -1, 1828),  (0, 1, 0, 1, -1794),  (0, 0, 0, 3, -1749),
    (0, 1, -1, 1, -1565),  (1, 0, 0, 1, -1491),  (0, 1, 1, 1, -1475),
    (0, 1, 1, -1, -1410),  (0, 1, 0, -1, -1344), (1, 0, 0, -1, -1335),
    (0, 0, 3, 0, 1107),    (4, 0, 0, -1, 1021),  (4, 0, -1, 1, 833),
]

_J2000 = datetime(2000, 1, 1, 12, 0)


def julian_day(dt: datetime) -> float:
    return 2451545.0 + (dt - _J2000).total_seconds() / 86400.0


def _norm(x: float) -> float:
    return x % 360.0


def _obliquity(T: float) -> float:
    return 23.439291 - 0.0130042 * T - 1.64e-7 * T ** 2 + 5.04e-7 * T ** 3


def moon_ecliptic(dt: datetime):
    """返回 (λ, β, Δ_km)。Meeus 第 47 章。"""
    jd = julian_day(dt)
    T = (jd - 2451545.0) / 36525.0
    Lp = (218.3164477 + 481267.88123421 * T - 0.0015786 * T ** 2
          + T ** 3 / 538841 - T ** 4 / 65194000)
    D = (297.8501921 + 445267.1114034 * T - 0.0018819 * T ** 2
         + T ** 3 / 545868 - T ** 4 / 113065000)
    M = (357.5291092 + 35999.0502909 * T - 0.0001536 * T ** 2 + T ** 3 / 24490000)
    Mp = (134.9633964 + 477198.8675055 * T + 0.0087414 * T ** 2
          + T ** 3 / 69699 - T ** 4 / 14712000)
    F = (93.2720950 + 483202.0175233 * T - 0.0036539 * T ** 2
         - T ** 3 / 3526000 + T ** 4 / 863310000)
    A1 = 119.75 + 131.849 * T
    A2 = 53.09 + 479264.290 * T
    A3 = 313.45 + 481266.484 * T
    E = 1 - 0.002516 * T - 0.0000074 * T ** 2

    sl = sr = sb = 0.0
    for d, m, mp, f, cl, cr in _TERMS_LON:
        arg = (d * D + m * M + mp * Mp + f * F) * RAD
        e = E ** abs(m)
        sl += cl * e * math.sin(arg)
        sr += cr * e * math.cos(arg)
    for d, m, mp, f, cb in _TERMS_LAT:
        arg = (d * D + m * M + mp * Mp + f * F) * RAD
        sb += cb * (E ** abs(m)) * math.sin(arg)

    sl += (3958 * math.sin(A1 * RAD) + 1962 * math.sin((Lp - F) * RAD)
           + 318 * math.sin(A2 * RAD))
    sb += (-2235 * math.sin(Lp * RAD) + 382 * math.sin(A3 * RAD)
           + 175 * math.sin((A1 - F) * RAD) + 175 * math.sin((A1 + F) * RAD)
           + 127 * math.sin((Lp - Mp) * RAD) - 115 * math.sin((Lp + Mp) * RAD))

    lam = _norm(Lp + sl / 1e6)
    bet = sb / 1e6
    dist = 385000.56 + sr / 1000.0
    return lam, bet, dist


def sun_ecliptic(dt: datetime):
    """返回太阳 (λ, β≈0)。Meeus 第 25 章（低精度版，误差 <0.01°）。"""
    jd = julian_day(dt)
    T = (jd - 2451545.0) / 36525.0
    L0 = _norm(280.46646 + 36000.76983 * T + 0.0003032 * T ** 2)
    M = _norm(357.52911 + 35999.05029 * T - 0.0001537 * T ** 2)
    C = ((1.914602 - 0.004817 * T - 0.000014 * T ** 2) * math.sin(M * RAD)
         + (0.019993 - 0.000101 * T) * math.sin(2 * M * RAD)
         + 0.000289 * math.sin(3 * M * RAD))
    return _norm(L0 + C), 0.0


def _ecl_to_eq(lam, bet, T):
    eps = _obliquity(T) * RAD
    l, b = lam * RAD, bet * RAD
    ra = math.atan2(math.sin(l) * math.cos(eps) - math.tan(b) * math.sin(eps),
                    math.cos(l))
    dec = math.asin(math.sin(b) * math.cos(eps) +
                    math.cos(b) * math.sin(eps) * math.sin(l))
    return _norm(math.degrees(ra)), math.degrees(dec)


def _gmst(dt: datetime) -> float:
    d = julian_day(dt) - 2451545.0
    return _norm(280.46061837 + 360.98564736629 * d)


def _subpoint(dt: datetime, lam, bet):
    T = (julian_day(dt) - 2451545.0) / 36525.0
    ra, dec = _ecl_to_eq(lam, bet, T)
    lon = _norm(ra - _gmst(dt) + 180) - 180
    return dec, lon


def sublunar_point(date_str: str, utc_hour: float):
    """(纬度, 经度) —— 月亮正下方那一点。"""
    dt = datetime.fromisoformat(date_str) + timedelta(hours=utc_hour)
    lam, bet, _ = moon_ecliptic(dt)
    return _subpoint(dt, lam, bet)


def subsolar_point(date_str: str, utc_hour: float):
    dt = datetime.fromisoformat(date_str) + timedelta(hours=utc_hour)
    lam, bet = sun_ecliptic(dt)
    return _subpoint(dt, lam, bet)


def earth_phase(date_str: str, utc_hour: float) -> float:
    """从月球看地球的被照亮百分比。"""
    mlat, mlon = sublunar_point(date_str, utc_hour)
    slat, slon = subsolar_point(date_str, utc_hour)
    c = (math.sin(mlat * RAD) * math.sin(slat * RAD)
         + math.cos(mlat * RAD) * math.cos(slat * RAD) * math.cos((mlon - slon) * RAD))
    ang = math.degrees(math.acos(max(-1.0, min(1.0, c))))
    return 100.0 * (1 + math.cos(ang * RAD)) / 2


if __name__ == "__main__":
    for d, h in (("2020-04-05", 4.0), ("2019-05-01", 4.0)):
        la, lo = sublunar_point(d, h)
        sla, slo = subsolar_point(d, h)
        print("%s %04.1f UTC" % (d, h))
        print("  月下点 %7.2f  %8.2f   太阳星下点 %6.2f %8.2f" % (la, lo, sla, slo))
        print("  地球相位 %.2f%%" % earth_phase(d, h))
