"""fix_wm_poisson.py —— 用梯度域融合去水印（照搬 doubao_boost.remove_watermark 的思路）

① 从同一高度、左侧一段取一块干净地形（那里没有水印）
② 算它与目标块在边界上的差值，重模糊成平滑场
③ 差值加回 → 接缝自然连续，内部保留真实纹理
"""
import numpy as np
from PIL import Image, ImageFilter

P = r"E:\DeskTop\地球\素材\moon_base_v2.png"
A = np.asarray(Image.open(P).convert("RGB")).astype(np.float32)
H, W = A.shape[:2]
L = A.mean(2)

# 水印范围（前面测出来的）
X0, X1, Y0, Y1 = 1634, 1889, 1177, 1255
pad = 6
X0, X1 = X0 - pad, X1 + pad
Y0, Y1 = Y0 - pad, Y1 + pad
w, h = X1 - X0, Y1 - Y0
print("目标块 %dx%d @ (%d,%d)" % (w, h, X0, Y0))

# ① 选源块：同高度、往左移 1.6 个块宽，且不含水印
SX0 = X0 - int(w * 1.6)
SX1 = SX0 + w
SY0, SY1 = Y0, Y1
src = A[SY0:SY1, SX0:SX1].copy()
print("源块 x %d~%d（同高）" % (SX0, SX1))

# 亮度对齐（源与目标周边的整体亮度差）
ring_t = A[Y0 - 6:Y0, X0:X1].mean((0, 1))
ring_s = A[SY0 - 6:SY0, SX0:SX1].mean((0, 1))
gain = (ring_t + 1e-3) / (ring_s + 1e-3)
src = np.clip(src * gain, 0, 255)
print("亮度对齐增益 %.3f" % float(gain.mean()))

# ② 差值场：目标块边界 − 源块边界（用目标块的边缘像素构造）
tgt = A[Y0:Y1, X0:X1]
diff = np.zeros_like(A)
diff[Y0:Y1, X0:X1] = tgt - src
d_img = Image.fromarray(np.clip(diff + 128, 0, 255).astype(np.uint8))
d_blur = np.asarray(d_img.filter(ImageFilter.GaussianBlur(26))).astype(np.float32) - 128

# ③ 合成
merged = np.clip(src + d_blur[Y0:Y1, X0:X1], 0, 255)
A[Y0:Y1, X0:X1] = merged

Image.fromarray(np.clip(A, 0, 255).astype(np.uint8)).save(P)
print("已用梯度域融合去水印")
