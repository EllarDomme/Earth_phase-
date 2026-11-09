"""crop_base.py —— 裁掉底部带水印的 130px，再拉回 1280 高（不编造纹理）"""
import numpy as np
from PIL import Image

SRC = r"C:\Users\34684\.dsh\attachments\v1\objects\a6\a6c39a0d5bbb63bc28c16a63d3e1e23ea5f552883d69d74b6a5dac628293710c"
OUT = r"E:\DeskTop\地球\素材\moon_base_v2.png"
CROP_BOTTOM = 140          # 水印底边 1255，再加 25px 余量

im = Image.open(SRC).convert("RGB")
W, H = im.size
keep_h = H - CROP_BOTTOM
im2 = im.crop((0, 0, W, keep_h)).resize((W, H), Image.LANCZOS)
print("裁掉底部 %dpx → %dx%d，再拉回 %dx%d" % (CROP_BOTTOM, W, keep_h, W, H))

A = np.asarray(im2).astype(np.float32)
L = A.mean(2)

# 地平线检测（与 build_base 同逻辑）
win = 9
cs = np.cumsum(np.vstack([np.zeros((1, W)), L]), 0)
cs2 = np.cumsum(np.vstack([np.zeros((1, W)), L * L]), 0)
horizon = np.full(W, H, dtype=np.int32)
for x in range(W):
    run = 0
    for y in range(int(H * 0.35), H - win):
        s1 = cs[y + win, x] - cs[y, x]
        s2 = cs2[y + win, x] - cs2[y, x]
        m = s1 / win
        sd = np.sqrt(max(s2 / win - m * m, 0))
        if sd > 4.0:
            run += 1
            if run >= 12:
                horizon[x] = y - 11
                break
        else:
            run = 0
k = 21
pad = np.pad(horizon, (k // 2, k // 2), mode="edge")
horizon = np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)
print("地平线 %d~%d" % (horizon.min(), horizon.max()))

# 天空刷纯黑 + 羽化
yy = np.arange(H)[:, None]
alpha = np.clip((horizon[None, :] + 1 - yy) / 4.0, 0, 1)[..., None]
out = A * (1 - alpha)

Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(OUT)
B = np.asarray(Image.open(OUT).convert("RGB")).astype(np.float32)
print("复查 顶部20行 %s  左上 %s  右上 %s  底部30行 %s"
      % (np.round(B[:20].mean((0, 1)), 1), np.round(B[:60, :60].mean((0, 1)), 1),
         np.round(B[:60, -60:].mean((0, 1)), 1), np.round(B[-30:].mean((0, 1)), 1)))
print("已保存:", OUT)
