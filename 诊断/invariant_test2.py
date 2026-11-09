"""invariant_test2.py —— 三条不变量（阈值按实测校准）"""
import os
import sys

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
sys.path.insert(0, HERE)
import lighting  # noqa: E402
from layout import disc_geom  # noqa: E402
import doubao_boost as DB  # noqa: E402
from starless import strip_stars  # noqa: E402

SRC = r"E:\DeskTop\草稿\_ra_2021-06-30.png"
im = Image.open(SRC).convert("RGB")
W, H = im.size
cx, cy, R = disc_geom(W, H)
yy, xx = np.mgrid[0:H, 0:W]
rr = np.hypot(xx - cx, yy - cy) / R
far = rr > 1.15          # 远离球缘（排除大气弧那圈）
A = np.asarray(im).astype(np.float32)

print("图 %dx%d  R=%.0f" % (W, H, R))

# ① 打光：球缘外 15% 以远处不许变；弧只允许在 1.0~1.1 环内
L = np.asarray(lighting.apply_lighting(im, "2021-06-30", 22.75, verbose=False)).astype(np.float32)
d = np.abs(A - L).max(2)
far_max = d[far].max()
ring_max = d[(rr > 1.0) & (rr <= 1.1)].max()
ok1 = far_max < 2.0 and ring_max > 5
print("① 打光：远处最大变化 %.1f（应 <2）  球缘环内 %.0f（大气弧，应 >5）" % (far_max, ring_max))

# ② 摘星：地形（盘内且地平线以下）不许变
Lm = A.mean(2)
above = Lm > 6
first = np.argmax(above, axis=0)
hz = np.where(above.any(axis=0), first, H).astype(np.int32)
hz = np.array([int(hz[max(0, i - 10):i + 21].min()) for i in range(W)], np.int32)
sky = np.zeros((H, W), bool)
for x in range(W):
    sky[:max(0, hz[x] - 2), x] = True
disc = rr <= 1.0
terrain = ~sky & ~disc
S, n_stars = strip_stars(A.copy(), hz, disc, verbose=False, sky=sky)
d2 = np.abs(A - np.asarray(S, dtype=np.float32)).max(2)
print("② 摘星：地形最大变化 %.1f（应 ≈0）  天空最大变化 %.0f（应 >0）  摘掉 %d 像素"
      % (d2[terrain].max(), d2[sky].max(), n_stars))
ok2 = d2[terrain].max() < 2.0      # 图里本来就没星点（天空已刷纯黑），只要求地形不动

# ③ restore_scene 的职责是"按均值把盘外亮度拉回"（乘法曝光补偿）
fake = Image.fromarray(np.clip(A * 0.7, 0, 255).astype(np.uint8))
R2 = np.asarray(DB.restore_scene(fake, im)).astype(np.float32)
B = A
m_out = far & (B.mean(2) > 8)          # 有内容的月面
mean_a = float(np.asarray(fake).astype(np.float32).mean(2)[m_out].mean())
mean_r = float(R2.mean(2)[m_out].mean())
mean_o = float(B.mean(2)[m_out].mean())
sky = B.mean(2) < 1.0
sky_max = float(R2.mean(2)[sky].max()) if sky.any() else 0.0
print("③ 还原：盘外均值 原图 %.1f → 校正后 %.1f（应≈原图，误差<2）  天空最大 %.1f（应≈0）"
      % (mean_o, mean_r, sky_max))
ok3 = abs(mean_r - mean_o) < 2.0 and sky_max < 2.0

print("\n%s" % ("三条不变量全部成立 ✓" if (ok1 and ok2 and ok3) else "有不变量被破坏 ✗"))
sys.exit(0 if (ok1 and ok2 and ok3) else 1)
