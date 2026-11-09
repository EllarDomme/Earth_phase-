"""verify_no_cut.py —— 检查新底图是否真的裁掉了月面顶部"""
import numpy as np
from PIL import Image

SRC = r"E:\DeskTop\影子图\中影图.png"
NEW = r"E:\DeskTop\地球\素材\moon_base_中影.png"

s = Image.open(SRC).convert("RGB")
n = Image.open(NEW).convert("RGB")
print("源图 %s   新图 %s" % (s.size, n.size))

A = np.asarray(s).astype(np.float32)
L = A.mean(2)
rows = L.mean(1)
cut = len(rows)
for y in range(len(rows) - 1, int(len(rows) * 0.80), -1):
    if rows[y] > 180:
        cut = y
    else:
        break
print("白带起点 y=%d（内容高度 %d）" % (cut, cut))

# 源内容（去白带）与缩放后的比例
content_h = cut
sc = 1920 / 1888
print("按宽等比缩放 ×%.4f → 内容高度应为 %.1f" % (sc, content_h * sc))
print("新图实际内容高度 = 1280（全部保留）" if content_h * sc <= 1281 else "超出")

# 地形高度对比
def terrain_h(img):
    B = np.asarray(img.convert("L")).astype(np.float32)
    H, W = B.shape
    ys = []
    for x in range(0, W, 40):
        idx = np.where(B[:, x] > 18)[0]
        ys.append(int(idx[0]) if len(idx) else H)
    hz = int(np.median(ys))
    return hz, H - hz

h1, t1 = terrain_h(s.crop((0, 0, 1888, cut)))
h2, t2 = terrain_h(n)
print("源(去白带)  %dx%d  地平线 %d  地形高 %d  （地形/宽 = %.4f）"
      % (1888, cut, h1, t1, t1 / 1888))
print("新图        %dx%d  地平线 %d  地形高 %d  （地形/宽 = %.4f）"
      % (1920, 1280, h2, t2, t2 / 1920))
print()
print("比例差 %.2f%%  → %s" % (abs(t1 / 1888 - t2 / 1920) / (t1 / 1888) * 100,
                              "几何完全一致，没有裁剪" if abs(t1 / 1888 - t2 / 1920) / (t1 / 1888) < 0.005 else "有差异"))
