"""verify_v2b.py —— 确认 v2 = 背景.png 等比缩放 + 裁天空（不是拉伸）"""
import numpy as np
from PIL import Image

SRC = r"E:\DeskTop\背景.png"
V2 = r"E:\DeskTop\地球\素材\moon_base_v2.png"

a = Image.open(SRC).convert("RGB")
print("背景.png 尺寸:", a.size)

W, H = a.size
new_h = round(H * 1920 / W)
b = a.resize((1920, new_h), Image.LANCZOS)
cut = new_h - 1280
b = b.crop((0, cut, 1920, new_h))
print("复现：%dx%d -> 等比缩放 1920x%d -> 顶部裁 %d -> 1920x1280" % (W, H, new_h, cut))

A = np.asarray(b).astype(np.float32)
B = np.asarray(Image.open(V2).convert("RGB")).astype(np.float32)
ya = int(1280 * 0.70)
ca, cb = A[ya:].mean(2), B[ya:].mean(2)
m = (ca > 3) & (cb > 3)
corr = float(np.corrcoef(ca[m], cb[m])[0, 1])
mad = float(np.abs(ca[m] - cb[m]).mean())
print("与 v2 的地形区相关 %.6f  平均差 %.3f" % (corr, mad))
print()
print("横向缩放 %.4f   纵向缩放 %.4f" % (1920 / W, new_h / H))
print("两者相等即为等比缩放（无拉伸）")
