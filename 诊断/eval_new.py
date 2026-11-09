"""eval_new.py —— 评估豆包新做的中影/短影两张图"""
import numpy as np
from PIL import Image

FILES = [("中影图", r"E:\DeskTop\影子图\中影图.png"),
         ("短影图", r"E:\DeskTop\影子图\短影图.png")]

for name, p in FILES:
    im = Image.open(p).convert("RGB")
    A = np.asarray(im).astype(np.float32)
    H, W = A.shape[:2]
    L = A.mean(2)
    print("== %s  %dx%d" % (name, W, H))
    print("   顶部20行 %s   左上角 %s" % (np.round(A[:20].mean((0, 1)), 1),
                                       np.round(A[:60, :60].mean((0, 1)), 1)))

    # 地平线（标准差法，避开亮天空）
    win = 9
    cs = np.cumsum(np.vstack([np.zeros((1, W)), L]), 0)
    cs2 = np.cumsum(np.vstack([np.zeros((1, W)), L * L]), 0)
    hor = np.full(W, H, dtype=np.int32)
    for x in range(W):
        run = 0
        for y in range(int(H * 0.30), H - win):
            s1 = cs[y + win, x] - cs[y, x]
            s2 = cs2[y + win, x] - cs2[y, x]
            m = s1 / win
            sd = np.sqrt(max(s2 / win - m * m, 0))
            if sd > 4.0:
                run += 1
                if run >= 12:
                    hor[x] = y - 11
                    break
            else:
                run = 0
    hz = int(np.median(hor))
    print("   地平线 中位 %d (%.1f%%)" % (hz, hz / H * 100))

    t = L[int(H * 0.70):, :]
    t = t[t > 3]
    med = np.median(t)
    sh = float((t < med * 0.85).mean() * 100)
    print("   地形 中位亮度 %.0f  影子占比 %.1f%%  p95/p5 %.1f"
          % (med, sh, np.percentile(t, 95) / max(np.percentile(t, 5), 1e-6)))

    # 水印/文字检查
    sub = L[int(H * 0.90):, int(W * 0.80):]
    print("   右下角 >190 亮像素 %d" % int((sub > 190).sum()))
    print()
