"""fix_watermark.py —— 收缩检测范围 + 提高阈值，只补"白字"，用扩散修补"""
import numpy as np
from PIL import Image

SRC = r"E:\DeskTop\地球\素材\moon_base_v2.png"
DEBUG = r"E:\DeskTop\地球\v2\wm_mask.png"

im = Image.open(SRC).convert("RGB")
A = np.asarray(im).astype(np.float32)
H, W = A.shape[:2]
L = A.mean(2)

x0, y0 = int(W * 0.84), int(H * 0.92)
sub = L[y0:, x0:]
mask_sub = sub > 195                      # 只抓明显白字
print("区域内像素 %d，白字像素 %d" % (sub.size, int(mask_sub.sum())))
if mask_sub.sum() < 20:
    print("没找到白字，退出")
    raise SystemExit

ys, xs = np.where(mask_sub)
Y0, Y1 = int(ys.min()) + y0, int(ys.max()) + y0
X0, X1 = int(xs.min()) + x0, int(xs.max()) + x0
print("白字范围 x %d~%d  y %d~%d" % (X0, X1, Y0, Y1))

pad = 8
X0, X1 = max(0, X0 - pad), min(W, X1 + pad)
Y0, Y1 = max(0, Y0 - pad), min(H, Y1 + pad)
mask = np.zeros((Y1 - Y0, X1 - X0), dtype=bool)
mask[ys + (y0 - Y0), xs + (x0 - X0)] = True
for _ in range(4):
    m = mask.copy()
    m[1:, :] |= mask[:-1, :]; m[:-1, :] |= mask[1:, :]
    m[:, 1:] |= mask[:, :-1]; m[:, :-1] |= mask[:, 1:]
    mask = m
print("膨胀后掩膜像素 %d" % int(mask.sum()))

# 调试图
dbg = np.asarray(im).copy()
dbg[Y0:Y1, X0:X1][mask] = [255, 40, 40]
Image.fromarray(dbg).save(DEBUG)

# 扩散修补
patch = A[Y0:Y1, X0:X1].copy()
h, w = mask.shape
work = patch.copy()
for c in range(3):
    ch = work[..., c]
    for _ in range(500):
        up = np.roll(ch, 1, 0); up[0] = ch[0]
        dn = np.roll(ch, -1, 0); dn[-1] = ch[-1]
        lf = np.roll(ch, 1, 1); lf[:, 0] = ch[:, 0]
        rt = np.roll(ch, -1, 1); rt[:, -1] = ch[:, -1]
        ch = np.where(mask, (up + dn + lf + rt) / 4.0, ch)
    work[..., c] = ch

# 环状邻域颗粒噪声
ring = np.zeros_like(mask)
for _ in range(8):
    r = ring.copy()
    r[1:, :] |= mask[:-1, :] | ring[:-1, :]
    r[:-1, :] |= mask[1:, :] | ring[1:, :]
    r[:, 1:] |= mask[:, :-1] | ring[:, :-1]
    r[:, :-1] |= mask[:, 1:] | ring[:, 1:]
    ring = r & ~mask
sigma = float(A[Y0:Y1, X0:X1].mean(2)[ring].std()) if ring.sum() > 50 else 5.0
rng = np.random.default_rng(3)
work = np.clip(work + rng.normal(0, sigma * 0.6, (h, w, 1)) * mask[..., None], 0, 255)

patch[mask] = work[mask]
A[Y0:Y1, X0:X1] = patch
Image.fromarray(np.clip(A, 0, 255).astype(np.uint8)).save(SRC)
print("已修补:", SRC, " 噪声σ=%.1f" % sigma)
