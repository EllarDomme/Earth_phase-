"""invariant_test.py —— 三条铁律不变量，真图验证

① 打光只改圆盘内（盘外月面/天空一个像素都不许变）
② 摘星只改天空（地形一个像素都不许变）
③ 提清晰度的「还原盘外」确实还原
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
sys.path.insert(0, HERE)
import lighting  # noqa: E402
from layout import disc_geom  # noqa: E402

SRC = os.path.join(HERE, "草稿", "_ra_2021-06-30.png")
if not os.path.exists(SRC):
    SRC = os.path.join(r"E:\DeskTop\草稿", "_ra_2021-06-30.png")
im = Image.open(SRC).convert("RGB")
W, H = im.size
cx, cy, R = disc_geom(W, H)
yy, xx = np.mgrid[0:H, 0:W]
rr = np.hypot(xx - cx, yy - cy)
outside = rr > R * 1.02
inside = rr < R * 0.95

print("图 %dx%d  圆盘中心 (%.0f,%.0f) R=%.0f" % (W, H, cx, cy, R))

# ── ① 打光不动盘外
A = np.asarray(im).astype(np.float32)
L = np.asarray(lighting.apply_lighting(im, "2021-06-30", 22.75, verbose=False)).astype(np.float32)
d_out = np.abs(A - L).max(2)[outside]
d_in = np.abs(A - L).max(2)[inside]
print("\n① 打光：盘外最大变化 %.2f（应 <1）  盘内最大变化 %.0f（应很大）"
      % (d_out.max(), d_in.max()))
ok1 = d_out.max() < 1.0 and d_in.max() > 20

# ── ② 摘星不动地形
from starless import strip_stars  # noqa: E402
sky_mask_out = outside
S = np.asarray(strip_stars(im, glow=6.0)).astype(np.float32) if "glow" in \
    strip_stars.__code__.co_varnames else np.asarray(strip_stars(im)).astype(np.float32)
d_terr = np.abs(A - S).max(2)[inside]
print("② 摘星：盘内最大变化 %.2f（应 ≈0）" % d_terr.max())
ok2 = d_terr.max() < 2.0

# ── ③ restore_scene 还原盘外
import doubao_boost as DB  # noqa: E402
fake = Image.fromarray(np.clip(A * 0.7 + 20, 0, 255).astype(np.uint8))  # 模拟豆包改了全图
R2 = np.asarray(DB.restore_scene(fake, im)).astype(np.float32)
d_out2 = np.abs(np.asarray(im).astype(np.float32) - R2).max(2)[outside]
print("③ restore：盘外最大差 %.2f（应 ≈0，即还原成原图）" % d_out2.max())
ok3 = d_out2.max() < 2.0

print("\n%s" % ("全部通过 ✓" if (ok1 and ok2 and ok3) else "有不变量被破坏 ✗"))
sys.exit(0 if (ok1 and ok2 and ok3) else 1)
