"""build_base.py —— 一步到位：去太阳光晕 → 天空刷纯黑 → 去水印（扩散修补）

素材：用户提供的 1920x1280 月面图（带太阳光晕 + 豆包水印）
目标：天空与旧素材一致（纯黑 0,0,0），水印消失且看不出补丁
"""
import numpy as np
from PIL import Image

SRC = r"C:\Users\34684\.dsh\attachments\v1\objects\a6\a6c39a0d5bbb63bc28c16a63d3e1e23ea5f552883d69d74b6a5dac628293710c"
OUT = r"E:\DeskTop\地球\素材\moon_base_v2.png"
DBG_MASK = r"E:\DeskTop\地球\v2\wm_mask.png"

im = Image.open(SRC).convert("RGB")
A = np.asarray(im).astype(np.float32)
H, W = A.shape[:2]
L = A.mean(2)

# ── ① 地平线：局部标准差（地形粗糙、天空/光晕平滑）
win = 9
cs = np.cumsum(np.vstack([np.zeros((1, W)), L]), 0)
cs2 = np.cumsum(np.vstack([np.zeros((1, W)), L * L]), 0)
horizon = np.full(W, H, dtype=np.int32)
y_start = int(H * 0.35)
for x in range(W):
    run = 0
    for y in range(y_start, H - win):
        s1 = cs[y + win, x] - cs[y, x]
        s2 = cs2[y + win, x] - cs2[y, x]
        m = s1 / win
        sd = np.sqrt(max(s2 / win - m * m, 0))
        if sd > 4.0:
            run += 1
            if run >= 12:
                horizon[x] = y - 11
                break
        else:
            run = 0
k = 21
pad = np.pad(horizon, (k // 2, k // 2), mode="edge")
horizon = np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)
print("地平线 %d~%d（旧素材 755~810）" % (horizon.min(), horizon.max()))

# ── ② 天空刷纯黑（羽化 4px）
yy = np.arange(H)[:, None]
alpha = np.clip((horizon[None, :] + 1 - yy) / 4.0, 0, 1)[..., None]
out = A * (1 - alpha)

# ── ③ 水印：在【原始图】上找白字（此时还没被任何东西覆盖）
x0, y0 = int(W * 0.84), int(H * 0.92)
sub = L[y0:, x0:]
mk = sub > 190
print("白字像素 %d" % int(mk.sum()))
if mk.sum() >= 20:
    ys, xs = np.where(mk)
    Y0, Y1 = int(ys.min()) + y0, int(ys.max()) + y0
    X0, X1 = int(xs.min()) + x0, int(xs.max()) + x0
    print("白字范围 x %d~%d  y %d~%d" % (X0, X1, Y0, Y1))
    P = 10
    X0, X1 = max(0, X0 - P), min(W, X1 + P)
    Y0, Y1 = max(0, Y0 - P), min(H, Y1 + P)
    # ★ 整块矩形全遮蔽：水印是半透明的，只遮亮笔画会留重影和光晕
    mask = np.ones((Y1 - Y0, X1 - X0), dtype=bool)

    dbg = np.asarray(Image.open(SRC).convert("RGB")).copy()
    dbg[Y0:Y1, X0:X1][mask] = [255, 40, 40]
    Image.fromarray(dbg).save(DBG_MASK)

    patch = out[Y0:Y1, X0:X1].copy()
    h, w = mask.shape
    work = patch.copy()
    for c in range(3):
        ch = work[..., c]
        for _ in range(600):
            up = np.roll(ch, 1, 0); up[0] = ch[0]
            dn = np.roll(ch, -1, 0); dn[-1] = ch[-1]
            lf = np.roll(ch, 1, 1); lf[:, 0] = ch[:, 0]
            rt = np.roll(ch, -1, 1); rt[:, -1] = ch[:, -1]
            ch = np.where(mask, (up + dn + lf + rt) / 4.0, ch)
        work[..., c] = ch

    ring = np.zeros_like(mask)
    for _ in range(8):
        r = ring.copy()
        r[1:, :] |= mask[:-1, :] | ring[:-1, :]
        r[:-1, :] |= mask[1:, :] | ring[1:, :]
        r[:, 1:] |= mask[:, :-1] | ring[:, :-1]
        r[:, :-1] |= mask[:, 1:] | ring[:, 1:]
        ring = r & ~mask
    sigma = float(out[Y0:Y1, X0:X1].mean(2)[ring].std()) if ring.sum() > 50 else 5.0
    rng = np.random.default_rng(11)
    work = np.clip(work + rng.normal(0, sigma * 0.35, (h, w, 1)) * mask[..., None], 0, 255)
    patch[mask] = work[mask]
    out[Y0:Y1, X0:X1] = patch
    print("水印已整块扩散修补（噪声σ=%.1f）" % sigma)

Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(OUT)
B = np.asarray(Image.open(OUT).convert("RGB")).astype(np.float32)
print("复查 顶部20行 %s  左上 %s  右上 %s"
      % (np.round(B[:20].mean((0, 1)), 1), np.round(B[:60, :60].mean((0, 1)), 1),
         np.round(B[:60, -60:].mean((0, 1)), 1)))
print("已保存:", OUT)
