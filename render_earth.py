"""render_earth.py —— 2008-10-26 地球圆盘（纹理层 + 光照渲染层）

1) 纹理层：GIBS 4096 宽，Terra + Aqua 互补，逐行 crossfade 补缺口，极区替换
2) 渲染层：球面法线 + 太阳方向 → 晨昏线、临边变暗、大气辉光
"""
import io
import math
import os
import ssl
import time
import urllib.request

import numpy as np
from PIL import Image, ImageFilter

OUT = r"E:\DeskTop\地球\v2"
TW, TH = 4096, 2048
LAYERS = {
    "viirs": "VIIRS_SNPP_CorrectedReflectance_TrueColor",
    "terra": "MODIS_Terra_CorrectedReflectance_TrueColor",
    "aqua": "MODIS_Aqua_CorrectedReflectance_TrueColor",
}
DATE = "2008-10-26"   # 由 CLI 覆盖
CTX = ssl._create_unverified_context()



def wms_bbox(south, west, north, east):
    """★ 唯一的 BBOX 出口：调用者永远按"南,西,北,东"的人话顺序传参，
       由这里翻成 WMS 1.3.0 的"纬度在前"格式。禁止在别处手写 BBOX 字面量。"""
    assert south < north and west < east, "bbox 边界顺序错误"
    return f"{south},{west},{north},{east}"


def fetch(layer, date, w=2048, h=1024, retries=3):
    url = ("https://wvs.earthdata.nasa.gov/api/v1/snapshot?REQUEST=GetSnapshot"
           f"&TIME={date}&BBOX={wms_bbox(-90, -180, 90, 180)}&CRS=EPSG:4326"
           f"&LAYERS={layer}&FORMAT=image/jpeg&WIDTH={w}&HEIGHT={h}")
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            d = urllib.request.urlopen(req, timeout=120, context=CTX).read()
            if len(d) < 5000:
                raise ValueError("too small")
            im = Image.open(io.BytesIO(d)).convert("RGB")
            g = np.asarray(im.convert("L"))
            rows = np.nonzero(g.max(axis=1) > 12)[0]
            if len(rows) == 0:
                raise ValueError("all black")
            im = im.crop((0, int(rows.min()), im.width, int(rows.max()) + 1))
            return im.resize((TW, TH), Image.LANCZOS)
        except Exception as e:                     # noqa: BLE001
            last = e
            print(f"    retry {i+1}: {type(e).__name__}")
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"fetch failed: {last}")


def valid_mask(im, thresh=8, grow=2):
    g = np.asarray(im.convert("L")).astype(np.int16)
    ok = g > thresh
    if grow:
        inv = Image.fromarray(((~ok) * 255).astype(np.uint8))
        inv = inv.filter(ImageFilter.MaxFilter(2 * grow + 1))
        ok = ~(np.asarray(inv) > 127)
    return ok


def crossfade_fill(img, valid):
    a = np.asarray(img).astype(np.float32)
    out = a.copy()
    H, W, _ = a.shape
    for y in range(H):
        v = valid[y]
        if v.all():
            continue
        x = 0
        while x < W:
            if v[x]:
                x += 1
                continue
            a0 = x
            while x < W and not v[x]:
                x += 1
            b0 = x - 1
            if a0 == 0 and b0 >= W - 1:
                continue
            if a0 == 0:
                out[y, a0:b0 + 1] = a[y, b0 + 1]
            elif b0 >= W - 1:
                out[y, a0:b0 + 1] = a[y, a0 - 1]
            else:
                left = a[y, a0 - 1]
                right = a[y, b0 + 1]
                t = np.linspace(0, 1, (b0 - a0 + 1) + 2, dtype=np.float32)[1:-1][:, None]
                out[y, a0:b0 + 1] = left * (1 - t) + right * t
    return out



def _box3(x):
    p = np.pad(x, ((1, 1), (1, 1)) + ((0, 0),) * (x.ndim - 2), mode="edge")
    return (p[:-2, :-2] + p[:-2, 1:-1] + p[:-2, 2:]
            + p[1:-1, :-2] + p[1:-1, 1:-1] + p[1:-1, 2:]
            + p[2:, :-2] + p[2:, 1:-1] + p[2:, 2:]) / 9.0


