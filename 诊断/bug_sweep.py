"""bug_sweep.py —— 针对新加的自动分档做边界扫查"""
import math
import subprocess
import sys

PY = sys.executable

# 1) 边界值：把 compose 里的分档逻辑单独复现，扫全区间
BASE_H = {"无影": 60.0, "短影": 30.0, "中影": 15.0, "长影": 8.0}
BASE_LUM = {"无影": 86.0, "短影": 52.0, "中影": 47.0, "长影": 43.0}


def pick(h):
    if h < 0:
        t = min(1.0, -h / 60.0)
        return "无影", min(0.22, 0.22 - 0.04 * t)
    if h >= 45:
        n = "无影"
    elif h >= 22:
        n = "短影"
    elif h >= 5:
        n = "中影"
    else:
        n = "长影"
    s = (math.sin(math.radians(max(h, 0.5))) / math.sin(math.radians(BASE_H[n]))) ** 0.7
    return n, min(1.0, s)


print("=== 扫 h = -90 ~ +90，看亮度是否有回跳/断崖 ===")
prev = None
bad = []
for h in [x * 0.5 for x in range(-180, 181)]:
    n, s = pick(h)
    lum = s * BASE_LUM[n]
    if prev is not None:
        ph, pl, pn = prev
        if h < 0:
            # 月夜段：相位越大越暗，亮度应随 h 上升而上升（单调不降）
            if lum < pl - 0.5:
                bad.append(("月夜回跳", ph, pl, h, lum))
        else:
            if lum < pl - 0.5:
                bad.append(("白天回跳", ph, pl, h, lum))
        if abs(lum - pl) > 12:
            bad.append(("断崖 >12", ph, pl, h, lum))
    prev = (h, lum, n)

for tag, h0, l0, h1, l1 in bad[:20]:
    print("  ✗ %-10s h %+5.1f(%.1f) → %+5.1f(%.1f)   Δ%+.1f" % (tag, h0, l0, h1, l1, l1 - l0))
if not bad:
    print("  ✓ 未见回跳/断崖")

print()
print("=== h=0 附近细看（最容易出错的地方）===")
for h in (-3, -1.5, -0.5, -0.01, 0.0, 0.01, 0.5, 1, 2, 3.4):
    n, s = pick(h)
    print("  h=%+6.2f  %-4s ×%.3f  → 亮度 %5.1f" % (h, n, s, s * BASE_LUM[n]))
