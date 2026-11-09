"""bug_sweep3.py —— 终版复核：单调性 + 连续性 + 四档都在用"""
import math

BASE_LUM = {"无影": 86.0, "短影": 52.0, "中影": 47.0, "长影": 43.0}
L_NIGHT, L_FLOOR = 18.5, 18.5


def pick(h):
    if h <= 0:
        L = L_NIGHT - 3.0 * min(1.0, -h / 60.0)
    else:
        L = 86.0 * (math.sin(math.radians(max(h, 0.5))) / math.sin(math.radians(60.0))) ** 0.7
        L = max(L, L_FLOOR)
    if h < 0:
        tier = "无影"
    elif h >= 45:
        tier = "无影"
    elif h >= 22:
        tier = "短影"
    elif h >= 5:
        tier = "中影"
    else:
        tier = "长影"
    cap = 1.0 if tier == "无影" else 1.30
    g = max(0.05, min(cap, L / BASE_LUM[tier]))
    rendered = g * BASE_LUM[tier]
    return tier, g, L, rendered


print("=== 单调性 & 连续性（h 从 -90 扫到 +90）===")
prev = None
bad = []
for i in range(-180, 181):
    h = i * 0.5
    tier, g, L, r = pick(h)
    if prev is not None:
        ph, pr = prev
        droop = pr - r
        if droop > 0.6:
            bad.append(("回跳(变暗)", ph, pr, h, r))
        if abs(r - pr) > 12:
            bad.append(("断崖", ph, pr, h, r))
    prev = (h, r)

for tag, h0, r0, h1, r1 in bad[:12]:
    print("  ✗ %-10s h %+5.1f(%.1f) → %+5.1f(%.1f)  Δ%+.1f" % (tag, h0, r0, h1, r1, r1 - r0))
if not bad:
    print("  ✓ 全程单调不回跳，无 >12 的断崖")

print()
print("=== 关键点 ===")
for h in (-60, -15.1, -6, -1, 0.0, 0.01, 3.9, 5, 10.7, 22, 31.3, 45, 53, 60, 73.7, 90):
    tier, g, L, r = pick(h)
    print("  h=%+6.2f  %-4s ×%.2f  目标 %5.1f  实际 %5.1f" % (h, tier, g, L, r))

print()
print("=== 实有日期 ===")
rows = [("2%", 73.7), ("9%", 55.1), ("10%", 53.1), ("24%", 31.3),
        ("41%", 10.7), ("47%", 3.9), ("63%", -15.1), ("76%", -31.3),
        ("92%", -57.1), ("96%", -66.9)]
used = set()
prevr = None
for name, h in rows:
    tier, g, L, r = pick(h)
    used.add(tier)
    flag = "" if prevr is None or r <= prevr + 0.01 else "  ← 比上一张小相位的更亮！"
    print("  %-4s h=%+6.1f  %-4s ×%.2f → %5.1f%s" % (name, h, tier, g, r, flag))
    prevr = r
print("  用到的底图:", "、".join(sorted(used)), "（共 %d 张）" % len(used))
