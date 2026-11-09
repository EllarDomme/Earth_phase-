"""edge_profile.py —— 1px 步长扫晨昏线，对比打光前/后"""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")

POST = r"E:\DeskTop\地球\成品\2006-04-05_月面_提升_1920x1280.png"
PRE = r"E:\DeskTop\地球\v2\_bak_uni_2006-04-05_月面_提升_1920x1280.png"

A = np.asarray(Image.open(POST).convert("L")).astype(np.float32)
try:
    B = np.asarray(Image.open(PRE).convert("L")).astype(np.float32)
    has_pre = B.shape == A.shape
except Exception:
    has_pre = False
    B = None

print("打光前备份存在:", has_pre)

for y in (80, 120, 180):
    print("\n=== y=%d ===" % y)
    xs = list(range(930, 1005))
    post = [A[y, x] for x in xs]
    pre = [B[y, x] for x in xs] if has_pre else None
    print("  x    打光后   打光前")
    for i, x in enumerate(xs):
        flag = ""
        if 0 < i < len(xs) - 1:
            # 局部极小（凹陷）：比左右都低
            if post[i] < post[i - 1] - 1.5 and post[i] < post[i + 1] - 1.5:
                flag = "  ← 打光后凹陷"
            if pre and pre[i] < pre[i - 1] - 1.5 and pre[i] < pre[i + 1] - 1.5:
                flag += "  ← 打光前凹陷"
        print("  %3d  %7.1f  %s%s" % (x, post[i], ("%7.1f" % pre[i]) if pre else "     -", flag))