def diffuse_fill(img, mask, iters=80):
    """扩散填充：有效像素的颜色一圈圈推进缺口，避免横向插值造成的条带。"""
    base = np.asarray(img).astype(np.float32)
    a = base * (~mask)[..., None]
    cnt = (~mask).astype(np.float32)
    for _ in range(iters):
        if (cnt > 0.5).all():
            break
        ab = _box3(a)
        cb = _box3(cnt)
        upd = (cnt < 0.5) & (cb > 0)
        if not upd.any():
            break
        a[upd] = ab[upd] / cb[upd][:, None]
        cnt[upd] = 1.0
    out = base.copy()
    out[mask] = a[mask]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fix_polar(out, valid):
    H, W, _ = out.shape
    rowfrac = valid.mean(axis=1)
    good = np.flatnonzero(rowfrac > 0.55)
    if len(good) == 0:
        return out
    y0, y1 = int(good[0]), int(good[-1])
    for y in range(0, y0):
        out[y] = out[min(2 * y0 - y, H - 1)]
    for y in range(y1 + 1, H):
        out[y] = out[max(2 * y1 - y, 0)]
    band = 40
    if y0 > 0:
        sub = Image.fromarray(np.clip(out[:y0 + band], 0, 255).astype(np.uint8))
        out[:y0 + band] = np.asarray(sub.filter(ImageFilter.GaussianBlur(6))).astype(np.float32)
    if y1 < H - 1:
        sub = Image.fromarray(np.clip(out[y1 - band:], 0, 255).astype(np.uint8))
        out[y1 - band:] = np.asarray(sub.filter(ImageFilter.GaussianBlur(6))).astype(np.float32)
    return out


def _gauss1d(x, sigma):
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    return np.convolve(np.pad(x, (r, r), mode="edge"), k, mode="valid")


def flatten_column_bands(a, sigma_lp=45, sigma_gain=10, maxgain=0.18):
    """把整幅的"列均值"拉向其低频趋势，消掉数据源拼接留下的竖直亮度台阶。"""
    prof = a.mean(axis=(0, 2))
    smooth = _gauss1d(prof, sigma_lp)
    gain = np.clip(smooth / np.maximum(prof, 1.0), 1 - maxgain, 1 + maxgain)
    gain = _gauss1d(gain, sigma_gain)
    return a * gain[None, :, None]



def soften_seam_bands(a, sigma_lp=45, half=22, blur_sigma=5.0, mix=0.75, k=6.0, floor=8.0, top=3):
    """自动找出列均值的异常台阶，只在那条窄带的局部做柔化，抹掉接缝的结构差。"""
    prof = a.mean(axis=(0, 2))
    smooth = _gauss1d(prof, sigma_lp)
    resid = prof - smooth
    mad = np.median(np.abs(resid)) + 1e-6
    hot = np.flatnonzero(np.abs(resid) > max(floor, k * mad))
    if hot.size == 0:
        return a
    blurred = np.asarray(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
                         .filter(ImageFilter.GaussianBlur(blur_sigma))).astype(np.float32)
    # 把相邻热点并成区间
    groups, cur = [], [hot[0]]
    for c in hot[1:]:
        if c - cur[-1] <= 3:
            cur.append(c)
        else:
            groups.append(cur); cur = [c]
    groups.append(cur)
    groups.sort(key=lambda g: -np.abs(resid[g]).max())
    groups = groups[:top]
    out = a.copy()
    W = a.shape[1]
    for g in groups:
        c0 = int(np.mean(g))
        lo, hi = max(0, c0 - half), min(W, c0 + half + 1)
        # 越靠中心混合越多
        t = np.linspace(-1, 1, hi - lo)
        w = np.clip(1 - np.abs(t), 0, 1) ** 0.7 * mix
        out[:, lo:hi] = a[:, lo:hi] * (1 - w[None, :, None]) + blurred[:, lo:hi] * w[None, :, None]
    print(f"      柔化接缝 {len(groups)} 处（经度: {[round(int(np.mean(g))/W*360-180) for g in groups]}）")
    return out



