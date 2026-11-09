"""ridge_scan.py —— 自动找盘内的“细暗线”（连续负向脊）"""
import numpy as np
from PIL import Image, ImageFilter

A = np.asarray(Image.open(r"E:\DeskTop\地球\成品\2006-04-05_月面_提升_1920x1280.png")
               .convert("L")).astype(np.float32)
H, W = A.shape
med = np.asarray(Image.fromarray(A.astype(np.uint8))
                 .filter(ImageFilter.MedianFilter(9))).astype(np.float32)
hp = A - med                      # 高频：正=亮细节，负=暗细节

# 只看地球盘内
cx, cy, R = 960, 397, 346
yy, xx = np.mgrid[0:H, 0:W]
disc = np.hypot(xx - cx, yy - cy) < R * 0.96

# 找"宽度约 2~4px、连续长度较长"的负向脊：沿行/列统计
neg = (hp < -6) & disc
print("盘内负向高频像素占比: %.2f%%" % (100.0 * neg.sum() / max(disc.sum(), 1)))

# 按列统计每条垂直线的负像素连续段长度
best = []
for x in range(int(cx - R), int(cx + R)):
    col = neg[:, x]
    run = 0
    mx = 0
    for v in col:
        if v:
            run += 1
            mx = max(mx, run)
        else:
            run = 0
    if mx >= 25:
        best.append((x, mx))
best.sort(key=lambda t: -t[1])
print("竖直线性暗脊（长度≥25px）前 10：", best[:10])

# 按行
bestr = []
for y in range(int(cy - R), int(cy + R)):
    rowm = neg[y, :]
    run = 0
    mx = 0
    for v in rowm:
        if v:
            run += 1
            mx = max(mx, run)
        else:
            run = 0
    if mx >= 25:
        bestr.append((y, mx))
bestr.sort(key=lambda t: -t[1])
print("水平线性暗脊前 10：", bestr[:10])
print()
print("结论：%s" % ("存在长直线状暗脊" if best or bestr else "未发现长直线状暗带"))
