"""grid_crop.py —— 给两张图叠加坐标网格，方便定位小坑"""
from PIL import Image, ImageDraw, ImageFont

A = Image.open(r"E:\DeskTop\地球\素材\moon_base_无影.png").convert("RGB")
B = Image.open(r"E:\DeskTop\地球\素材\moon_base_中影.png").convert("RGB")
f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 22)

BOX = (250, 820, 1350, 1280)     # 前景大坑所在区域


def gridded(im, name):
    c = im.crop(BOX)
    d = ImageDraw.Draw(c)
    step = 100
    for x in range(0, BOX[2] - BOX[0], step):
        d.line([(x, 0), (x, c.size[1])], fill=(255, 60, 60), width=1)
        d.text((x + 3, 3), str(BOX[0] + x), font=f, fill=(255, 200, 60))
    for y in range(0, BOX[3] - BOX[1], step):
        d.line([(0, y), (c.size[0], y)], fill=(255, 60, 60), width=1)
        d.text((3, y + 2), str(BOX[1] + y), font=f, fill=(255, 200, 60))
    c.save(r"E:\DeskTop\草稿\网格_%s.png" % name)
    print("  网格_%s.png  %s" % (name, c.size))


gridded(A, "无影")
gridded(B, "中影")
print("红框区域:", BOX)
