"""paint_shadow.py —— 给左边那个坑按大坑的光照画阴影

几何：把坑当椭圆碗 h = -D·(1-r²)
光照：大坑实测的太阳方向 (0.95, 0.20, 0.28)（光从右侧来）
      内壁受光面 = 法线与光线夹角小的一侧 → 左侧内壁亮、右侧内壁暗
"""
import numpy as np
from PIL import Image, ImageFilter

BASE = r"E:\DeskTop\草稿\中影_局部重绘.png"     # 已补细节（无影）的版本
OUT = r"E:\DeskTop\草稿\中影_画阴影.png"

CX, CY = 250.0, 1190.0        # 坑心
RX, RY = 215.0, 105.0         # 坑半径
D = 0.85                      # 碗深（相对半径）
L = np.array([0.95, 0.20, 0.28], dtype=np.float32)
L /= np.linalg.norm(L)

im = Image.open(BASE).convert("RGB")
A = np.asarray(im).astype(np.float32)
H, W = A.shape[:2]

# 只在这个框里算
X0, X1 = int(CX - RX * 1.35), int(CX + RX * 1.35)
Y0, Y1 = int(CY - RY * 1.6), int(CY + RY * 1.6)
X0, Y0 = max(0, X0), max(0, Y0)
X1, Y1 = min(W, X1), min(H, Y1)

yy, xx = np.mgrid[Y0:Y1, X0:X1]
u = (xx - CX) / RX
v = (yy - CY) / RY
r2 = u * u + v * v
inside = r2 < 1.0

# 高度场（归一化坐标），碗：中心最低
h = np.where(inside, -D * (1 - r2), 0.0)

# 法线（数值差分）
gy, gx = np.gradient(h)
nz = np.ones_like(h)
n = np.stack([-gx * RX / RX, -gy * RY / RY, nz], axis=-1)   # 梯度已按像素算
nn = np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
n = n / nn

# 朗伯
ndl = np.clip((n * L).sum(-1), 0, 1)
shade = 0.18 + 0.82 * ndl            # 加一点环境光，避免纯黑

# 只影响坑内，边缘 25% 羽化
edge = np.clip((1.0 - r2) / 0.25, 0, 1)
w = np.where(inside, edge, 0.0)
w = np.asarray(Image.fromarray((w * 255).astype(np.uint8))
               .filter(ImageFilter.GaussianBlur(6))).astype(np.float32) / 255.0

region = A[Y0:Y1, X0:X1]
new = region * shade[..., None]
out = A.copy()
out[Y0:Y1, X0:X1] = new * w[..., None] + region * (1 - w[..., None])
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(OUT)

S = (760, 380)
c = Image.new("RGB", (S[0] * 2 + 10, S[1]), (10, 10, 10))
c.paste(Image.open(BASE).crop((0, 980, 760, 1280)).resize(S, Image.LANCZOS), (0, 0))
c.paste(Image.open(OUT).crop((0, 980, 760, 1280)).resize(S, Image.LANCZOS), (S[0] + 10, 0))
c.save(r"E:\DeskTop\草稿\画阴影前后.png")
print("已保存:", OUT)
print("对比: 草稿\\画阴影前后.png (左=补细节后 右=画阴影后)")
