"""make_docs_samples.py —— 生成 README 用的示意图（缩到 1200x800 的 JPEG）"""
import os

from PIL import Image

OUT = r"E:\DeskTop\地球\docs"
os.makedirs(OUT, exist_ok=True)

SAMPLES = [
    ("2009-06-21", "phase96", "96% 相位 · 中国几乎正中"),
    ("2004-11-08", "phase76", "76% 相位"),
    ("2002-10-01", "phase63", "63% 相位"),
    ("2021-06-25", "phase02", "2% 相位 · 极细月牙"),
]

total = 0
for date, tag, desc in SAMPLES:
    src = r"E:\DeskTop\地球\成品\%s_月面_提升_1920x1280.png" % date
    if not os.path.exists(src):
        print("缺:", src)
        continue
    im = Image.open(src).convert("RGB").resize((1200, 800), Image.LANCZOS)
    dst = os.path.join(OUT, "%s_%s.jpg" % (date, tag))
    im.save(dst, quality=88, optimize=True)
    sz = os.path.getsize(dst) / 1024
    total += sz
    print("  %-28s %6.0f KB   %s" % (os.path.basename(dst), sz, desc))

print()
print("合计 %.0f KB" % total)
