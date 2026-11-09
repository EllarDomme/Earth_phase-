"""rebuild_exact.py —— 严格按要求：裁白边 → 不缩放 → 太空背景补齐尺寸

源图 1888×1344，白带在底部（约 87px）
裁掉后 1888×1257
放进 1920×1280 的黑画布：
   顶部补 23px 太空
   左右各补 16px 太空
月面 1:1 保留，不缩放、不裁切
"""
import numpy as np
from PIL import Image

AST = r"E:\DeskTop\地球\素材"
FILES = [("中影", r"E:\DeskTop\影子图\中影图.png"),
         ("短影", r"E:\DeskTop\影子图\短影图.png")]
TARGET = (1920, 1280)

for name, p in FILES:
    im = Image.open(p).convert("RGB")
    W0, H0 = im.size
    A = np.asarray(im).astype(np.float32)
    L = A.mean(2)

    # ① 找底部白带
    rows = L.mean(1)
    cut = H0
    for y in range(H0 - 1, int(H0 * 0.80), -1):
        if rows[y] > 180:
            cut = y
        else:
            break
    A = A[:cut]
    h1, w1 = A.shape[:2]
    print("[%s] %dx%d → 裁白带 %dpx → %dx%d" % (name, W0, H0, H0 - cut, w1, h1))

    if w1 > TARGET[0] or h1 > TARGET[1]:
        print("   内容比目标大，需要裁（本不该发生）")
        A = A[:TARGET[1], :TARGET[0]]
        h1, w1 = A.shape[:2]

    # ② 天空刷纯黑（保持纯净）
    hor = np.full(w1, h1, dtype=np.int32)
    L2 = A.mean(2)
    for x in range(w1):
        idx = np.where(L2[:, x] > 12)[0]
        hor[x] = int(idx[0]) if len(idx) else h1
    k = 21
    pd = np.pad(hor, (k // 2, k // 2), mode="edge")
    hor = np.array([pd[i:i + k].min() for i in range(w1)], dtype=np.int32)
    yy = np.arange(h1)[:, None]
    alpha = np.clip((hor[None, :] + 1 - yy) / 4.0, 0, 1)[..., None]
    A = A * (1 - alpha)

    # ③ 放进黑画布：底部对齐、水平居中
    TW, TH = TARGET
    canvas = np.zeros((TH, TW, 3), dtype=np.float32)
    ox = (TW - w1) // 2
    oy = TH - h1
    canvas[oy:oy + h1, ox:ox + w1] = A
    print("   放入 %dx%d：偏移 x=%d, y=%d（顶部补 %dpx, 左右各补 %dpx）"
          % (TW, TH, ox, oy, oy, ox))

    out = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
    out.save(AST + r"\moon_base_%s.png" % name)
    out.transpose(Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_%s_mirror.png" % name)

    B = np.asarray(out.convert("L")).astype(np.float32)
    ys = []
    for x in range(0, TW, 40):
        idx = np.where(B[:, x] > 18)[0]
        ys.append(int(idx[0]) if len(idx) else TH)
    print("   复查：%dx%d  顶部20行 %.1f  地平线 中位 %d" % (TW, TH, B[:20].mean(), int(np.median(ys))))
