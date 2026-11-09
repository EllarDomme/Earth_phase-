"""shorten_shadow2.py —— 调参：正确抓出影子，再回缩"""
import numpy as np
from PIL import Image, ImageFilter

AST = r"E:\DeskTop\地球\素材"
SRC = AST + r"\moon_base_v2.png"

A = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)
H, W = A.shape[:2]
L = A.mean(2)
terr = L > 3

print("=== 试不同模糊半径/阈值，看影子占比 ===")
for br in (40, 80, 120):
    med = np.asarray(Image.fromarray(np.clip(L, 0, 255).astype(np.uint8))
                     .filter(ImageFilter.GaussianBlur(br))).astype(np.float32)
    for th in (0.75, 0.85):
        sh = (L < med * th) & terr
        print("  模糊%3d  阈值%.2f  影子占比 %5.1f%%" % (br, th, sh.mean() * 100))
