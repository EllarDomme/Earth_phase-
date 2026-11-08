import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REF = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "素材", "ref_月面地球_1920x1280.jpg")
if not os.path.exists(REF):   # 兜底：原始附件路径
    REF = r"C:\Users\34684\.dsh\attachments\v1\objects\fb\fb268ef67fda3d795201cacf9c4ddd4590ed133420fd924380a477000e9bb454"
OUT = r"E:\DeskTop\地球\素材\moon_base.png"
os.makedirs(os.path.dirname(OUT), exist_ok=True)

im = Image.open(REF).convert("RGB")
A = np.asarray(im).astype(np.float32)
H, W = A.shape[:2]

# ① 擦掉原地球（含辉光）
x0, y0, x1, y1 = 466 - 45, 425 - 45, 1094 + 45, 639 + 45
w, h = x1 - x0, y1 - y0
sx = max(0, x0 - w - 40)
sw = min(w, W - sx)
patch = A[y0:y1, sx:sx + sw]
if sw < w:                        # 不够宽就用镜像补齐
    patch = np.pad(patch, ((0, 0), (0, w - sw), (0, 0)), mode="reflect")
patch = patch[:, :w].copy()

ringL = A[y0:y1, max(0, x0 - 30):x0].reshape(-1, 3)
ringR = A[y0:y1, x1:min(W, x1 + 30)].reshape(-1, 3)
ring = np.concatenate([ringL, ringR], axis=0)
pm, ps = patch.reshape(-1, 3).mean(0), patch.reshape(-1, 3).std(0) + 1e-6
rm, rs = ring.mean(0), ring.std(0) + 1e-6
A[y0:y1, x0:x1] = np.clip((patch - pm) / ps * rs + rm, 0, 255)

base = Image.fromarray(A.astype(np.uint8))
pad = 18
box = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
soft = base.filter(ImageFilter.GaussianBlur(2.5))
m = Image.new("L", (box[2] - box[0], box[3] - box[1]), 255)
d = ImageDraw.Draw(m)
d.rectangle((pad, pad, pad + w, pad + h), fill=0)
m = m.filter(ImageFilter.GaussianBlur(pad / 2))
base.paste(soft.crop(box), (box[0], box[1]), m)

# ② 裁掉底部 6%（水印带），再缩回原尺寸
cut = int(H * 0.94)
base = base.crop((0, 0, W, cut)).resize((W, H), Image.LANCZOS)

base.save(OUT)
print("底图已生成：", OUT, base.size)
