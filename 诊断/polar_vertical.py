"""polar_vertical.py —— 北极附近竖直剖面，找“临边→亮面”之间是否凹陷"""
import numpy as np
from PIL import Image

POST = r"E:\DeskTop\地球\成品\2006-04-05_月面_提升_1920x1280.png"
A = np.asarray(Image.open(POST).convert("L")).astype(np.float32)

print("竖直剖面（从上往下，经过球缘 → 北极 → 内部）")
for x in (860, 900, 930):
    print("\n=== x=%d ===" % x)
    col = A[20:200, x]
    for i in range(0, len(col), 2):
        y = 20 + i
        mark = ""
        if 2 < i < len(col) - 3:
            # 局部极小（先升后降）
            if col[i] < col[i - 2] - 2 and col[i] < col[i + 2] - 2:
                mark = "  ← 凹陷"
        print("  y=%3d  %6.1f%s" % (y, col[i], mark))
