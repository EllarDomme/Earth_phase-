"""probe_bg.py —— 看新图（已去水印）的尺寸/天空/太阳位置"""
import numpy as np
from PIL import Image

NEW = r"E:\DeskTop\背景.png"
OLD = r"E:\DeskTop\地球\素材\moon_base.png"

for name, p in (("新 背景.png", NEW), ("旧 moon_base", OLD)):
    im = Image.open(p).convert("RGB")
    A = np.asarray(im).astype(np.float32)
    H, W = A.shape[:2]
    L = A.mean(2)
    print("== %s  %dx%d" % (name, W, H))
    print("   顶部 20 行均值 %s" % np.round(A[:20].mean((0, 1)), 1))
    print("   左上角 60x60   %s" % np.round(A[:60, :60].mean((0, 1)), 1))
    print("   右上角 60x60   %s" % np.round(A[:60, -60:].mean((0, 1)), 1))
    # 最亮处（找太阳）
    y, x = np.unravel_index(np.argmax(L[: int(H * 0.6)]), L[: int(H * 0.6)].shape)
    print("   上半部最亮点 (%d,%d) 亮度 %.0f" % (x, y, L[y, x]))
    print("   右下角 200x120 均值 %s" % np.round(A[-120:, -200:].mean((0, 1)), 1))
    print()
