"""shadow_metrics.py —— 更严谨地量"影子多少"

指标说明：
  ① 只统计地形（地平线以下）
  ② 阴影占比：亮度 < 局部中位数 45% 的像素比例（这才是"被影子盖住多少"）
  ③ 对比度：p90 / p10（去掉极端值，不被个别像素带偏）
  ④ 中位亮度：整体亮不亮
"""
import numpy as np
from PIL import Image

BASES = [
    ("无影", r"E:\DeskTop\地球\素材\moon_base_无影.png"),
    ("中影", r"E:\DeskTop\地球\素材\moon_base_中影.png"),
    ("长影", r"E:\DeskTop\地球\素材\moon_base_长影.png"),
]

print("%-6s %-10s %-12s %-10s %-10s" % ("底图", "中位亮度", "阴影占比", "p90/p10", "p10"))
for name, p in BASES:
    A = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    H, W = A.shape
    # 地形=地平线以下
    hor = np.full(W, H, dtype=np.int32)
    for x in range(W):
        idx = np.where(A[:, x] > 12)[0]
        hor[x] = int(idx[0]) if len(idx) else H
    k = 21
    pad = np.pad(hor, (k // 2, k // 2), mode="edge")
    hor = np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)
    yy = np.arange(H)[:, None]
    m = (yy > hor[None, :] + 25)          # 离地平线远一点，避开边缘
    terr = A[m]
    terr = terr[terr > 3]
    med = np.median(terr)
    p10, p90 = np.percentile(terr, [10, 90])
    shadow = float((terr < med * 0.45).mean() * 100)
    print("%-6s %-10.0f %-11.1f%% %-10.2f %-10.0f"
          % (name, med, shadow, p90 / max(p10, 1e-6), p10))

print()
print("说明：'阴影占比' 才是肉眼说的'影子多不多'；p95/p5 会被亮面面积带偏。")
