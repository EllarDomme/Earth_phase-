"""make_base_v2.py —— 去太阳光晕 + 天空刷纯黑 + 去水印（改进检测）"""
import numpy as np
from PIL import Image, ImageFilter

SRC = r"C:\Users\34684\.dsh\attachments\v1\objects\a6\a6c39a0d5bbb63bc28c16a63d3e1e23ea5f552883d69d74b6a5dac628293710c"
OUT = r"E:\DeskTop\地球\素材\moon_base_v2.png"
DBG = r"E:\DeskTop\地球\v2\base_v2_horizon.png"

im = Image.open(SRC).convert("RGB")
A = np.asarray(im).astype(np.float32)
H, W = A.shape[:2]
L = A.mean(2)

# 每列的局部标准差（9 行窗口）：地形起伏大，天空/光晕平滑
win = 9
std_map = np.zeros_like(L)
cs = np.cumsum(np.vstack([np.zeros((1, W)), L]), axis=0)
cs2 = np.cumsum(np.vstack([np.zeros((1, W)), L * L]), axis=0)
for y in range(0, H - win):
    s1 = cs[y + win] - cs[y]
    s2 = cs2[y + win] - cs2[y]
    m = s1 / win
    std_map[y] = np.sqrt(np.maximum(s2 / win - m * m, 0))

# 地平线：从 0.35H 开始，第一个"连续 12 行 std>4"的位置
horizon = np.full(W, H, dtype=np.int32)
y_start = int(H * 0.35)
for x in range(W):
    run = 0
    for y in range(y_start, H - win):
        if std_map[y, x] > 4.0:
            run += 1
            if run >= 12:
                horizon[x] = y - 11
                break
        else:
            run = 0

k = 21
pad = np.pad(horizon, (k // 2, k // 2), mode="edge")
horizon = np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)
print("地平线: 最小 %d 中位 %d 最大 %d" % (horizon.min(), int(np.median(horizon)), horizon.max()))

# 画调试图
dbg = A.copy()
for x in range(0, W, 4):
    y = horizon[x]
    if 0 <= y < H:
        dbg[max(0, y - 2):y + 3, x] = [255, 0, 0]
Image.fromarray(dbg.astype(np.uint8)).save(DBG)

# 天空刷纯黑 + 交界羽化
yy = np.arange(H)[:, None]
SKY = 0.0
alpha = np.clip((horizon[None, :] + 1 - yy) / 4.0, 0, 1)[..., None]
out = A * (1 - alpha) + SKY * alpha

# 去水印：只看最右下角
x_lo, y_lo = int(W * 0.82), int(H * 0.90)
sub = L[y_lo:, x_lo:]
ys, xs = np.where(sub > 200)
if len(xs) > 40:
    x0 = int(xs.min()) + x_lo
    x1 = int(xs.max()) + x_lo
    y0 = int(ys.min()) + y_lo
    y1 = int(ys.max()) + y_lo
    print("水印范围: x %d~%d  y %d~%d" % (x0, x1, y0, y1))
    pad2 = 10
    x0, x1 = max(0, x0 - pad2), min(W, x1 + pad2)
    y0, y1 = max(y_lo, y0 - pad2), min(H, y1 + pad2)
    w, h = x1 - x0, y1 - y0
    base = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    patch = base.crop((x0, max(0, y0 - h - 14), x1, max(1, y0 - 14)))
    mask = Image.new("L", (w, h), 255).filter(ImageFilter.GaussianBlur(5))
    base.paste(patch, (x0, y0), mask)
    out = np.asarray(base).astype(np.float32)
    print("已去水印")

Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(OUT)
B = np.asarray(Image.open(OUT).convert("RGB")).astype(np.float32)
print("处理后 顶部20行 %s  左上 %s  右上 %s"
      % (np.round(B[:20].mean((0, 1)), 1), np.round(B[:60, :60].mean((0, 1)), 1),
         np.round(B[:60, -60:].mean((0, 1)), 1)))
print("已保存:", OUT)
