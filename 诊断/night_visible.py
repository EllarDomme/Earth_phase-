"""night_visible.py —— 92% 月夜：无影底图 + 三档亮度（可见 vs 压黑）"""
import os

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
OUT = r"E:\DeskTop\草稿"

flat = np.asarray(Image.open(os.path.join(OUT, "无影底图.png")).convert("RGB")).astype(np.float32)
H, W = flat.shape[:2]

VARIANTS = [
    ("压黑_1e-4", 0.006, 1.2, "按地球曝光的严格值（地面纯黑）"),
    ("微亮_a", 0.10, 3.0, "地面隐约可见"),
    ("微亮_b", 0.22, 4.0, "地面清楚可见（推荐）"),
    ("微亮_c", 0.35, 5.0, "偏亮"),
]

tiles = []
for tag, g, floor, desc in VARIANTS:
    out = flat * g + floor
    out[..., 0] *= 0.93
    out[..., 2] *= 1.04
    out = np.clip(out, 0, 255)
    p = os.path.join(OUT, "月夜_%s.png" % tag)
    Image.fromarray(out.astype(np.uint8)).save(p)
    terr = out[900:]
    print("  %-10s 增益 %.3f  地形均 %5.1f  p95 %5.1f   %s"
          % (tag, g, terr.mean(), np.percentile(terr, 95), desc))
    tiles.append((tag, p))

S = (700, 380)
crop_y = 860
ims = [Image.open(p).crop((0, crop_y, W, H)).resize(S, Image.LANCZOS) for _, p in tiles]
sheet = Image.new("RGB", (S[0] * len(ims) + 6 * (len(ims) - 1), S[1]), (10, 10, 10))
for i, im in enumerate(ims):
    sheet.paste(im, (i * (S[0] + 6), 0))
sp = os.path.join(OUT, "月夜亮度对比.png")
sheet.save(sp)
print("对比条:", sp, "（左→右：压黑 / 0.10 / 0.22 / 0.35）")
