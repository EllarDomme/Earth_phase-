"""layout.py —— 版面几何的唯一真相（所有脚本都从这里取）

以前 0.33 / 0.44 / 0.50 散落在 6 个文件里，
改一次参数就要挨个改，漏一个就错位（2026-11-07 踩过）。
"""

EARTH_CX = 0.50      # 地球圆心（画宽比例）
EARTH_CY = 0.31      # 地球圆心（画高比例）
EARTH_PCT = 0.36     # 地球直径占画宽
MASK_SHRINK = 0.985  # 贴图遮罩内收（防源图天空漏出）


def disc_geom(W, H):
    """返回圆盘几何：(cx, cy, R)，单位像素。"""
    return EARTH_CX * W, EARTH_CY * H, EARTH_PCT * W / 2.0


def disc_mask_np(W, H, scale=1.0):
    """返回 bool 数组：True = 圆盘内（scale<1 时更小）。"""
    import numpy as np
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy, R = disc_geom(W, H)
    return np.hypot(xx - cx, yy - cy) <= R * scale
