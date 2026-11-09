"""crop_mid_final.py —— 去掉底部白边（含标尺线和豆包水印），补齐到 1920x1280"""
import numpy as np
from PIL import Image

SRC = r"C:\Users\34684\.dsh\attachments\v1\objects\bc\bc632918ca807bdad4aed9fe7801a0c62e66b52204a595f3a4f89c48f9be523e"
OUT = r"E:\DeskTop\地球\素材\moon_base_中影.png"
COPY = r"E:\DeskTop\草稿\中影底图_1920x1280.png"

im = Image.open(SRC).convert("RGB")
A = np.asarray(im).astype(np.float32)
H, W = A.shape[:2]
L = A.mean(2)
print("原图 %dx%d" % (W, H))

# ① 找出底部白带：从下往上，行均值 > 180 视为白边
rows = L.mean(1)
cut = H
for y in range(H - 1, int(H * 0.80), -1):
    if rows[y] > 180:
        cut = y
    else:
        break
print("白带从 y=%d 开始（高 %d px）" % (cut, H - cut))

A = A[:cut]
H2 = A.shape[0]
print("裁掉白边后 %dx%d" % (W, H2))

# ② 天空刷纯黑（羽化）—— 与另两张一致
L2 = A.mean(2)
hor = np.full(W, H2, dtype=np.int32)
for x in range(W):
    idx = np.where(L2[:, x] > 12)[0]
    hor[x] = int(idx[0]) if len(idx) else H2
k = 21
pad = np.pad(hor, (k // 2, k // 2), mode="edge")
hor = np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)
print("地平线 中位 %d" % int(np.median(hor)))
yy = np.arange(H2)[:, None]
alpha = np.clip((hor[None, :] + 1 - yy) / 4.0, 0, 1)[..., None]
A = A * (1 - alpha)

# ③ 等比放到宽 1920，再从顶部补/裁到 1280
img = Image.fromarray(np.clip(A, 0, 255).astype(np.uint8))
new_h = round(H2 * 1920 / W)
img = img.resize((1920, new_h), Image.LANCZOS)
print("等比缩放到 1920x%d" % new_h)
if new_h < 1280:                      # 高度不够 → 顶部补黑太空
    add = 1280 - new_h
    canvas = Image.new("RGB", (1920, 1280), (0, 0, 0))
    canvas.paste(img, (0, add))
    img = canvas
    print("顶部补 %dpx 黑色太空" % add)
elif new_h > 1280:                    # 高度超出 → 从顶部裁天空
    cut2 = new_h - 1280
    img = img.crop((0, cut2, 1920, new_h))
    print("顶部裁掉 %dpx 天空" % cut2)

img.save(OUT)
img.transpose(Image.FLIP_LEFT_RIGHT).save(
    r"E:\DeskTop\地球\素材\moon_base_中影_mirror.png")
img.save(COPY)

B = np.asarray(Image.open(OUT).convert("L")).astype(np.float32)
ys = []
for x in range(0, 1920, 40):
    idx = np.where(B[:, x] > 18)[0]
    ys.append(int(idx[0]) if len(idx) else 1280)
t = B[900:]
t = t[t > 3]
print("复查: 顶部20行 %.1f  地平线 中位 %d  地形 p5=%.0f p95=%.0f 阴影深度 %.1f"
      % (B[:20].mean(), int(np.median(ys)), np.percentile(t, 5),
         np.percentile(t, 95), np.percentile(t, 95) / max(np.percentile(t, 5), 1e-6)))
print("已保存:", OUT)
