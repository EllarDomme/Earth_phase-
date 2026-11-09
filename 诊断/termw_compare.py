"""termw_compare.py —— 零额度：只改晨昏线宽度，重打光并裁同一块对比"""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
import lighting  # noqa: E402

PRE = r"E:\DeskTop\地球\v2\_bak_uni_2006-04-05_月面_提升_1920x1280.png"
DATE, UTC = "2006-04-05", 7.75
BOX = (900, 30, 1040, 300)

im = Image.open(PRE).convert("RGB")
outs = []
for tw in (0.08, 0.12, 0.16):
    o = lighting.apply_lighting(im, DATE, UTC, verbose=False, term_w=tw)
    outs.append((tw, o))
    o.crop(BOX).resize((280, 540), Image.LANCZOS).save(
        r"E:\DeskTop\草稿\_tw_%02d.png" % int(tw * 100))

c = Image.new("RGB", (280 * 3 + 20, 570), (12, 12, 12))
from PIL import ImageDraw, ImageFont  # noqa: E402
f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 22)
d = ImageDraw.Draw(c)
for i, (tw, _) in enumerate(outs):
    x = i * (280 + 10)
    c.paste(Image.open(r"E:\DeskTop\草稿\_tw_%02d.png" % int(tw * 100)), (x, 30))
    d.text((x + 6, 4), "term_w = %.2f" % tw, font=f, fill=(160, 220, 255))
c.save(r"E:\DeskTop\草稿\晨昏线宽度对比.png")
print("已生成对比图")
