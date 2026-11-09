"""align_new_bases.py —— 去掉白带，尺寸与地平线全部对齐 moon_base_长影.png"""
import numpy as np
from PIL import Image

AST = r"E:\DeskTop\地球\素材"
REF = AST + r"\moon_base_长影.png"
FILES = [("中影", r"E:\DeskTop\影子图\中影图.png", r"E:\DeskTop\影子图\短影图.png")]


def horizon_of(A):
    H, W = A.shape
    L = A
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
    k = 21
    pd = np.pad(hor, (k // 2, k // 2), mode="edge")
    hor = np.array([pd[i:i + k].min() for i in range(W)], dtype=np.int32)
    return int(np.median(hor))


ref = np.asarray(Image.open(REF).convert("RGB")).astype(np.float32)
H_T = horizon_of(ref.mean(2))
print("参照 moon_base_长影.png: %dx%d  地平线 %d" % (ref.shape[1], ref.shape[0], H_T))


def process(src_path, name):
    im = Image.open(src_path).convert("RGB")
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
    h1 = A.shape[0]
    print("  [%s] 原图 %dx%d  裁白带 %dpx → %dx%d" % (name, W0, H0, H0 - cut, W0, h1))

    # ② 天空刷纯黑
    hor_now = horizon_of(A.mean(2))
    yy = np.arange(h1)[:, None]
    alpha = np.clip((np.full((1, W0), hor_now) + 1 - yy) / 4.0, 0, 1)[..., None]
    A = A * (1 - alpha)

    # ③ 等比缩放到宽 1920
    sc = 1920 / W0
    nh = round(h1 * sc)
    img = Image.fromarray(np.clip(A, 0, 255).astype(np.uint8)).resize((1920, nh), Image.LANCZOS)
    hz2 = round(hor_now * sc)
    print("     缩放 ×%.4f → 1920x%d  地平线 %.0f→%d" % (sc, nh, hor_now, hz2))

    # ④ 放到 1920x1280 画布，使地平线落在 H_T
    offset = H_T - hz2                    # 正数=图往下挪（顶部补黑）
    canvas = np.zeros((1280, 1920, 3), dtype=np.float32)
    src = np.asarray(img).astype(np.float32)
    if offset >= 0:
        paste_h = min(nh, 1280 - offset)
        canvas[offset:offset + paste_h] = src[:paste_h]
    else:
        # 需要上移：裁掉顶部
        skip = -offset
        paste_h = min(nh - skip, 1280)
        canvas[:paste_h] = src[skip:skip + paste_h]
    print("     地平线对齐：偏移 %+d px → 地平线 %d" % (offset, H_T))

    out = canvas
    p = AST + r"\moon_base_%s.png" % name
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(p)
    Image.open(p).transpose(Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_%s_mirror.png" % name)

    # 复查
    B = out.mean(2)
    t = B[900:]
    t = t[t > 3]
    print("     复查 %dx1280  顶部20行 %.1f  地形中位 %.0f  影子占比 %.1f%%"
          % (1920, B[:20].mean(), np.median(t),
             float((t < np.median(t) * 0.85).mean() * 100)))
    return p


for name, mid_p, short_p in FILES:
    process(mid_p, "中影")
    process(short_p, "短影")
