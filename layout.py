"""layout.py —— 版面几何的唯一真相（所有脚本都从这里取）

以前 0.33 / 0.44 / 0.50 散落在 6 个文件里，
改一次参数就要挨个改，漏一个就错位（2026-11-07 踩过）。

2026-11-10 新增：地球尺寸两种模式
  artistic —— 占画宽 36%，艺术压缩（相当于 400mm 长焦的视觉效果）
  true     —— 真实角直径 1.9°（地球半径 6371 km / 地月距离 384400 km），
              按 40° 视场换算 = 4.75% 画宽 ≈ 91 px @1920
"""

import math

EARTH_CX = 0.50      # 地球圆心（画宽比例）
EARTH_CY = 0.31      # 地球圆心（画高比例）
EARTH_PCT = 0.36     # 地球直径占画宽（artistic 模式）
MASK_SHRINK = 0.985  # 贴图遮罩内收（防源图天空漏出）

HORIZON_Y = 761      # 月面地平线（像素，1280 高）
EARTH_GAP = 20       # 地球下缘与地平线的空隙（像素）

# ── 真实尺寸的物理量 ──
R_EARTH_KM = 6371.0
D_MOON_KM = 384400.0
EARTH_ANG_DEG = 2.0 * math.degrees(math.atan(R_EARTH_KM / D_MOON_KM))  # ≈ 1.899°
EARTH_FOV_DEG = 40.0                                                   # 画框视场（声明值）
EARTH_PCT_TRUE = EARTH_ANG_DEG / EARTH_FOV_DEG                          # ≈ 0.0475

EARTH_SIZES = {"artistic": EARTH_PCT, "true": EARTH_PCT_TRUE}


def earth_pct(mode="artistic", fov_deg=None):
    """按模式返回地球直径占画宽。true 模式可用 fov_deg 覆盖视场。"""
    m = (mode or "artistic").lower()
    if m in ("true", "real", "物理", "真实"):
        fov = float(fov_deg) if fov_deg else EARTH_FOV_DEG
        return EARTH_ANG_DEG / fov
    return EARTH_PCT


def disc_geom(W, H, pct=None, cx=None):
    """返回圆盘几何：(cx, cy, R)，单位像素。

    pct 给定时按该直径重算 cy，让地球下缘与地平线保持 EARTH_GAP。
    """
    _cx = (EARTH_CX if cx is None else cx) * W
    if pct is None or abs(pct - EARTH_PCT) < 1e-9:
        # 默认尺寸走旧路径，保证和 2026-11-09 之前的成品逐像素一致
        return _cx, EARTH_CY * H, EARTH_PCT * W / 2.0
    R = pct * W / 2.0
    # 地平线按画高比例换算（1280 设计稿 → 当前高）
    hz = HORIZON_Y * H / 1280.0
    gap = EARTH_GAP * H / 1280.0
    return _cx, hz - gap - R, R


def disc_mask_np(W, H, scale=1.0, pct=None, cx=None):
    """返回 bool 数组：True = 圆盘内（scale<1 时更小）。"""
    import numpy as np
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy, R = disc_geom(W, H, pct=pct, cx=cx)
    return np.hypot(xx - cx, yy - cy) <= R * scale
