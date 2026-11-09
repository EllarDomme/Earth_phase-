"""edge_avg.py —— 多行平均，找出系统性凹陷（灰线）"""
import numpy as np
from PIL import Image

POST = r"E:\DeskTop\地球\成品\2006-04-05_月面_提升_1920x1280.png"
PRE = r"E:\DeskTop\地球\v2\_bak_uni_2006-04-05_月面_提升_1920x1280.png"

A = np.asarray(Image.open(POST).convert("L")).astype(np.float32)
B = np.asarray(Image.open(PRE).convert("L")).astype(np.float32)

for y0, y1 in ((60, 140), (150, 260), (280, 380)):
    pa = A[y0:y1, 920:1010].mean(0)
    pb = B[y0:y1, 920:1010].mean(0)
    print("=== y %d~%d 平均剖面 ===" % (y0, y1))
    print("  x     打光后  打光前")
    dip = None
    for i in range(len(pa)):
        x = 920 + i
        mark = ""
        if 1 < i < len(pa) - 2:
            if pa[i] < pa[i - 1] - 0.8 and pa[i] < pa[i + 1] - 0.8:
                mark = " ← 打光后凹陷"
                dip = x
        print("  %3d   %6.1f  %6.1f%s" % (x, pa[i], pb[i], mark))
    print("  找到凹陷:", dip)
    print()
