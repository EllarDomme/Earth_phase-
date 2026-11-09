"""final_three.py —— 三张底图最终核对"""
import numpy as np
from PIL import Image

AST = r"E:\DeskTop\地球\素材"
BASES = [("无影", AST + r"\moon_base_无影.png"),
         ("中影", AST + r"\moon_base_中影.png"),
         ("长影", AST + r"\moon_base_v2.png")]


def stats(p):
    A = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    H, W = A.shape
    hor = np.full(W, H, dtype=np.int32)
    for x in range(W):
        idx = np.where(A[:, x] > 12)[0]
        hor[x] = int(idx[0]) if len(idx) else H
    k = 21
    pd = np.pad(hor, (k // 2, k // 2), mode="edge")
    hor = np.array([pd[i:i + k].min() for i in range(W)], dtype=np.int32)
    t = A[int(H * 0.70):, :]
    t = t[t > 3]
    med = np.median(t)
    sh = float((t < med * 0.85).mean() * 100)
    return W, H, int(np.median(hor)), med, sh


print("%-6s %-12s %-9s %-9s %-9s" % ("底图", "尺寸", "地平线", "中位亮度", "影子占比"))
for name, p in BASES:
    W, H, hz, med, sh = stats(p)
    print("%-6s %-12s %-9d %-9.0f %-9.1f%%" % (name, "%dx%d" % (W, H), hz, med, sh))

print()
print("相位分配：")
print("  < 20%   无影（亮）")
print("  20~35%  中影")
print("  35~55%  长影")
print("  > 55%   无影（压暗 0.18~0.22）")
