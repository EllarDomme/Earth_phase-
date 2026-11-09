"""probe_newbase.py —— 评估豆包新做的"中影"底图"""
import numpy as np
from PIL import Image

NEW = r"C:\Users\34684\.dsh\attachments\v1\objects\74\74673ca6dc541d16f3b066acb30b4331b6831fb2070bcd4a4434496e22688169"
OLD = r"E:\DeskTop\地球\素材\moon_base_v2.png"

for name, p in (("新（中影）", NEW), ("现有 v2", OLD)):
    im = Image.open(p).convert("RGB")
    A = np.asarray(im).astype(np.float32)
    H, W = A.shape[:2]
    L = A.mean(2)
    print("== %s  %dx%d" % (name, W, H))
    print("   顶部 20 行   %s" % np.round(A[:20].mean((0, 1)), 1))
    print("   左上角 60x60 %s" % np.round(A[:60, :60].mean((0, 1)), 1))
    print("   右下角 120x80 %s" % np.round(A[-80:, -120:].mean((0, 1)), 1))

    # 地平线
    ys = []
    for x in range(0, W, 40):
        idx = np.where(L[:, x] > 18)[0]
        ys.append(int(idx[0]) if len(idx) else H)
    print("   地平线 中位 %d  范围 %d~%d" % (int(np.median(ys)), min(ys), max(ys)))

    # 地形统计
    terr = L[int(H * 0.62):, :]
    terr = terr[terr > 3]
    p5, p50, p95 = np.percentile(terr, [5, 50, 95])
    print("   地形 p5=%.0f p50=%.0f p95=%.0f  阴影深度 %.1f" % (p5, p50, p95, p95 / max(p5, 1e-6)))

    # 水印检查（右下角是否有很亮的字）
    sub = L[int(H * 0.90):, int(W * 0.82):]
    print("   右下角 >190 亮像素 %d" % int((sub > 190).sum()))
    print()
