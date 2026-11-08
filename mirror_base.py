"""mirror_base.py —— 把月面底图左右镜像（光照自然翻到右侧）"""
import sys

from PIL import Image

src = sys.argv[1]
dst = sys.argv[2]
im = Image.open(src).convert("RGB")
im.transpose(Image.FLIP_LEFT_RIGHT).save(dst)
print("已镜像输出：", dst, im.size)
