"""local_retouch.py —— 局部重绘实验：把"无影"左下方的无影细节搬到"中影"

做法（梯度域融合，Poisson-lite）：
  ① 取源块（无影）与目标块（中影）同一区域
  ② 亮度对齐
  ③ 差值场重模糊 → 加回源块 → 接缝自然、内部保留源图的光照
  ④ 用羽化蒙版贴回去，只影响左下那一块
"""
import numpy as np
from PIL import Image, ImageFilter

AST = r"E:\DeskTop\地球\素材"
SRC = AST + r"\moon_base_无影.png"
DST = AST + r"\moon_base_中影.png"
OUT = r"E:\DeskTop\草稿\中影_局部重绘.png"

BOX = (0, 1040, 420, 1280)      # 左下那一块

a = Image.open(SRC).convert("RGB")
b = Image.open(DST).convert("RGB")
src = a.crop(BOX)
tgt = b.crop(BOX)
w, h = src.size

A = np.asarray(src).astype(np.float32)
B = np.asarray(tgt).astype(np.float32)

# ② 亮度对齐
gain = (B.mean() + 1e-3) / (A.mean() + 1e-3)
A = np.clip(A * gain, 0, 255)
print("亮度对齐增益 %.3f" % gain)

# ③ 梯度域融合
diff = np.zeros_like(np.asarray(b).astype(np.float32))
diff[BOX[1]:BOX[3], BOX[0]:BOX[2]] = B - A
d = Image.fromarray(np.clip(diff + 128, 0, 255).astype(np.uint8))
d_blur = np.asarray(d.filter(ImageFilter.GaussianBlur(40))).astype(np.float32) - 128
merged = np.clip(A + d_blur[BOX[1]:BOX[3], BOX[0]:BOX[2]], 0, 255)

# ④ 羽化蒙版（左/上边界软，右/下留在画面外）
m = np.ones((h, w), dtype=np.float32)
fx, fy = 70, 50
for i in range(fx):
    m[:, i] *= i / fx
for i in range(fx):
    m[:, w - 1 - i] *= min(1.0, (w - 1 - i) / (w - 0.001)) if False else 1.0
for j in range(fy):
    m[j, :] *= j / fy
m = np.asarray(Image.fromarray((m * 255).astype(np.uint8))
               .filter(ImageFilter.GaussianBlur(12))).astype(np.float32) / 255.0

out = np.asarray(b).astype(np.float32).copy()
region = out[BOX[1]:BOX[3], BOX[0]:BOX[2]]
out[BOX[1]:BOX[3], BOX[0]:BOX[2]] = merged * m[..., None] + region * (1 - m[..., None])
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(OUT)

# 对比图
S = (700, 437)
c = Image.new("RGB", (S[0] * 2 + 10, S[1]), (10, 10, 10))
c.paste(b.crop((0, 900, 900, 1280)).resize(S, Image.LANCZOS), (0, 0))
c.paste(Image.open(OUT).crop((0, 900, 900, 1280)).resize(S, Image.LANCZOS), (S[0] + 10, 0))
c.save(r"E:\DeskTop\草稿\中影_重绘前后.png")
print("已保存:", OUT)
print("对比: 草稿\\中影_重绘前后.png（左=原中影 右=重绘后）")
