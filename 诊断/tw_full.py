"""tw_full.py —— 用 term_w=0.08 / 0.12 各出一张整图，供上下对比"""
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"E:\DeskTop\地球")
import lighting  # noqa: E402

PRE = r"E:\DeskTop\地球\v2\_bak_uni_2006-04-05_月面_提升_1920x1280.png"
DATE, UTC = "2006-04-05", 7.75
im = Image.open(PRE).convert("RGB")

a = lighting.apply_lighting(im, DATE, UTC, verbose=False, term_w=0.08)
b = lighting.apply_lighting(im, DATE, UTC, verbose=False, term_w=0.12)
a.save(r"E:\DeskTop\草稿\_tw008_full.png")
b.save(r"E:\DeskTop\草稿\_tw012_full.png")

# 标注框对比
box = (900, 30, 1040, 300)
S = (280, 540)
f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 20)
c = Image.new("RGB", (S[0] * 2 + 12, S[1] + 30), (12, 12, 12))
d = ImageDraw.Draw(c)
for i, (t, img) in enumerate((("term_w=0.08（当前）", a), ("term_w=0.12（建议）", b))):
    x = i * (S[0] + 12)
    c.paste(img.crop(box).resize(S, Image.LANCZOS), (x, 28))
    d.text((x + 4, 4), t, font=f, fill=(160, 220, 255))
c.save(r"E:\DeskTop\草稿\橡皮筋_两版对比.png")
print("已生成，零额度")
