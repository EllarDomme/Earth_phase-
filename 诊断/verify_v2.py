"""verify_v2.py —— 用"与原始图对比"的办法，确认 v2 有没有几何变形"""
import numpy as np
from PIL import Image

SRC = r"C:\Users\34684\.dsh\attachments\v1\objects\a6\a6c39a0d5bbb63bc28c16a63d3e1e23ea5f552883d69d74b6a5dac628293710c"
V2 = r"E:\DeskTop\地球\素材\moon_base_v2.png"

a = Image.open(SRC).convert("RGB")
b = Image.open(V2).convert("RGB")
print("原始 %s   v2 %s" % (a.size, b.size))

if a.size == b.size:
    A = np.asarray(a).astype(np.float32)
    B = np.asarray(b).astype(np.float32)
    # 地形区（下半部）
    ya = int(a.size[1] * 0.70)
    ca = A[ya:].mean(2)
    cb = B[ya:].mean(2)
    m = (ca > 3) & (cb > 3)
    if m.sum() > 1000:
        corr = np.corrcoef(ca[m], cb[m])[0, 1]
        mad = float(np.abs(ca[m] - cb[m]).mean())
        # 平移 1px 后的相关（若被拉伸，位移相关会明显低）
        cb_s = np.roll(cb, 1, axis=0)
        corr2 = np.corrcoef(ca[m], cb_s[m])[0, 1]
        print("地形区：相关 %.6f   平均差 %.3f   竖直位移1px相关 %.6f" % (corr, mad, corr2))
        print("结论：%s" % ("几何完全一致（未拉伸）" if corr > 0.999 else "有差异，需检查"))
    else:
        print("地形像素太少，换区域")
else:
    print("尺寸不同 → 做过缩放，需要检查是否等比")
    sx = b.size[0] / a.size[0]
    sy = b.size[1] / a.size[1]
    print("  横向缩放 %.4f   纵向缩放 %.4f   差 %.2f%%" % (sx, sy, abs(sx - sy) / sx * 100))
