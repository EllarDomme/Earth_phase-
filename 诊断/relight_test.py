"""relight_test.py —— 方案 B 验证：从底图反推法线，把太阳高度改掉

做法（relief transfer）：
  ① 用亮度梯度当作"起伏"，构造法线场 n = normalize(-k·∂I/∂x, -k·∂I/∂y, 1)
  ② 网格搜索原太阳方向 l_old，使 max(0, n·l) 与原图亮度最相关
  ③ 换新太阳方向 l_new，算比值 shading_new / shading_old
  ④ 把比值乘回原图 → 阴影方向/长度改变，纹理与反照率保留
"""
import numpy as np
from PIL import Image, ImageFilter

BASE = r"E:\DeskTop\地球\素材\moon_base_v2.png"
OUT_TMPL = r"E:\DeskTop\测试_重打光_太阳%d度.png"

im = Image.open(BASE).convert("RGB")
A = np.asarray(im).astype(np.float32) / 255.0
H, W = A.shape[:2]
L = A.mean(2)

# 只处理地形（天空保持纯黑）
sky_black = L < 0.02
print("图像 %dx%d，天空像素占比 %.0f%%" % (W, H, sky_black.mean() * 100))

# ① 梯度 → 法线
blur = np.asarray(Image.fromarray((L * 255).astype(np.uint8))
                  .filter(ImageFilter.GaussianBlur(1.5))).astype(np.float32) / 255.0
gx = np.zeros_like(blur); gy = np.zeros_like(blur)
gx[:, 1:-1] = (blur[:, 2:] - blur[:, :-2]) * 0.5
gy[1:-1, :] = (blur[2:, :] - blur[:-2, :]) * 0.5

K = 6.0                                    # 起伏强度（越大越"立体"）
nx, ny, nz = -K * gx, -K * gy, np.ones_like(blur)
norm = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-9
nx, ny, nz = nx / norm, ny / norm, nz / norm


def lvec(elev_deg, az_deg):
    e, a = np.radians(elev_deg), np.radians(az_deg)
    return np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)], dtype=np.float32)


# ② 校准原太阳方向
best = None
sample = ~sky_black
idx = np.where(sample)
step = max(1, len(idx[0]) // 60000)
si = (idx[0][::step], idx[1][::step])
for elev in (5, 10, 15, 20, 25):
    for az in range(0, 360, 15):
        l = lvec(elev, az)
        sh = np.maximum(nx * l[0] + ny * l[1] + nz * l[2], 0)
        a1 = sh[si]; b1 = L[si]
        c = np.corrcoef(a1, b1)[0, 1]
        if best is None or c > best[0]:
            best = (c, elev, az, l)
corr, elev0, az0, l_old = best
print("校准原太阳：高度 %d°  方位 %d°  相关 %.3f" % (elev0, az0, corr))

sh_old = np.maximum(nx * l_old[0] + ny * l_old[1] + nz * l_old[2], 0.02)

# ③ 换太阳高度（方位不变）
for elev_new in (30, 55):
    l_new = lvec(elev_new, az0)
    sh_new = np.maximum(nx * l_new[0] + ny * l_new[1] + nz * l_new[2], 0.02)
    ratio = np.clip(sh_new / sh_old, 0.15, 3.0)

    out = A * ratio[..., None]
    out[sky_black] = 0.0                    # 天空不动
    out = np.clip(out, 0, 1)
    p = OUT_TMPL % elev_new
    Image.fromarray((out * 255).astype(np.uint8)).save(p)
    print("已生成：太阳 %d° → %s" % (elev_new, p))
