"""marked_region.py —— 用户红框区域（x 950~1015, y 40~290）的平均剖面"""
import numpy as np
from PIL import Image

POST = r"E:\DeskTop\地球\成品\2006-04-05_月面_提升_1920x1280.png"
PRE = r"E:\DeskTop\地球\v2\_bak_uni_2006-04-05_月面_提升_1920x1280.png"

A = np.asarray(Image.open(POST).convert("L")).astype(np.float32)
B = np.asarray(Image.open(PRE).convert("L")).astype(np.float32)

for y0, y1 in ((140, 200), (200, 280)):
    pa = A[y0:y1, 920:1020].mean(0)
    pb = B[y0:y1, 920:1020].mean(0)
    print("=== 平均剖面 y %d~%d ===" % (y0, y1))
    print("   x    打光后  打光前   打光后斜率")
    for i in range(len(pa)):
        x = 920 + i
        slope = pa[i] - pa[i - 1] if i else 0
        mark = ""
        if 1 < i < len(pa) - 2 and pa[i] < pa[i - 1] - 0.4 and pa[i] < pa[i + 1] - 0.4:
            mark = "  ← 凹陷（灰线）"
        print("  %3d   %6.1f  %6.1f   %+5.1f%s" % (x, pa[i], pb[i], slope, mark))
    print()
