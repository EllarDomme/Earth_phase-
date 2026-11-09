"""phase_night.py —— 地球相位 → 月面太阳高度 → 月面是白天/黄昏/黑夜"""
import numpy as np

def sun_elev(k):
    """k = 地球受照比例(0~1)，返回子地球点的太阳高度角（度）"""
    cos_theta = 1 - 2 * k        # θ = 地球与太阳在天上的夹角
    theta = np.degrees(np.arccos(np.clip(cos_theta, -1, 1)))
    return 90 - theta

print("=== 相位 → 月面太阳高度 ===")
print("%-8s %-10s %-10s %s" % ("地球相位", "日地夹角", "太阳高度", "月面状态"))
for k in [0.0, 0.1, 0.2, 0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8, 0.9, 1.0]:
    th = np.degrees(np.arccos(np.clip(1 - 2 * k, -1, 1)))
    h = 90 - th
    if h > 30:
        s = "白天，短影"
    elif h > 3:
        s = "白天，长影"
    elif h > -1:
        s = "太阳贴地平线"
    elif h > -6:
        s = "暮光将尽，地面很暗"
    elif h > -20:
        s = "几乎全黑（只剩地球照）"
    else:
        s = "全黑，只有地球照"
    print("%-8.0f%% %-10.0f° %-10.1f° %s" % (k * 100, th, h, s))

print()
print("=== 亮度量级（相对太阳直射）===")
for h in (30, 10, 3, 0.5, 0, -5, -20):
    if h >= 0:
        rel = np.sin(np.radians(max(h, 0.01)))
        txt = "太阳照度 = 直射的 %.3f" % rel
    else:
        rel = 0.0
        txt = "无直射阳光"
    print("  太阳高度 %+5.1f° → %s" % (h, txt))

print()
print("=== 关键分界 ===")
for name, h_lim in (("太阳落到地平线下", 0.0), ("完全无直射（几乎全黑）", -6.0),
                    ("深度黑夜", -20.0)):
    # 解 90 - arccos(1-2k) = h_lim  → k
    cos_t = np.cos(np.radians(90 - h_lim))
    k = (1 - cos_t) / 2
    print("  %-22s 相位 ≥ %.0f%%" % (name, k * 100))
