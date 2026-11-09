"""check_stretch.py —— 核对 moon_base_v2 有没有被拉伸"""
import numpy as np
from PIL import Image

SRC = r"C:\Users\34684\.dsh\attachments\v1\objects\a6\a6c39a0d5bbb63bc28c16a63d3e1e23ea5f552883d69d74b6a5dac628293710c"
V2 = r"E:\DeskTop\地球\素材\moon_base_v2.png"
OLD = r"E:\DeskTop\地球\素材\moon_base.png"


def horizon(p):
    A = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    H, W = A.shape
    ys = []
    for x in range(0, W, 40):
        idx = np.where(A[:, x] > 18)[0]
        ys.append(int(idx[0]) if len(idx) else H)
    return W, H, int(np.median(ys))


for name, p in (("原始 背景.png", SRC), ("moon_base_v2", V2), ("moon_base(旧)", OLD)):
    W, H, hz = horizon(p)
    print("%-16s %4dx%-4d  地平线 %4d  地平线占比 %.1f%%  地形高 %d px"
          % (name, W, H, hz, hz / H * 100, H - hz))

print()
print("=== 换算核对 v2 的生成过程 ===")
W0, H0, hz0 = horizon(SRC)
scale = 1920 / 1760
print("原始 %dx%d → 等比缩放到宽 1920：x%.4f → 高度 %.0f" % (W0, H0, scale, H0 * scale))
print("缩放后地平线应为 %.0f，再从顶部裁 84px → %.0f" % (hz0 * scale, hz0 * scale - 84))
print("实测 v2 地平线 %d，地形高 %d（应为 %.0f）"
      % (V2 and horizon(V2)[2], horizon(V2)[1] - horizon(V2)[2], (H0 - hz0) * scale))
