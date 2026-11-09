"""find_line2.py —— 逐行找窄凹，按列计票，定位竖直线"""
import numpy as np
from PIL import Image

POST = r"E:\DeskTop\地球\成品\2006-04-05_月面_提升_1920x1280.png"
PRE = r"E:\DeskTop\地球\v2\_bak_uni_2006-04-05_月面_提升_1920x1280.png"


def detect(path, tag, y0=70, y1=260, x0=940, x1=1040, depth=2.0):
    A = np.asarray(Image.open(path).convert("L")).astype(np.float32)
    votes = np.zeros(x1 - x0)
    for y in range(y0, y1):
        row = A[y, x0:x1]
        # 平滑 3px 去掉单像素噪声
        k = np.ones(3) / 3.0
        sm = np.convolve(row, k, mode="same")
        for i in range(3, len(sm) - 3):
            if (sm[i] < sm[i - 1] - depth / 2 and sm[i] < sm[i + 1] - depth / 2
                    and sm[i] < sm[i - 3] - depth and sm[i] < sm[i + 3] - depth):
                votes[i] += 1
    order = np.argsort(-votes)[:6]
    print("%s：逐行窄凹计票（前 6 列）" % tag)
    for i in order:
        print("   x=%d  命中 %d 行" % (x0 + i, int(votes[i])))
    return votes


v1 = detect(POST, "成品（打光后）")
print()
v2 = detect(PRE, "打光前")
print()
print("判定：若某列命中 >50%% 的行 → 存在连续竖直暗线")
print("  成品最高命中率 %.0f%%   打光前最高 %.0f%%"
      % (100.0 * v1.max() / 190, 100.0 * v2.max() / 190))