def soften_dateline(a, half=30, blur_sigma=7.0, mix=0.9):
    """日界线接缝是每日拼图的固有问题：滚半圈后在中部柔化，再滚回去。"""
    W = a.shape[1]
    r = np.roll(a, W // 2, axis=1)
    blur = np.asarray(Image.fromarray(np.clip(r, 0, 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(blur_sigma))).astype(np.float32)
    c0 = W // 2
    lo, hi = c0 - half, c0 + half + 1
    t = np.linspace(-1, 1, hi - lo)
    w = (np.clip(1 - np.abs(t), 0, 1) ** 0.6 * mix)[None, :, None]
    r[:, lo:hi] = r[:, lo:hi] * (1 - w) + blur[:, lo:hi] * w
    print("      已柔化日界线接缝")
    return np.roll(r, -(W // 2), axis=1)


def suppress_seams(img, k=2.2, radius=5, passes=3):
    """找出异常突出的竖直列（补洞留下的接缝），只对这些列用邻列均值替换。"""
    a = np.asarray(img).astype(np.float32).copy()
    H, W, _ = a.shape
    for _ in range(passes):
        dx = np.abs(np.diff(a, axis=1)).mean(axis=(0, 2))
        dx = np.convolve(dx, np.ones(3) / 3, mode="same")   # 让相邻列一起判定
        med = np.median(dx)
        mad = np.median(np.abs(dx - med)) + 1e-6
        hot = np.flatnonzero(dx > med + k * mad)
        if hot.size == 0:
            break
        for c in hot:
            lo, hi = max(0, c - radius), min(W, c + radius + 1)
            nb = np.concatenate([a[:, lo:c], a[:, c + 1:hi]], axis=1)
            if nb.shape[1] > 0:
                a[:, c] = nb.mean(axis=1)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def build_texture():
    os.makedirs(OUT, exist_ok=True)
    tex_path = os.path.join(OUT, f"texture_{DATE}.jpg")
    ims = {}
    layers = dict(LAYERS)
    if DATE < "2012-01-01":          # VIIRS 2012 年才上线
        layers.pop("viirs", None)
    for name, layer in layers.items():
        p = os.path.join(OUT, f"raw_{name}_{DATE}.jpg")
        if os.path.exists(p):
            im = Image.open(p).convert("RGB")
        else:
            print(f"  取 {name} ...")
            im = fetch(layer, DATE)
            im.save(p, quality=92)
        ims[name] = im
        print(f"  {name}: {im.size}, 缺口 {100*(~valid_mask(im)).mean():.2f}%")

    order = [k for k in ("viirs", "terra", "aqua") if k in ims]
    if os.environ.get("SINGLE_SOURCE"):
        order = order[:1]
    base = np.asarray(ims[order[0]]).astype(np.float32)
    valid = valid_mask(ims[order[0]])
    out = base.copy()
    for k in order[1:]:
        a = np.asarray(ims[k]).astype(np.float32)
        vk = valid_mask(ims[k])
        sel = (~valid) & vk
        if sel.any():
            # 羽化：把"取用区域"的掩膜模糊掉，边界处渐变融合，避免出现竖直硬边
            m = Image.fromarray((sel * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(14))
            alpha = (np.asarray(m).astype(np.float32) / 255.0)[..., None]
            out = out * (1 - alpha) + a * alpha
        valid |= vk
        print(f"  +{k} 后缺口 {100*(~valid).mean():.2f}%")
    print(f"  多源互补后缺口 {100*(~valid).mean():.2f}%")

    filled = ~valid
    out = crossfade_fill(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)), valid)
    # 填补区域做各向同性柔化，压掉横向条带感
    blur = np.asarray(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(9))).astype(np.float32)
    out[filled] = 0.25 * out[filled] + 0.75 * blur[filled]
    # 高纬度缺口被拉得更宽，补出来的条带更显眼：极区直接换成重度柔化
    heavy = np.asarray(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(16))).astype(np.float32)
    latv = 90.0 - (np.arange(out.shape[0]) + 0.5) / out.shape[0] * 180.0
    polar = (np.abs(latv) > 45)[:, None] & filled
    out[polar] = heavy[polar]
    out = fix_polar(out, valid)
    out = np.asarray(suppress_seams(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)))).astype(np.float32)
    out = flatten_column_bands(out)
    out = soften_seam_bands(out)
    out = soften_dateline(out)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(tex_path, quality=95)
    # 色彩迁移：向 Blue Marble 的调色靠拢（只改色，不改内容）
    bm_path = os.path.join(OUT, "world.topo.bathy.200412.3x5400x2700.jpg")
    if os.path.exists(bm_path):
        bm = Image.open(bm_path).convert("RGB").resize((TW, TH), Image.LANCZOS)
        out = color_transfer(np.clip(out, 0, 255), np.asarray(bm).astype(np.float32), strength=0.0)
        print("  已做色彩迁移（Blue Marble 参考）")
    # 轻度调色：提对比 + 提饱和，让画面不那么灰
    from PIL import ImageEnhance
    grade = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    grade = ImageEnhance.Contrast(grade).enhance(1.06)
    grade = ImageEnhance.Color(grade).enhance(1.10)
    out = np.asarray(grade).astype(np.float32)
    np.save(os.path.join(OUT, "texture.npy"), np.clip(out, 0, 255).astype(np.uint8))
    print(f"  纹理已存 {tex_path}")
    return tex_path



