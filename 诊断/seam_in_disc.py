"""seam_in_disc.py —— 在 1536 圆盘底图里找竖直接缝"""
import numpy as np
from PIL import Image

DISC = r"E:\DeskTop\地球\v2\_bak_uni_2006-04-05_地球相_2048.png"
A = np.asarray(Image.open(DISC).convert("L")).astype(np.float32)
H, W = A.shape
print("底图 %dx%d" % (W, H))

# 只看上半部（北极带），行均值对每列
band = A[300:900, :]
col = band.mean(0)
# 用 31px 滑动中值去掉大尺度趋势
from statistics import median
trend = np.array([median(col[max(0, i - 15):i + 16]) for i in range(len(col))])
res = col - trend
print("列残差 标准差 %.3f" % res.std())

order = np.argsort(-np.abs(res))[:10]
print("残差最大的 10 列：")
for i in order:
    print("   x=%4d  残差 %+.2f" % (i, res[i]))

# 找"单列或双列"的突变（接缝特征：相邻列差异大，远处平坦）
d = np.diff(col)
order2 = np.argsort(-np.abs(d))[:10]
print()
print("列间最大跳变（接缝最可能在这里）：")
for i in order2:
    print("   x=%4d→%4d  跳变 %+.2f" % (i, i + 1, d[i]))
