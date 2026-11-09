"""find_line.py —— 定位那条细暗线的列位置，并判断来自底图还是合成"""
import numpy as np
from PIL import Image, ImageFilter

POST = r"E:\DeskTop\地球\成品\2006-04-05_月面_提升_1920x1280.png"
PRE = r"E:\DeskTop\地球\v2\_bak_uni_2006-04-05_月面_提升_1920x1280.png"
DISC = r"E:\DeskTop\地球\v2\_bak_uni_2006-04-05_地球相_2048.png"


def line_profile(path, y0, y1, x0, x1, tag):
    A = np.asarray(Image.open(path).convert("L")).astype(np.float32)
    band = A[y0:y1, x0:x1]
    col = band.mean(0)
    # 去掉缓趋势（大窗口中值），得到局部起伏
    trend = np.median(np.stack([np.roll(col, k) for k in range(-25, 26, 5)]), axis=0)
    res = col - trend
    idx = int(np.argmin(res))
    lo = res[max(0, idx - 1)]
    hi = res[min(len(res) - 1, idx + 1)]
    print("%-10s 暗线 x≈%d  深度 %.2f  邻列 %.2f/%.2f"
          % (tag, x0 + idx, res[idx], lo, hi))
    return x0 + idx, res


print("=== 成品海报（打光后）===")
xl, _ = line_profile(POST, 80, 250, 960, 1030, "成品")
print("=== 打光前海报 ===")
xb, _ = line_profile(PRE, 80, 250, 960, 1030, "打光前")
print()
print("=== 底图（1536 圆盘图）里的同一位置 ===")
# 海报里地球直径 691 → 底图 1536，比例 691/1536
cx_p, cy_p, R_p = 960, 397, 346
cx_d, cy_d, R_d = 768, 768, 768
sx = (xl - (cx_p - R_p)) / (2 * R_p)
d_x = int((cx_d - R_d) + sx * 2 * R_d)
A = np.asarray(Image.open(DISC).convert("L")).astype(np.float32)
band = A[400:1100, max(0, d_x - 40):d_x + 40]
col = band.mean(0)
trend = np.median(np.stack([np.roll(col, k) for k in range(-25, 26, 5)]), axis=0)
res = col - trend
i = int(np.argmin(res))
print("  对应底图列 x≈%d  深度 %.2f（该带内最深 %.2f）"
      % (max(0, d_x - 40) + i, res[i], res.min()))