def _srgb2lab(rgb):
    rgb = rgb.astype(np.float32) / 255.0
    m = rgb > 0.04045
    rgb = np.where(m, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]], np.float32)
    xyz = rgb @ M.T
    xyz /= np.array([0.95047, 1.0, 1.08883], np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def _lab2srgb(lab):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200
    f = np.stack([fx, fy, fz], axis=-1)
    xyz = np.where(f ** 3 > 0.008856, f ** 3, (f - 16 / 116) / 7.787)
    xyz *= np.array([0.95047, 1.0, 1.08883], np.float32)
    M = np.array([[3.2404542, -1.5371385, -0.4985314],
                  [-0.9692660, 1.8760108, 0.0415560],
                  [0.0556434, -0.2040259, 1.0572252]], np.float32)
    rgb = xyz @ M.T
    rgb = np.clip(rgb, 0, None)
    m = rgb > 0.0031308
    rgb = np.where(m, 1.055 * rgb ** (1 / 2.4) - 0.055, 12.92 * rgb)
    return np.clip(rgb * 255, 0, 255)


def color_transfer(src, ref, strength=0.75):
    """Reinhard 色彩迁移：把 src 的调色板靠向 ref（保留 src 的内容）。"""
    if strength <= 0:
        return src
    ls, lr = _srgb2lab(src), _srgb2lab(ref)
    out = ls.copy()
    for i in range(3):
        ms, ss = ls[..., i].mean(), ls[..., i].std() + 1e-6
        mr, sr = lr[..., i].mean(), lr[..., i].std() + 1e-6
        out[..., i] = (ls[..., i] - ms) * (sr / ss) * strength + ms * (1 - strength) + mr * strength
    return _lab2srgb(out)


# ---------------------------------------------------------------- 渲染层
def sun_vector(date=None, utc_hour=2.683):
    """太阳方向（ECEF）。用"赤纬 + 时角"的简化公式，误差 <1°。"""
    from datetime import date as _date
    d = _date.fromisoformat(date or DATE)
    doy = d.timetuple().tm_yday
    dec = math.radians(-23.44 * math.cos(math.radians(360.0 / 365.0 * (doy + 10))))
    lon = math.radians((12.0 - utc_hour) * 15.0)
    return np.array([math.cos(dec) * math.cos(lon),
                     math.cos(dec) * math.sin(lon),
                     math.sin(dec)], np.float32)


def render(lat0=20.0, lon0=105.0, size=1400, utc_hour=2.683):
    tex = np.load(os.path.join(OUT, "texture.npy")).astype(np.float32) / 255.0
    H, W, _ = tex.shape

    p0, l0 = math.radians(lat0), math.radians(lon0)
    e_z = np.array([math.cos(p0) * math.cos(l0), math.cos(p0) * math.sin(l0), math.sin(p0)], np.float32)
    e_x = np.array([-math.sin(l0), math.cos(l0), 0.0], np.float32)          # 东向
    e_y = np.cross(e_z, e_x).astype(np.float32)                              # 北向

    # ★ 超采样（2026-11-07）：球缘附近经度被极度压缩，
    #   按目标分辨率直接采样会出现密集条纹（"磕磕绊绊"的真凶）。
    #   内部按 SS 倍分辨率渲染，再用 LANCZOS 缩回去。
    SS = int(globals().get("SS", 2))
    SS = max(1, SS)
    size_hi = size * SS

    R = size_hi // 2
    xx, yy = np.meshgrid((np.arange(size_hi) - R + 0.5) / R, (R - np.arange(size_hi) - 0.5) / R)
    r2 = xx * xx + yy * yy
    inside = r2 <= 1.0
    zz = np.sqrt(np.clip(1.0 - r2, 0, 1))

    n = (xx[..., None] * e_x + yy[..., None] * e_y + zz[..., None] * e_z).astype(np.float32)
    lat = np.arcsin(np.clip(n @ np.array([0, 0, 1], np.float32), -1, 1))
    lon = np.arctan2(n[..., 1], n[..., 0])

    u = ((np.rad2deg(lon) + 180) % 360) / 360 * W
    v = (90 - np.rad2deg(lat)) / 180 * H
    # 经度方向环绕采样：u 越过 0/W 时从另一侧取，日界线不再有接缝
    u0 = np.floor(u).astype(int) % W
    u1 = (u0 + 1) % W
    v0 = np.clip(v.astype(int), 0, H - 2); v1 = v0 + 1
    fu = (u - np.floor(u))[..., None]; fv = (v - v0)[..., None]
    col = (tex[v0, u0] * (1 - fu) * (1 - fv) + tex[v0, u1] * fu * (1 - fv)
           + tex[v1, u0] * (1 - fu) * fv + tex[v1, u1] * fu * fv)

    s = sun_vector(utc_hour=utc_hour)
    cosi = n @ s
    day = np.clip((cosi + 0.02) / 0.10, 0, 1)               # 晨昏线过渡
    day = day * day * (3 - 2 * day)
    limb = 0.72 + 0.28 * np.clip(zz, 0, 1) ** 0.45          # 临边变暗
    if int(globals().get("FULL_FLAT", 0)):
        limb = np.ones_like(limb)                            # 去掉临边，纯反照率
    # 环境光：物理上地球暗面只被月光照亮（~1e-6），这里保留一丝便于辨认轮廓
    # AMBIENT=0 为严格真实；0.0005 是"几乎全黑但能看出球体"
    AMBIENT = float(globals().get("AMBIENT", 0.02))   # 5% 地照：暗面必须看得见，亮+暗合起来才是完整正圆

    # ★ 云顶悬照（2026-11-05 新增）：
    #   云顶高约 10 km，比地面早看到日出。地面晨昏线外 3.2°（约 357 km）内，
    #   云顶仍是亮的 —— 真实卫星照片里能看到那圈"发光云顶"。
    #   cosi 门槛 = sin(-3.2°) ≈ -0.056
    CLOUD_TOP = float(globals().get("CLOUD_TOP", 0.25))

    day_mix = day
    if CLOUD_TOP > 0:
        lum_c = col.mean(axis=2)
        cloud = np.clip((lum_c - 0.52) / 0.30, 0, 1)        # 云的浓淡（0=晴空，1=厚云）
        ct = np.clip((cosi + 0.056) / 0.030, 0, 1)
        ct = ct * ct * (3 - 2 * ct)                          # 云顶越过晨昏线的过渡
        day_mix = day + (1.0 - day) * cloud * ct * CLOUD_TOP

    # ★ FULL_LIT=1：输出"全亮"，只保留临边（视角决定），不打光照。
    #   用于验证"先定几何、最后打光"的流水线方案。
    FULL_LIT = int(globals().get("FULL_LIT", 0))
    if FULL_LIT:
        day_mix = np.ones_like(day_mix)

    shade = (AMBIENT + (1.0 - AMBIENT) * day_mix) * limb

    out = col * shade[..., None]

    # ★ 晨昏线"大气薄雾"（2026-11-07）：
    #   掠射角下光线穿过大气层的路径变长，散射会把地表对比冲淡——
    #   这是真实物理（不是磨皮）。做法：在 cosi≈0 附近把图像往"低频"拉一点，
    #   锯齿状的云边就会被压平，但明暗分界的位置不变。
    TERM_HAZE = float(globals().get("TERM_HAZE", 0.0))
    if TERM_HAZE > 0:
        from PIL import ImageFilter as _IF
        import numpy as _np
        _g = _np.clip(out * 255.0, 0, 255).astype(_np.uint8)
        _bl = _np.asarray(Image.fromarray(_g).filter(
            _IF.GaussianBlur(3.5))).astype(_np.float32) / 255.0
        _w = _np.exp(-((cosi / 0.20) ** 2)) * TERM_HAZE
        out = out * (1.0 - _w[..., None]) + _bl * _w[..., None]
    # ★ 大气弧光：紧贴球缘、允许溢出球外（大气在球体之外 + 镜头 bloom）
    ARC_W = float(globals().get("ARC_W", 0.018))     # 带宽度（占半径）
    ARC_A = float(globals().get("ARC_A", 0.35))      # 峰值强度
    ARC_OUT = float(globals().get("ARC_OUT", 2.0))   # 允许溢出几个像素
    _rr = np.sqrt(r2)
    _band = np.exp(-np.abs(_rr - 0.995) / ARC_W)          # 以球缘为中心的亮带
    _ocut = np.clip((1.0 + ARC_OUT / R - _rr) / (ARC_OUT / R), 0, 1)   # 外侧 2px 淡出
    arc = _band * _ocut * np.clip(cosi * 3.0, 0, 1) ** 1.2
    arc = arc[..., None] * np.array([0.45, 0.62, 0.95], np.float32) * ARC_A

    # 太阳耀斑抑制：在星下点附近做一个高斯凹陷（模拟缺少镜面反射）
    ang = np.arccos(np.clip(cosi, -1, 1))
    # ★ 耀斑压制强度（2026-11-06 可调）
    #   0.55 是早期为了压住星下点"白斑"设的，但它会把太阳直射区压得比外圈还暗，
    #   违反"亮度 ∝ cos(入射角)"。物理上应接近 0（地球是漫反射，海面镜面反射很窄）。
    # 保持 0.55：给豆包的图要"原始色调"（中心略压，避免白斑），
    # 光照补偿放到最后一道（doubao_boost 的 deglint）
    GLINT = float(globals().get("GLINT", 0.55))
    glint = 1.0 - GLINT * np.exp(-(ang / 0.40) ** 2)
    out = out * glint[..., None]
    # ★ 云顶自阴影（极轻）：用亮度当高度场，向阳坡稍亮、背光坡稍暗
    #   太阳方向投影到画面平面 → 与亮度梯度点乘
    RELIEF = float(globals().get("RELIEF", 0.06))
    if RELIEF > 0:
        lum0 = out.mean(axis=2)
        # 画面平面的太阳方向（east/north 分量）
        s_e = float(s @ e_x)
        s_n = float(s @ e_y)
        nrm = math.hypot(s_e, s_n) or 1.0
        gy, gx = np.gradient(lum0)
        slope = (gx * (s_e / nrm) + (-gy) * (s_n / nrm))
        out = out * (1.0 + RELIEF * np.clip(slope * 6.0, -1, 1))[..., None]

    # 高光压制：整体降一点曝光 + 软膝曲线压住 >0.48 的部分（给云顶留层次）
    # ★ NO_TONE=1 时全部跳过，用于查看"未经任何色调处理"的原始纹理（诊断用）
    NO_TONE = int(os.environ.get("RENDER_NO_TONE", globals().get("NO_TONE", 0)))
    # 环境变量 RENDER_NO_TONE=1 可在不改代码的情况下一键关闭全部色调处理
    if not NO_TONE:
        out = out * 0.84
        knee = 0.48
        hi = out > knee
        out[hi] = knee + (1.0 - knee) * np.tanh((out[hi] - knee) / (1.0 - knee) * 1.4) / np.tanh(1.4)
        # 过曝区去饱和
        lum = out.mean(axis=2, keepdims=True)
        w = np.clip((out.max(axis=2, keepdims=True) - 0.75) / 0.25, 0, 1) * 0.6
        out = out * (1 - w) + lum * w
    out[~inside] = 0
    edge = np.clip((1.0 - np.sqrt(r2)) / 0.0015, 0, 1)[..., None]
    out = out * edge
    out = np.clip(out + arc, 0, 1)          # ← 弧光最后叠加，可溢出球缘
    img = Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8))
    if SS > 1:
        img = img.resize((size, size), Image.LANCZOS)
    p = os.path.join(OUT, f"disk_{DATE}.png")
    img.save(p)
    print("  已保存", p)
    return p


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2008-10-26")
    ap.add_argument("--utc", type=float, default=2.683, help="UTC 小时，北京 10:41 = 2.683")
    ap.add_argument("--lat", type=float, default=20.0)
    ap.add_argument("--lon", type=float, default=105.0)
    ap.add_argument("--size", type=int, default=1400)
    a = ap.parse_args()
    DATE = a.date
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    print(f"[1/2] 纹理层 {DATE}")
    build_texture()
    print("[2/2] 渲染层")
    render(lat0=a.lat, lon0=a.lon, size=a.size, utc_hour=a.utc)
    print(f"完成，用时 {time.time()-t0:.0f}s")
