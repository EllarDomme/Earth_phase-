"""phase_terrain_demo.py —— 用新底图演示：不同相位下月面应该多暗

规则（由星历推出）：
  太阳高度 h = 90° − arccos(1 − 2k)      k = 地球相位
  h ≥ +6°   → 增益 1.00（白天长影）
  0 ~ +6°   → 1.00 → 0.15
  −6 ~ 0°   → 0.15 → 0.02
  h ≤ −6°   → 0.02 → 0.005（月夜，只剩地球照）
月夜同时：抬暗部（地球是大面光源，阴影浅）+ 轻微冷调
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
sys.path.insert(0, HERE)
import lighting  # noqa: E402

BASE = os.path.join(HERE, "素材", "moon_base_v2.png")
OUT = os.path.join(HERE, "v2")
CASES = [
    ("2021-06-25", 22.75, 0.02),
    ("2021-06-30", 22.75, 0.41),
    ("2002-10-01", 0.0, 0.63),
    ("2004-11-08", 1.25, 0.76),
    ("2008-10-26", 3.5, 0.92),
]


def sun_elev(k):
    cos_t = 1 - 2 * k
    return 90 - np.degrees(np.arccos(np.clip(cos_t, -1, 1)))


def gain_of(h):
    if h >= 6:
        return 1.0, 0.0
    if h >= 0:
        t = h / 6.0
        return 0.15 + (1.0 - 0.15) * t, 0.0
    if h >= -6:
        t = (h + 6) / 6.0
        return 0.02 + (0.15 - 0.02) * t, 0.0
    # 更深：0.02 → 0.005
    t = min(1.0, (-6 - h) / 54.0)
    return 0.02 * (1 - t) + 0.005 * t, 0.0


def horizon_of(path):
    A = np.asarray(Image.open(path).convert("L")).astype(np.float32)
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
    pad = np.pad(hor, (k // 2, k // 2), mode="edge")
    return np.array([pad[i:i + k].min() for i in range(W)], dtype=np.int32)


hor = horizon_of(BASE)
print("底图地平线 中位 %d" % int(np.median(hor)))

rows = []
for date, utc, k in CASES:
    src = os.path.join(OUT, "_bak_uni_%s_地球相_2048.png" % date)
    mid = os.path.join(OUT, "_demo_%s_c.png" % date)
    subprocess.run([sys.executable, os.path.join(HERE, "compose_moon.py"),
                    src, mid, "--base", BASE, "--date", date, "--utc", str(utc),
                    "--width", "1920", "--earth-pct", "0.36", "--moon-gain", "0.65",
                    "--sky-target", "1,1,1", "--earth-gamma", "1.0", "--earth-sat", "1.0"],
                   capture_output=True)

    im = Image.open(mid).convert("RGB")
    lit = lighting.apply_lighting(im, date, utc, verbose=False)
    A = np.asarray(lit).astype(np.float32)

    h = sun_elev(k)
    g, _ = gain_of(h)
    H, W = A.shape[:2]
    yy = np.arange(H)[:, None]
    terr = (yy > hor[None, :] + 2)[..., None]

    # 月夜：压暗 + 抬暗部（模拟头顶大面光源的平光）+ 轻微冷调
    if h < 0:
        # 月夜：只剩地球照 —— 整体压到极暗，再给一个很小的绝对底板
        # （地球是头顶的大面光源，阴影很浅，所以底板不能是 0，否则死黑没形状）
        float_floor = 1.8 if h > -20 else 1.2
        out = A * g + float_floor
        out[..., 0] *= 0.92                             # 轻微冷调（地球是蓝的）
        out[..., 2] *= 1.03
    else:
        out = A * g
    out = np.where(terr, np.clip(out, 0, 255), A)

    p = os.path.join(OUT, "_demo_%s.png" % date)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(p)

    t = out[terr[..., 0]]
    tl = t.mean(1)
    print("  %s  相位 %2.0f%%  太阳 %+5.1f°  增益 %.3f  地形均 %5.1f  p5 %4.1f  p95 %5.1f"
          % (date, k * 100, h, g, tl.mean(), np.percentile(tl, 5), np.percentile(tl, 95)))
    rows.append((date, k, h, g, p))

# 拼成对比条
ims = [Image.open(r[4]) for r in rows]
S = (600, 400)
sheet = Image.new("RGB", (S[0] * len(ims) + 8 * (len(ims) - 1), S[1]), (8, 8, 8))
for i, im in enumerate(ims):
    sheet.paste(im.resize(S, Image.LANCZOS), (i * (S[0] + 8), 0))
sp = os.path.join(OUT, "_demo_sheet.png")
sheet.save(sp)
print("对比条:", sp)
