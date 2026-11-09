"""edge_straightness.py —— 判断那条竖直边是纹理还是合成边界

原理：纹理边缘逐行位置会抖动；合成边界逐行位置几乎不变（±1px）。
"""
import numpy as np
from PIL import Image

PRE = r"E:\DeskTop\地球\v2\_bak_uni_2006-04-05_月面_提升_1920x1280.png"
A = np.asarray(Image.open(PRE).convert("L")).astype(np.float32)

xs = []
for y in range(70, 250):
    row = A[y, 940:1000]
    if row.max() - row.min() < 8:
        continue
    # 平滑后取梯度最大处
    k = np.ones(3) / 3
    sm = np.convolve(row, k, mode="same")
    g = np.abs(np.diff(sm))
    xs.append((y, 940 + int(np.argmax(g))))

if not xs:
    print("没有梯度明显的行")
else:
    arr = np.array([x for _, x in xs])
    print("竖直边逐行位置：共 %d 行" % len(xs))
    print("  位置 中位 %d  标准差 %.2f  范围 %d~%d"
          % (int(np.median(arr)), arr.std(), arr.min(), arr.max()))
    vals, cnts = np.unique(arr, return_counts=True)
    print("  出现最多的列：", [(int(v), int(c)) for v, c in zip(vals, cnts)][:6])
    # 直方图集中度
    top = cnts.max() / len(arr)
    print("  最集中一列占 %.0f%%" % (top * 100))
    print()
    print("判定：%s" % ("⚠ 近乎笔直 → 可能是合成/重绘边界"
                     if arr.std() < 2.0 and top > 0.4 else
                     "✓ 位置抖动 → 是自然纹理边缘"))
    print("  前 20 行样本:", xs[:20])
