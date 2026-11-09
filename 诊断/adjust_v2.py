"""adjust_v2.py —— 让 v2 的前景比例与旧图一致：地平线 761 → 785

做法：底部裁 24px（少一点前景），顶部补 24px 黑太空（尺寸不变）
"""
import numpy as np
from PIL import Image

P = r"E:\DeskTop\地球\素材\moon_base_v2.png"
M = r"E:\DeskTop\地球\素材\moon_base_v2_mirror.png"

im = Image.open(P).convert("RGB")
W, H = im.size
A = np.asarray(im).astype(np.float32)
L = A.mean(2)

hor = np.full(W, H, dtype=np.int32)
for x in range(W):
    idx = np.where(L[:, x] > 18)[0]
    hor[x] = int(idx[0]) if len(idx) else H
h0 = int(np.median(hor))
print("调整前：%dx%d  地平线 %d  地形高 %d" % (W, H, h0, H - h0))

TARGET = 785
SHIFT = TARGET - h0          # = 24
print("要下移 %d px → 底部裁 %d，顶部补 %d 黑太空" % (SHIFT, SHIFT, SHIFT))

# 裁底
A2 = A[:H - SHIFT]
# 顶部补黑
canvas = np.zeros((H, W, 3), dtype=np.float32)
canvas[SHIFT:] = A2

out = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
out.save(P)
out.transpose(Image.FLIP_LEFT_RIGHT).save(M)

# 复查
B = np.asarray(Image.open(P).convert("L")).astype(np.float32)
ys = []
for x in range(0, W, 40):
    idx = np.where(B[:, x] > 18)[0]
    ys.append(int(idx[0]) if len(idx) else H)
hz = int(np.median(ys))
print("调整后：%dx%d  地平线 %d  地形高 %d  顶部20行 %.1f"
      % (W, H, hz, H - hz, B[:20].mean()))
print("对比旧图 moon_base.png：地平线 785  地形高 495")
