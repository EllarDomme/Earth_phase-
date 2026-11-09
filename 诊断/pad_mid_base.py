"""pad_mid_base.py —— 中影版底图：补回 204px 太空背景 + 天空刷纯黑

原图 1920×1076（少了 204px，缺的正是顶部太空）
→ 顶部补 204px 纯黑 → 1920×1280
→ 天空统一刷成 0（与旧素材一致）
"""
import numpy as np
from PIL import Image

SRC = r"C:\Users\34684\.dsh\attachments\v1\objects\74\74673ca6dc541d16f3b066acb30b4331b6831fb2070bcd4a4434496e22688169"
OUT = r"E:\DeskTop\地球\素材\moon_base_mid.png"
OUT_MIRROR = r"E:\DeskTop\地球\素材\moon_base_mid_mirror.png"
COPY = r"E:\DeskTop\草稿\中影底图_1920x1280.png"

im = Image.open(SRC).convert("RGB")
A = np.asarray(im).astype(np.float32)
H0, W = A.shape[:2]
print("原图 %dx%d" % (W, H0))

L = A.mean(2)
hor = np.full(W, H0, dtype=np.int32)
for x in range(W):
    idx = np.where(L[:, x] > 12)[0]
    hor[x] = int(idx[0]) if len(idx) else H0
k = 21
pad = np.pad(hor, (k // 2, k // 2), mode="edge")
hor = np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)
print("原地平线 中位 %d" % int(np.median(hor)))

# ① 天空刷纯黑（羽化 4px）
yy = np.arange(H0)[:, None]
alpha = np.clip((hor[None, :] + 1 - yy) / 4.0, 0, 1)[..., None]
A = A * (1 - alpha)

# ② 顶部补 204px 纯黑
ADD = 1280 - H0
canvas = np.zeros((1280, W, 3), dtype=np.float32)
canvas[ADD:] = A
print("顶部补 %dpx 黑色太空 → 1920x1280" % ADD)
print("新地平线 中位 %d" % (int(np.median(hor)) + ADD))

Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8)).save(OUT)
Image.open(OUT).transpose(Image.FLIP_LEFT_RIGHT).save(OUT_MIRROR)
Image.open(OUT).save(COPY)

B = np.asarray(Image.open(OUT).convert("RGB")).astype(np.float32)
BL = B.mean(2)
ys = []
for x in range(0, W, 40):
    idx = np.where(BL[:, x] > 18)[0]
    ys.append(int(idx[0]) if len(idx) else 1280)
print("复查：顶部20行 %s  左上 %s  地平线 中位 %d  底部均 %.0f"
      % (np.round(B[:20].mean((0, 1)), 1), np.round(B[:60, :60].mean((0, 1)), 1),
         int(np.median(ys)), B[-50:].mean()))
print("已保存:", OUT)
print("镜像:  ", OUT_MIRROR)
print("预览:  ", COPY)
