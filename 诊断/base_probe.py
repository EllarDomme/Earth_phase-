"""base_probe.py —— 分析新素材与旧素材的天空/地平线/水印"""
import numpy as np
from PIL import Image

NEW = r"C:\Users\34684\.dsh\attachments\v1\objects\a6\a6c39a0d5bbb63bc28c16a63d3e1e23ea5f552883d69d74b6a5dac628293710c"
OLD = r"E:\DeskTop\地球\素材\moon_base.png"

for name, p in (("旧 moon_base", OLD), ("新素材", NEW)):
    im = Image.open(p).convert("RGB")
    A = np.asarray(im).astype(np.float32)
    H, W = A.shape[:2]
    print("== %s  %dx%d" % (name, W, H))
    # 顶部/角落天空
    print("   顶部 20 行 均值 RGB %s" % np.round(A[:20].mean((0, 1)), 1))
    print("   左上角 60x60 均值     %s" % np.round(A[:60, :60].mean((0, 1)), 1))
    print("   右上角 60x60 均值     %s" % np.round(A[:60, -60:].mean((0, 1)), 1))
    # 找地平线：逐列第一个"明显亮"的行
    L = A.mean(2)
    ys = []
    for x in range(0, W, max(1, W // 40)):
        col = L[:, x]
        idx = np.where(col > 18)[0]
        ys.append(int(idx[0]) if len(idx) else H)
    print("   地平线 y: 最小 %d  中位 %d  最大 %d" % (min(ys), int(np.median(ys)), max(ys)))
    print()
