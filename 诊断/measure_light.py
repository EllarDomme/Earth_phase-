"""measure_light.py —— 从"最大环形山"反推光照方向

思路：环形山内壁的亮点 = 正对太阳的那一侧。
      取大坑区域，找最亮的那一簇像素相对坑心的方向 → 太阳方向。
"""
import numpy as np
from PIL import Image, ImageFilter

AST = r"E:\DeskTop\地球\素材"
B = np.asarray(Image.open(AST + r"\moon_base_中影.png").convert("L")).astype(np.float32)

# 大坑大致范围（从网格图读出来的）
X0, X1, Y0, Y1 = 330, 1010, 1060, 1280
sub = B[Y0:Y1, X0:X1]
h, w = sub.shape
yy, xx = np.mgrid[0:h, 0:w]
cx, cy = w * 0.45, h * 0.55          # 坑心估计
r = np.hypot((xx - cx) / (w * 0.42), (yy - cy) / (h * 0.55))
inner = (r > 0.45) & (r < 0.95)      # 只取内壁环带

bright = sub > np.percentile(sub[inner], 92)
by = (yy[bright & inner] - cy).mean()
bx = (xx[bright & inner] - cx).mean()
n = np.hypot(bx, by) + 1e-6
print("大坑内壁最亮处相对坑心: dx=%+.1f dy=%+.1f  → 归一化 (%+.2f, %+.2f)"
      % (bx, by, bx / n, by / n))
print("太阳方向（屏幕坐标，y 向下）: (%+.2f, %+.2f)" % (bx / n, by / n))
print("即：光来自 %s%s" % ("右下" if bx > 0 and by > 0 else
                         "左上" if bx < 0 and by < 0 else "混合"),
      "角 %.0f°" % np.degrees(np.arctan2(by, bx)))

# 顺便量一下大坑的明暗对比（给合成阴影定强度）
vals = sub[inner]
print("内壁亮度: p10=%.0f p50=%.0f p90=%.0f  对比 p90/p10=%.1f"
      % tuple(list(np.percentile(vals, [10, 50, 90])) + [np.percentile(vals, 90) / max(np.percentile(vals, 10), 1)]))
