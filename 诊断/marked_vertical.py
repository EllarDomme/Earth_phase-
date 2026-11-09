"""marked_vertical.py —— 红框区域竖直剖面（找横着的暗线）"""
import numpy as np
from PIL import Image

POST = r"E:\DeskTop\地球\成品\2006-04-05_月面_提升_1920x1280.png"
PRE = r"E:\DeskTop\地球\v2\_bak_uni_2006-04-05_月面_提升_1920x1280.png"
A = np.asarray(Image.open(POST).convert("L")).astype(np.float32)
B = np.asarray(Image.open(PRE).convert("L")).astype(np.float32)

for x0, x1 in ((960, 990), (990, 1015)):
    pa = A[30:320, x0:x1].mean(1)
    pb = B[30:320, x0:x1].mean(1)
    print("=== 竖直剖面 x %d~%d ===" % (x0, x1))
    print("   y    打光后  打光前   斜率")
    for i in range(len(pa)):
        y = 30 + i
        slope = pa[i] - pa[i - 1] if i else 0
        mark = ""
        if 1 < i < len(pa) - 2 and pa[i] < pa[i - 1] - 1.0 and pa[i] < pa[i + 1] - 1.0:
            mark = "  ← 凹陷（横线）"
        if y % 2 == 0:
            print("  %3d   %6.1f  %6.1f  %+5.1f%s" % (y, pa[i], pb[i], slope, mark))
    print()
