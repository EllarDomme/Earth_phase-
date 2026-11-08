"""seamcheck.py —— 判断一张成品的拼接残线程度（原分辨率，不缩放）"""
import sys

import numpy as np
from PIL import Image


def seam_score(path, thr=0.70, span=8, min_frac=0.30):
    A = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    H, W = A.shape
    stack = []
    for d in list(range(-span, -2)) + list(range(3, span + 1)):
        stack.append(np.roll(A, d, axis=1))
    med = np.median(np.stack(stack, 0), axis=0)
    dark = A < med * thr
    col_lit = (A > 10).sum(0) > H * 0.30
    frac = dark.mean(0)
    bad = (frac > min_frac) & col_lit
    return int(bad.sum()), float(frac.max())


if __name__ == "__main__":
    for p in sys.argv[1:]:
        n, mx = seam_score(p)
        print("%-50s 疑似线列 %4d  峰值 %.2f  %s"
              % (p.split("\\")[-1], n, mx, "有残线" if n >= 8 else "干净"))
