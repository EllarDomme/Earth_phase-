"""bug_sweep2.py —— 复核修好后的亮度曲线（与 compose_moon 里的逻辑一致）"""
import math

BASE_LUM = {"无影": 86.0, "短影": 52.0, "中影": 47.0, "长影": 43.0}
L_NIGHT, L_FLOOR = 18.5, 15.5


def pick(h):
    if h <= 0:
        L = L_NIGHT - 3.0 * min(1.0, -h / 60.0)
    else:
        L = 86.0 * (math.sin(math.radians(max(h, 0.5))) / math.sin(math.radians(60.0))) ** 0.7
        L = max(L, L_FLOOR)
    if h < 0:
        tier = "无影"
    else:
        ok = [n for n in BASE_LUM if BASE_LUM[n] >= L - 1e-6]
        tier = min(ok, key=lambda n: BASE_LUM[n]) if ok else "无影"
    g = max(0.05, min(1.0, L / BASE_LUM[tier]))
    return tier, g, L


print("=== 扫 h 全区间 ===")
prev = None
jumps = []
prev_base = None
for i in range(-180, 181):
    h = i * 0.5
    tier, g, L = pick(h)
    if prev is not None:
        dl = L - prev
        if dl > 0.6:
            jumps.append(("回跳", h - 0.5, prev, h, L))
        if abs(dl) > 10:
            jumps.append(("断崖", h - 0.5, prev, h, L))
    prev = L

for tag, h0, l0, h1, l1 in jumps[:15]:
    print("  ✗ %s  h %+5.1f(%.1f) → %+5.1f(%.1f)  Δ%+.1f" % (tag, h0, l0, h1, l1, l1 - l0))
if not jumps:
    print("  ✓ 无回跳、无断崖（Δ 全 ≤ 1.0）")

print()
print("=== h=0 前后 ===")
for h in (-6, -3, -1, -0.01, 0.0, 0.01, 1, 2, 3.4, 4.5, 5, 10.4, 21.5, 22, 31, 44.5, 45, 53, 60, 73.7):
    tier, g, L = pick(h)
    print("  h=%+6.2f  %-4s ×%.3f  目标亮度 %5.1f" % (h, tier, g, L))

print()
print("=== 实测日期对照 ===")
for name, h in (("2%", 73.7), ("9%", 55.1), ("10%", 53.1), ("24%", 31.3),
                ("41%", 10.7), ("47%", 3.9), ("63%", -15.1), ("92%", -57.1)):
    tier, g, L = pick(h)
    print("  %-4s h=%+6.1f  %-4s ×%.2f → %.1f" % (name, h, tier, g, L))
