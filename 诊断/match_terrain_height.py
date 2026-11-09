"""match_terrain_height.py —— 把两张新图的「月面高度」拉齐到 moon_base_长影.png

用户观察：中影图的月面被压扁了（比长影矮）。
做法：纵向按比例拉伸，使地形高度 = 长影的地形高度；画布仍 1920×1280，差额从太空扣。
"""
import numpy as np
from PIL import Image

AST = r"E:\DeskTop\地球\素材"
REF = AST + r"\moon_base_长影.png"
FILES = [("中影", r"E:\DeskTop\影子图\中影图.png"),
         ("短影", r"E:\DeskTop\影子图\短影图.png")]
TW, TH = 1920, 1280


def horizon_median(A):
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


ref = np.asarray(Image.open(REF).convert("L")).astype(np.float32)
HZ_REF = horizon_median(ref)
TERR_REF = ref.shape[0] - HZ_REF
print("参照 长影: %dx%d  地平线 %d  地形高 %d" % (ref.shape[1], ref.shape[0], HZ_REF, TERR_REF))

for name, p in FILES:
    im = Image.open(p).convert("RGB")
    W0, H0 = im.size
    A = np.asarray(im).astype(np.float32)
    rows = A.mean(2).mean(1)
    cut = H0
    for y in range(H0 - 1, int(H0 * 0.80), -1):
        if rows[y] > 180:
            cut = y
        else:
            break
    A = A[:cut]
    h1, w1 = A.shape[:2]
    hz = horizon_median(A.mean(2))
    terr = h1 - hz
    sy = TERR_REF / terr
    print("[%s] 裁白带后 %dx%d  地平线 %d  地形高 %d  → 纵向拉伸 ×%.4f"
          % (name, w1, h1, hz, terr, sy))

    # 天空刷黑
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

    # 缩放：宽→1920，高按 sy
    nh = round(h1 * sy)
    img = Image.fromarray(np.clip(A, 0, 255).astype(np.uint8)).resize((TW, nh), Image.LANCZOS)
    hz_new = hz * sy
    print("   缩放后 1920x%d   地平线应为 %.0f" % (nh, hz_new))

    # 对齐地平线到 HZ_REF，多余的从顶部裁（或补）
    canvas = np.zeros((TH, TW, 3), dtype=np.float32)
    S = np.asarray(img).astype(np.float32)
    shift = HZ_REF - hz_new          # >0 往下挪；<0 往上挪
    if shift >= 0:
        shift = int(round(shift))
        paste_h = min(nh, TH - shift)
        canvas[shift:shift + paste_h] = S[:paste_h]
        print("   顶部补 %dpx 太空" % shift)
    else:
        skip = int(round(-shift))
        paste_h = min(nh - skip, TH)
        canvas[:paste_h] = S[skip:skip + paste_h]
        print("   顶部裁掉 %dpx 太空" % skip)

    out = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
    out.save(AST + r"\moon_base_%s.png" % name)
    out.transpose(Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_%s_mirror.png" % name)

    B = np.asarray(out.convert("L")).astype(np.float32)
    hz_f = horizon_median(B)
    print("   复查 %dx%d  地平线 %d  地形高 %d  （参照 %d）"
          % (TW, TH, hz_f, TH - hz_f, TERR_REF))
