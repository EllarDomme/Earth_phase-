"""starless.py —— 只摘星点，不动天空底色

原理：星点是"比周围亮很多的小点"。
用大核中值滤波估出局部天空底色，把明显高于底色的像素替换成底色，
其余像素一个都不碰——天空的亮度、渐变、噪声全部保留。
"""
import numpy as np
from PIL import Image, ImageFilter


def strip_stars(A, hz, disc, thresh=8, verbose=False, sky=None):
    """A: float32 (H,W,3) RGB；hz: 地平线行号；disc: 地球圆盘 mask（True=盘内，不动）

    sky: 可选，逐像素天空 mask。给了就用它（跟随地形轮廓），
         否则退回"hz 以上"——后者会误吃地形峰顶的高光（2026-11-07）。
    """
    if sky is not None:
        sky_mask = sky & ~disc
    else:
        sky_mask = np.zeros(A.shape[:2], bool)
        sky_mask[:hz] = True
        sky_mask &= ~disc

    lum = A.mean(2)
    # 大核中值 = 局部天空底色（用 L 通道估）
    L = Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8))
    bg = np.asarray(L.filter(ImageFilter.MedianFilter(9))).astype(np.float32)

    stars = sky_mask & (lum > bg + thresh)
    n = int(stars.sum())
    if n:
        # 用底色替换（逐通道：按 lum 差值抬回原位）
        off = (bg - lum)[..., None]
        A = np.where(stars[..., None], np.clip(A + off, 0, 255), A)
    if verbose:
        print("    摘星 %d 个像素" % n)
    return A, n
