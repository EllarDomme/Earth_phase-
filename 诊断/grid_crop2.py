"""grid_crop2.py —— 更宽的取景，看清"最大坑左边那个坑" """
from PIL import Image, ImageDraw, ImageFont

A = Image.open(r"E:\DeskTop\地球\素材\moon_base_无影.png").convert("RGB")
B = Image.open(r"E:\DeskTop\地球\素材\moon_base_中影.png").convert("RGB")
f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 24)

BOX = (0, 980, 1300, 1280)


def gridded(im, name):
    c = im.crop(BOX)
    d = ImageDraw.Draw(c)
    for x in range(0, BOX[2] - BOX[0], 100):
        d.line([(x, 0), (x, c.size[1])], fill=(255, 70, 70), width=1)
        d.text((x + 3, 3), str(BOX[0] + x), font=f, fill=(255, 210, 70))
    for y in range(0, BOX[3] - BOX[1], 60):
        d.line([(0, y), (c.size[0], y)], fill=(255, 70, 70), width=1)
        d.text((3, y + 1), str(BOX[1] + y), font=f, fill=(255, 210, 70))
    c.save(r"E:\DeskTop\草稿\宽网格_%s.png" % name)
    print("  宽网格_%s.png %s" % (name, c.size))


gridded(A, "无影")
gridded(B, "中影")
