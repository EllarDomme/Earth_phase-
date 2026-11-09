"""make_bg_v2.py —— 新背景图：去太阳光晕 → 太空刷成旧素材的纯黑 → 补到 1920x1280

不裁掉地形、不拉伸地形：只按比例放大到宽 1920，再从【上方天空】裁到 1280 高。
"""
import numpy as np
from PIL import Image

NEW = r"E:\DeskTop\背景.png"
OLD = r"E:\DeskTop\地球\素材\moon_base.png"
OUT = r"E:\DeskTop\地球\素材\moon_base_v2.png"

# 旧素材的太空色（作为目标）
oldA = np.asarray(Image.open(OLD).convert("RGB")).astype(np.float32)
sky_target = oldA[:40].reshape(-1, 3).mean(0)
print("旧素材太空色: %s" % np.round(sky_target, 2))

im = Image.open(NEW).convert("RGB")
A = np.asarray(im).astype(np.float32)
H, W = A.shape[:2]
L = A.mean(2)
print("原图 %dx%d" % (W, H))

# ① 地平线：局部标准差（地形粗糙，天空/光晕平滑）
win = 9
cs = np.cumsum(np.vstack([np.zeros((1, W)), L]), 0)
cs2 = np.cumsum(np.vstack([np.zeros((1, W)), L * L]), 0)
horizon = np.full(W, H, dtype=np.int32)
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
                horizon[x] = y - 11
                break
        else:
            run = 0
k = 21
pad = np.pad(horizon, (k // 2, k // 2), mode="edge")
horizon = np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)
print("地平线 %d~%d（中位 %d）" % (horizon.min(), horizon.max(), int(np.median(horizon))))

# ② 检查天空光晕是否溢到地形（对比地平线上下 30 行的亮度）
y_med = int(np.median(horizon))
above = L[y_med - 40:y_med - 5].mean()
below = L[y_med + 5:y_med + 40].mean()
print("地平线上方 %.1f / 下方 %.1f" % (above, below))

# ③ 天空刷成旧素材的颜色（= 去掉太阳光晕）
yy = np.arange(H)[:, None]
alpha = np.clip((horizon[None, :] + 1 - yy) / 4.0, 0, 1)[..., None]
out = A * (1 - alpha) + sky_target[None, None, :] * alpha

# ④ 放大到宽 1920（等比例），再从上方裁到 1280
img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
new_h = round(H * 1920 / W)
img = img.resize((1920, new_h), Image.LANCZOS)
print("放大到 1920x%d（等比例）" % new_h)
if new_h > 1280:
    cut = new_h - 1280
    img = img.crop((0, cut, 1920, new_h))     # 从上方裁掉天空
    print("从上方裁掉 %dpx 天空 → 1920x1280" % cut)
elif new_h < 1280:
    canvas = Image.new("RGB", (1920, 1280), tuple(int(v) for v in sky_target))
    canvas.paste(img, (0, 1280 - new_h))
    img = canvas
    print("下方补天空 → 1920x1280")

img.save(OUT)

# ⑤ 复查
B = np.asarray(Image.open(OUT).convert("RGB")).astype(np.float32)
BL = B.mean(2)
ys = []
for x in range(0, 1920, 40):
    idx = np.where(BL[:, x] > 18)[0]
    ys.append(int(idx[0]) if len(idx) else 1280)
print("处理后: 顶部20行 %s  左上 %s  地平线 中位 %d  底部亮度 %.0f"
      % (np.round(B[:20].mean((0, 1)), 1), np.round(B[:60, :60].mean((0, 1)), 1),
         int(np.median(ys)), B[-50:].mean()))
# 水印复查：右下角有无很亮的字
sub = BL[int(1280 * 0.90):, int(1920 * 0.82):]
print("右下角 >190 亮像素: %d" % int((sub > 190).sum()))
print("已保存:", OUT)
