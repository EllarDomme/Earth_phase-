"""restore_and_fix.py —— 恢复原图，用"多候选块 + 梯度域融合"补水印

思路：
  ① 在图中找若干候选源块（同高度、左右不同偏移）
  ② 对每个候选，算它与被补块**边界环**的差异（SSD），挑最像的
  ③ 用梯度域融合（模糊差值场）粘回去 —— 内部是真纹理，只对齐接缝
"""
import numpy as np
from PIL import Image, ImageFilter

SRC = r"C:\Users\34684\.dsh\attachments\v1\objects\a6\a6c39a0d5bbb63bc28c16a63d3e1e23ea5f552883d69d74b6a5dac628293710c"
OUT = r"E:\DeskTop\地球\素材\moon_base_v2.png"

im = Image.open(SRC).convert("RGB")
A = np.asarray(im).astype(np.float32)
H, W = A.shape[:2]
L = A.mean(2)

# ── 天空：去太阳光晕 + 刷纯黑（这一段保留原图构图，不裁不缩）
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
yy = np.arange(H)[:, None]
alpha = np.clip((horizon[None, :] + 1 - yy) / 4.0, 0, 1)[..., None]
A = A * (1 - alpha)
print("天空已刷黑（地平线 %d~%d），画面尺寸保持 %dx%d" % (horizon.min(), horizon.max(), W, H))

# ── 水印：目标块（含 12px 余量）
X0, X1, Y0, Y1 = 1634 - 12, 1889 + 12, 1177 - 12, 1255 + 12
Y1 = min(Y1, H)
w, h = X1 - X0, Y1 - Y0
tgt = A[Y0:Y1, X0:X1]

print("目标块 %dx%d @ (%d,%d)" % (w, h, X0, Y0))

# ── 候选源块：同高度，左右平移若干距离
best = None
for dx in (int(w * 1.2), int(w * 1.6), int(w * 2.0), -int(w * 1.2), -int(w * 1.6)):
    sx = X0 + dx
    if sx < 0 or sx + w > W:
        continue
    cand = A[Y0:Y1, sx:sx + w]
    # 边界环差异（只比边缘 4px）
    ring_t = np.concatenate([tgt[:4].ravel(), tgt[-4:].ravel(),
                             tgt[:, :4].ravel(), tgt[:, -4:].ravel()])
    ring_c = np.concatenate([cand[:4].ravel(), cand[-4:].ravel(),
                             cand[:, :4].ravel(), cand[:, -4:].ravel()])
    # 亮度先对齐再比结构
    g = (ring_t.mean() + 1e-3) / (ring_c.mean() + 1e-3)
    cand2 = np.clip(cand * g, 0, 255)
    ring_c2 = np.concatenate([cand2[:4].ravel(), cand2[-4:].ravel(),
                              cand2[:, :4].ravel(), cand2[:, -4:].ravel()])
    score = float(np.mean((ring_t - ring_c2) ** 2))
    print("  候选 dx=%+5d  边界差异 %8.1f  增益 %.3f" % (dx, score, g))
    if best is None or score < best[0]:
        best = (score, cand2)

if best is None:
    raise SystemExit("没有可用候选块")

_, src = best
# ── 梯度域融合
diff = np.zeros_like(A)
diff[Y0:Y1, X0:X1] = tgt - src
d = Image.fromarray(np.clip(diff + 128, 0, 255).astype(np.uint8))
d_blur = np.asarray(d.filter(ImageFilter.GaussianBlur(30))).astype(np.float32) - 128
A[Y0:Y1, X0:X1] = np.clip(src + d_blur[Y0:Y1, X0:X1], 0, 255)

Image.fromarray(np.clip(A, 0, 255).astype(np.uint8)).save(OUT)
print("已保存（原构图、无裁剪）:", OUT)
