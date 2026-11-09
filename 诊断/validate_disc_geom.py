"""validate_disc_geom.py —— 零额度验证：boost 换成居中圆盘后，几何必须显式传

对照组：
  A. 默认几何（海报 0.50/0.31/0.36）用在居中铺满的圆盘图上 → 应当打偏
  B. 显式传 0.5,0.5,0.5                                   → 应当正确
判据：
  ① restore_scene 在圆盘图上不该改动任何像素（盘外为空）
  ② match_disc 应把整体压暗的盘内亮度还原回原图（误差 <2）
"""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
import doubao_boost as DB  # noqa: E402

SRC = r"E:\DeskTop\地球\v2\_bak_uni_2021-06-30_地球相_2048.png"
im = Image.open(SRC).convert("RGB")
A = np.asarray(im).astype(np.float32)
H, W = A.shape[:2]
print("圆盘素材 %dx%d（地球铺满整幅）" % (W, H))

dark = Image.fromarray(np.clip(A * 0.70, 0, 255).astype(np.uint8))
D = np.asarray(dark).astype(np.float32)

print("\n=== A：默认海报几何（0.50,0.31,0.36）===")
DB.set_disc_geom(None)
r_a = np.asarray(DB.restore_scene(dark, im)).astype(np.float32)
chg_a = np.abs(D - r_a).max()
print("  restore_scene 改动最大 %.1f  （圆盘图不该改，>2 就是打偏）" % chg_a)

print("\n=== B：显式居中几何（0.50,0.50,0.50）===")
DB.set_disc_geom(0.5, 0.5, 0.5)
r_b = np.asarray(DB.restore_scene(dark, im)).astype(np.float32)
chg_b = np.abs(D - r_b).max()
print("  restore_scene 改动最大 %.1f  （应 ≈0）" % chg_b)

print("\n=== match_disc：两种几何下盘内亮度还原 ===")
for tag in ("A 默认", "B 居中"):
    DB.set_disc_geom(None) if tag.startswith("A") else DB.set_disc_geom(0.5, 0.5, 0.5)
    out = np.asarray(DB.match_disc(dark, im)).astype(np.float32)
    m = out.mean(2) > 8
    cur, ref = float(out.mean(2)[m].mean()), float(A.mean(2)[m].mean())
    print("  %-7s 还原后 %.1f  原图 %.1f  误差 %.1f" % (tag, cur, ref, abs(cur - ref)))

DB.set_disc_geom(None)
print("\n结论：B 必须通过（改动≈0、误差<2）；A 应当明显偏离。")
