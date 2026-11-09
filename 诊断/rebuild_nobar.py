"""rebuild_nobar.py —— 不加黑边：白边裁掉 → 宽度拉到 1920（纵向不变）→ 顶部补太空

纵向 1257px 保持 1:1（不缩放、不裁切）
横向 1888 → 1920，只拉宽 1.7%（肉眼几乎看不出）
顶部补 23px 纯黑太空，补足 1280
"""
import numpy as np
from PIL import Image

AST = r"E:\DeskTop\地球\素材"
FILES = [("中影", r"E:\DeskTop\影子图\中影图.png"),
         ("短影", r"E:\DeskTop\影子图\短影图.png")]
TW, TH = 1920, 1280

for name, p in FILES:
    im = Image.open(p).convert("RGB")
    W0, H0 = im.size
    A = np.asarray(im).astype(np.float32)
    L = A.mean(2)

    # ① 裁底部白带
    rows = L.mean(1)
    cut = H0
    for y in range(H0 - 1, int(H0 * 0.80), -1):
        if rows[y] > 180:
            cut = y
        else:
            break
    A = A[:cut]
    h1, w1 = A.shape[:2]
    print("[%s] %dx%d → 裁白带 → %dx%d" % (name, W0, H0, w1, h1))

    # ② 天空刷纯黑
    L2 = A.mean(2)
    hor = np.full(w1, h1, dtype=np.int32)
    for x in range(w1):
        idx = np.where(L2[:, x] > 12)[0]
        hor[x] = int(idx[0]) if len(idx) else h1
    k = 21
    pd = np.pad(hor, (k // 2, k // 2), mode="edge")
    hor = np.array([pd[i:i + k].min() for i in range(w1)], dtype=np.int32)
    yy = np.arange(h1)[:, None]
    alpha = np.clip((hor[None, :] + 1 - yy) / 4.0, 0, 1)[..., None]
    A = A * (1 - alpha)

    # ③ 只横向拉伸到 1920（纵向像素数不变）
    img = Image.fromarray(np.clip(A, 0, 255).astype(np.uint8)).resize((TW, h1), Image.LANCZOS)
    S = np.asarray(img).astype(np.float32)
    print("   横向 1888→1920（×%.4f）  纵向保持 %d（1:1）" % (TW / w1, h1))

    # ④ 顶部补太空
    add = TH - h1
    canvas = np.zeros((TH, TW, 3), dtype=np.float32)
    canvas[add:] = S
    print("   顶部补 %dpx 纯黑太空 → %dx%d" % (add, TW, TH))

    out = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
    out.save(AST + r"\moon_base_%s.png" % name)
    out.transpose(Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_%s_mirror.png" % name)

    B = np.asarray(out.convert("L")).astype(np.float32)
    ys = []
    for x in range(0, TW, 40):
        idx = np.where(B[:, x] > 18)[0]
        ys.append(int(idx[0]) if len(idx) else TH)
    print("   复查：%dx%d  顶部20行 %.1f  地平线 %d  左右边缘亮度 %.1f/%.1f"
          % (TW, TH, B[:20].mean(), int(np.median(ys)), B[1000, :8].mean(), B[1000, -8:].mean()))
