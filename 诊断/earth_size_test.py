"""earth_size_test.py —— 两种地球尺寸对比（零额度）"""
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"E:\DeskTop\地球")

R_EARTH = 6371.0
D_MOON = 384400.0
ANG = 2 * math.degrees(math.atan(R_EARTH / D_MOON))
FOV = 40.0
PCT_TRUE = ANG / FOV
PCT_ART = 0.36

print("地球角直径 %.3f°" % ANG)
print("视场 %.0f°  ->  真实占比 %.4f（%.0f px @1920）" % (FOV, PCT_TRUE, PCT_TRUE * 1920))
print("现在（艺术）  %.2f（%.0f px）" % (PCT_ART, PCT_ART * 1920))
print("倍率差 %.1f 倍" % (PCT_ART / PCT_TRUE))

DISC = r"E:\DeskTop\地球\v2\_bak_uni_2008-10-26_地球相_2048.png"
BASE = r"E:\DeskTop\地球\素材\moon_base_无影.png"
HZ = 761
GAP = 20
OUT = r"E:\DeskTop\草稿"


def compose(pct, tag):
    W, H = 1920, 1280
    base = Image.open(BASE).convert("RGB")
    # 按夜面档压暗（92% 相位）
    a = np.asarray(base).astype(np.float32) * 0.65 * 0.18
    lum = a.mean(2)
    m = lum > 1
    if m.any():
        med = float(np.median(lum[m]))
        a[m] = np.clip(med + (a[m] - med) * 4.0, 0, 255)
    base = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    earth = Image.open(DISC).convert("RGB")
    D = int(W * pct)
    earth = earth.resize((D, D), Image.LANCZOS)
    cx = W // 2
    cy = HZ - GAP - D // 2
    _mask = Image.new("L", (D, D), 0)
    ImageDraw.Draw(_mask).ellipse([0, 0, D - 1, D - 1], fill=255)
    base.paste(earth, (cx - D // 2, cy - D // 2), _mask)
    import lighting
    out = lighting.apply_lighting(base, "2008-10-26", 4.0, verbose=False)
    p = "%s\\_size_%s.png" % (OUT, tag)
    out.save(p)
    return p, D


p1, d1 = compose(PCT_ART, "art")
p2, d2 = compose(PCT_TRUE, "true")
print("艺术版 直径 %d px  真实版 直径 %d px" % (d1, d2))

f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 26)
S = (860, 573)
c = Image.new("RGB", (S[0], (S[1] + 40) * 2), (10, 10, 10))
d = ImageDraw.Draw(c)
for i, (t, p) in enumerate((("① 现状：占画宽 36%%（艺术压缩，相当于 400mm 长焦）", p1),
                            ("② 真实：角直径 1.9°，40° 视场下占 4.75%", p2))):
    y = i * (S[1] + 40) + 34
    c.paste(Image.open(p).resize(S, Image.LANCZOS), (0, y))
    d.text((8, y - 30), t, font=f, fill=(150, 210, 255))
c.save(OUT + r"\地球尺寸两模式.png")
print("对比图：", OUT + r"\地球尺寸两模式.png")
