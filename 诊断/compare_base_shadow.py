"""compare_base_shadow.py —— 量化两张底图的"影子强度" """
import numpy as np
from PIL import Image

BASES = {
    "旧 moon_base": r"E:\DeskTop\地球\素材\moon_base.png",
    "新 moon_base_v2": r"E:\DeskTop\地球\素材\moon_base_v2.png",
}

for name, p in BASES.items():
    A = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    H, W = A.shape
    # 只看地形（下半部且不是天空）
    terrain = A[int(H * 0.62):, :]
    terrain = terrain[terrain > 3]
    if terrain.size < 1000:
        print(name, "地形像素太少")
        continue
    p2, p5, p50, p95, p98 = np.percentile(terrain, [2, 5, 50, 95, 98])
    # 暗部占比（相对于中位数）
    dark_frac = float((terrain < p50 * 0.25).mean() * 100)
    bright_frac = float((terrain > p50 * 2.0).mean() * 100)
    print("== %s" % name)
    print("   地形亮度  p5=%.0f  p50=%.0f  p95=%.0f" % (p5, p50, p95))
    print("   动态范围  p95/p5 = %.2f" % (p95 / max(p5, 1e-6)))
    print("   很暗的像素(<25%%中位) %.1f%%   很亮的(>2x中位) %.1f%%" % (dark_frac, bright_frac))
    print()
