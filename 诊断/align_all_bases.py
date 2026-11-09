"""align_all_bases.py —— 四张底图的地形高度全部对齐（504px），并重做镜像"""
import numpy as np
from PIL import Image

AST = r"E:\DeskTop\地球\素材"
NAMES = ["无影", "短影", "中影", "长影"]
TW, TH = 1920, 1280
TERR_T, HZ_T = 504, 776          # 目标（以长影为参照）


def measure(A):
    H, W = A.shape
    win = 9
    cs = np.cumsum(np.vstack([np.zeros((1, W)), A]), 0)
    cs2 = np.cumsum(np.vstack([np.zeros((1, W)), A * A]), 0)
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
    hz = int(np.median(hor))
    return hz, H - hz


for name in NAMES:
    p = AST + r"\moon_base_%s.png" % name
    im = Image.open(p).convert("RGB")
    A = np.asarray(im).astype(np.float32)
    hz, terr = measure(A.mean(2))
    sy = TERR_T / terr
    print("[%s] 现 %dx%d  地平线 %d  地形高 %d  → 纵向 ×%.4f"
          % (name, im.size[0], im.size[1], hz, terr, sy))

    if abs(sy - 1.0) < 0.002:
        print("   已对齐，跳过")
        Image.fromarray(np.clip(A, 0, 255).astype(np.uint8)).transpose(
            Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_%s_mirror.png" % name)
        continue

    nh = round(TH * sy)
    img = Image.fromarray(np.clip(A, 0, 255).astype(np.uint8)).resize((TW, nh), Image.LANCZOS)
    S = np.asarray(img).astype(np.float32)
    hz_new = hz * sy
    shift = HZ_T - hz_new

    canvas = np.zeros((TH, TW, 3), dtype=np.float32)
    if shift >= 0:
        s = int(round(shift))
        paste_h = min(nh, TH - s)
        canvas[s:s + paste_h] = S[:paste_h]
        note = "顶部补 %dpx 太空" % s
    else:
        s = int(round(-shift))
        paste_h = min(nh - s, TH)
        canvas[:paste_h] = S[s:s + paste_h]
        note = "顶部裁 %dpx 太空" % s

    out = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
    out.save(p)
    out.transpose(Image.FLIP_LEFT_RIGHT).save(AST + r"\moon_base_%s_mirror.png" % name)

    hz2, terr2 = measure(canvas.mean(2))
    print("   %s  缩放后 %dx%d → 复查 地平线 %d 地形高 %d"
          % (note, TW, nh, hz2, terr2))

print()
print("=== 最终核对（含镜像）===")
for name in NAMES:
    for suf in ("", "_mirror"):
        p = AST + r"\moon_base_%s%s.png" % (name, suf)
        B = np.asarray(Image.open(p).convert("L")).astype(np.float32)
        hz, terr = measure(B)
        print("  %-14s %dx%d  地平线 %d  地形高 %d" % (name + suf, B.shape[1], B.shape[0], hz, terr))
