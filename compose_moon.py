"""compose_moon.py —— 把地相图合成到"月面 + 星空"底图上（《地出》式构图）

底图：素材/moon_base.png（1920×1280，已擦掉原地球、已裁掉水印带）
      素材/moon_base_mirror.png 为左右镜像版，光照方向相反
构图参数（2026-11-05 定稿，全部为默认值，流水线无需额外传参）：
  画幅        1920×1280（1.5:1）
  地平线      画高 59.5%
  地球直径    画宽 33%
  地球中心    (50%, 31%)   ← 2026-11-06 水平居中
  天空底色    对齐地球暗部 (3,3,4)
  星点        抹除

用法:
  python compose_moon.py <地球图> <输出.png> [--earth-pct 0.36] [--cx 0.50] [--cy 0.31]
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
# 底图光照方向（2026-11-06 实测更正）：
#   月面底图的【受光方向】≈ 0°（从右照来）
#   判据：陨石坑的亮壁在受光的【对面】——亮壁在左 ⇒ 光从右
# ★ 四张底图（按太阳高度分档，2026-11-09 定稿）
#   亮度不按"底图 × 系数"算 —— 那样换底图时会跳变。
#   改成先定"目标亮度曲线"，再反算系数，边界才连续。
BASE_TIERS = {
    "无影": (60.0, "moon_base_无影.png"),
    "短影": (30.0, "moon_base_短影.png"),
    "中影": (15.0, "moon_base_中影.png"),
    "长影": (8.0,  "moon_base_长影.png"),
}
BASE_LUM = {"无影": 86.0, "短影": 52.0, "中影": 47.0, "长影": 43.0}  # 地形中位亮度
L_NIGHT = 18.5        # 月夜目标亮度（h=0 处的连续点）
L_FLOOR = 18.5        # 白天最低 = 夜面上限，保证跨 0° 不回跳
# ★ 月夜档的"质感补偿"（2026-11-09）
#   月夜把月面压到中位 ~18，8 位色阶只剩 30 来个（白天是 200+），
#   高频能量 1.5 vs 7.0，看着糊。这里围绕中位做一次温和的对比度拉伸，
#   平均亮度基本不变，但细节能读出来。1.0 = 关。
#   注意：这是"暗部提亮"，属于后期美化，不是物理还原。
NIGHT_CONTRAST = float(os.environ.get("DSH_NIGHT_CONTRAST", "1.6"))
BASE = os.path.join(HERE, "素材", "moon_base.png")
BASE_MIRROR = os.path.join(HERE, "素材", "moon_base_mirror.png")
_BASE_SCALE = 1.0          # 月面亮度系数（只压不提）
MOON_LIGHT_DEG = 0.0        # 月面受光方向（画面角度：0=右, 90=上）

ap = argparse.ArgumentParser()
ap.add_argument("earth")
ap.add_argument("out")
ap.add_argument("--base", default=None, help="月面底图（默认按光照自动选）")
ap.add_argument("--date", default=None, help="日期 YYYY-MM-DD（给了就能自动选底图）")
ap.add_argument("--utc", type=float, default=None, help="UTC 小时（配合 --date）")
ap.add_argument("--no-auto-base", action="store_true",
                help="不自动选底图，强制用原版")
ap.add_argument("--width", type=int, default=1920)
ap.add_argument("--earth-pct", type=float, default=0.36)
ap.add_argument("--moon-gain", type=float, default=1.0,
                    help="月面亮度系数（<1 压暗，让地球更突出）")
ap.add_argument("--moon-grain", type=float, default=0.0,
                help="月面颗粒强度（默认 0=关）。2026-11-06 试过 1.2，"
                     "白噪声太规整、肉眼可见，已弃用；真要加必须有空间相关的胶片颗粒模型")
ap.add_argument("--cx", type=float, default=0.50)
ap.add_argument("--cy", type=float, default=0.31)
ap.add_argument("--sky-target", default="1,1,1",
                    help="天空统一色；默认 1,1,1 = 真实太空（近似全黑）")
ap.add_argument("--keep-stars", action="store_true")
ap.add_argument("--earth-rot", type=float, default=0.0,
                help="地球旋转角（度，逆时针）；默认 0 = 正北朝上（不要随意转）")
ap.add_argument("--dark-floor", type=float, default=0.0,
                help="球面亮度下限（0~15）：让暗面一直延伸到球缘，圆才读得完整")
ap.add_argument("--dark-lift", type=float, default=1.0,
                help="暗面提亮倍数（>1 让球体轮廓在夜空里可辨，球才显得居中）")
ap.add_argument("--earth-gamma", type=float, default=0.88,
                help="地球提亮（<1 更亮），建议 0.85~0.95")
ap.add_argument("--earth-sat", type=float, default=1.30,
                help="地球饱和度倍数，建议 1.2~1.6")
ap.add_argument("--limb-dark", type=float, default=0.0,
                help="临边变暗强度（0=关，0.3 左右比较像球；对应真实球体 cos 衰减）")
ap.add_argument("--earth-p99", type=float, default=200.0,
                help="把地球最亮压到该值（跟月面 p99≈183 接近）")
a = ap.parse_args()

# ★ 自动选底图：比较"地球亮面朝向"与"月面受光方向"
_auto_note = ""
if a.base:
    # ★ 显式指定底图时，仍然要按光照方向决定用原图还是镜像
    #   （以前这里直接 return，导致 --base 指定的图永远不镜像，
    #     2026-11-09 用户发现 47% 那张地球在西、月面却东边受光）
    BASE = a.base
    if (not a.no_auto_base) and a.date and (a.utc is not None):
        try:
            import math as _m0
            import ephem_hp as _E0

            def _unit0(lat, lon):
                la, lo = _m0.radians(lat), _m0.radians(lon)
                return np.array([_m0.cos(la) * _m0.cos(lo),
                                 _m0.cos(la) * _m0.sin(lo), _m0.sin(la)])

            _l0, _n0 = _E0.sublunar_point(a.date, a.utc)
            _S0 = _unit0(*_E0.subsolar_point(a.date, a.utc))
            _V0 = _unit0(_l0, _n0)
            _ex0 = np.cross([0, 0, 1.0], _V0); _ex0 /= np.linalg.norm(_ex0)
            _ey0 = np.cross(_V0, _ex0)
            _sun0 = _m0.degrees(_m0.atan2(float(_S0 @ _ey0), float(_S0 @ _ex0))) % 360
            _d0 = abs(_sun0 - MOON_LIGHT_DEG) % 360
            _d0 = min(_d0, 360 - _d0)
            _mir0 = a.base.replace(".png", "_mirror.png")
            if _d0 > 90 and os.path.exists(_mir0):
                BASE = _mir0
                _auto_note = ("地球亮面 %.0f° / 月面受光 %.0f° → 相差 %.0f°，"
                              "显式底图换成【镜像】" % (_sun0, MOON_LIGHT_DEG, _d0))
            else:
                _auto_note = ("地球亮面 %.0f° / 月面受光 %.0f° → 相差 %.0f°，"
                              "显式底图用【原图】" % (_sun0, MOON_LIGHT_DEG, _d0))
        except Exception as _e0:
            _auto_note = "显式底图的镜像判断失败（%s），用原图" % _e0
elif (not a.no_auto_base) and a.date and (a.utc is not None):
    try:
        import math as _m
        import ephem_hp as _E

        def _unit(lat, lon):
            la, lo = _m.radians(lat), _m.radians(lon)
            return np.array([_m.cos(la) * _m.cos(lo), _m.cos(la) * _m.sin(lo), _m.sin(la)])

        _lat0, _lon0 = _E.sublunar_point(a.date, a.utc)
        _S = _unit(*_E.subsolar_point(a.date, a.utc))
        _V = _unit(_lat0, _lon0)

        # ★ 月面太阳高度（子月下点）
        #   ephem_hp 返回的 S / V 方向相反（S 是"指向太阳"，V 是"指向地球"），
        #   实测直接 asin(S·V) 会得到反号，所以取负号。
        _h = -_m.degrees(_m.asin(max(-1.0, min(1.0, float(_S @ _V)))))

        # ① 目标亮度（唯一真相，连续函数）
        if _h <= 0:
            _L = L_NIGHT - 3.0 * min(1.0, -_h / 60.0)     # 月夜：18.5 → 15.5
        else:
            _L = 86.0 * (_m.sin(_m.radians(max(_h, 0.5))) / _m.sin(_m.radians(60.0))) ** 0.7
            _L = max(_L, L_FLOOR)                          # ★ 不能比夜面还黑

        # ② 选底图：只管"影子形态"，亮度由目标曲线统一决定
        _IS_NIGHT = _h < 0
        if _h < 0:
            _tier = "无影"          # 无直射光，没有影子
        elif _h >= 45:
            _tier = "无影"
        elif _h >= 22:
            _tier = "短影"
        elif _h >= 5:
            _tier = "中影"
        else:
            _tier = "长影"

        # ③ 反算系数
        #   · 无影底图够亮，只压不提
        #   · 短/中/长影底图偏暗，允许最多 +30% 提亮，否则分档边界会出现
        #     20 多个亮度单位的跳变（实测 44.5°→45° 差 22.6）
        _cap = 1.0 if _tier == "无影" else 1.30
        _BASE_SCALE = max(0.05, min(_cap, _L / BASE_LUM[_tier]))
        _tier_file = BASE_TIERS[_tier][1]
        _p_tier = os.path.join(HERE, "素材", _tier_file)
        _p_tier_m = os.path.join(HERE, "素材", _tier_file.replace(".png", "_mirror.png"))
        print("月面：太阳高度 %+.1f° → 目标亮度 %.1f → 用【%s】×%.2f"
              % (_h, _L, _tier, _BASE_SCALE))
        _ex = np.cross([0, 0, 1.0], _V); _ex /= np.linalg.norm(_ex)
        _ey = np.cross(_V, _ex)
        _sun_deg = _m.degrees(_m.atan2(float(_S @ _ey), float(_S @ _ex))) % 360
        _d = abs(_sun_deg - MOON_LIGHT_DEG) % 360
        _d = min(_d, 360 - _d)
        if _d > 90 and os.path.exists(_p_tier_m):
            BASE = _p_tier_m
            _auto_note = "地球亮面 %.0f° / 月面受光 %.0f° → 相差 %.0f°，用【镜像底图】" % (
                _sun_deg, MOON_LIGHT_DEG, _d)
        else:
            BASE = _p_tier if os.path.exists(_p_tier) else BASE
            _auto_note = "地球亮面 %.0f° / 月面受光 %.0f° → 相差 %.0f°，用【原底图】" % (
                _sun_deg, MOON_LIGHT_DEG, _d)
    except Exception as _e:
        _auto_note = "自动选底图失败（%s），用原底图" % _e

if _auto_note:
    print("底图选择：" + _auto_note)

if not os.path.exists(BASE):
    sys.exit("缺少底图：%s（先跑 make_base_final.py）" % BASE)

if "_IS_NIGHT" not in dir():
    _IS_NIGHT = False

base = Image.open(BASE).convert("RGB")
_gain_all = float(getattr(a, "moon_gain", 1.0)) * _BASE_SCALE
if abs(_gain_all - 1.0) > 0.001:
    import numpy as _np2
    _b = _np2.asarray(base).astype(_np2.float32) * _gain_all
    base = Image.fromarray(_np2.clip(_b, 0, 255).astype(_np2.uint8))
    print("月面亮度：x%.2f（含相位系数 %.2f）" % (_gain_all, _BASE_SCALE))

# ★ 月夜档：围绕地形中位做温和对比拉伸，找回被压掉的质感
if _IS_NIGHT and NIGHT_CONTRAST > 1.01:
    _bn = np.asarray(base).astype(np.float32)
    _lum = _bn.mean(2)
    _tm = _lum > 1                      # 地形（天空是 0）
    if _tm.any():
        _med = float(np.median(_lum[_tm]))
        _bn[_tm] = np.clip(_med + (_bn[_tm] - _med) * NIGHT_CONTRAST, 0, 255)
        base = Image.fromarray(np.clip(_bn, 0, 255).astype(np.uint8))
        print("月面质感：月夜档对比 x%.2f（中位 %.0f 保持）" % (NIGHT_CONTRAST, _med))
W0, H0 = base.size
W = a.width
H = int(round(H0 * W / W0))
base = base.resize((W, H), Image.LANCZOS)
hz = int(H * 0.595)

# ── ① 天空：默认刷成近黑的真实太空（1,1,1）
#  ★ 底图自带的天空是 8~12 的灰（AI 生成残留），真实太空应 ≈0。
#    注意不要再"按行硬切"——那会在 hz 处造出"雾光带"和"矩形"（2026-11-07 踩过），
#    整片统一刷 + 地平线 2 行抗锯齿即可。
#    --sky-target "" 或 none/keep 可保持底图原样。
if a.sky_target and a.sky_target.lower() not in ("none", "keep", ""):
    A = np.asarray(base).astype(np.float32)
    tgt = np.array([float(v) for v in a.sky_target.split(",")], np.float32)
    med = np.median(A[:hz].reshape(-1, 3), axis=0)
    rng = np.random.default_rng(7)
    flat = np.clip(tgt[None, None, :] + rng.normal(0, 0.25, (A.shape[0], A.shape[1], 1)),
                   0, 255).astype(np.float32)

    # ★ 天空按"地形轮廓"填，不能按固定行 hz 硬切：
    #   地形最高处到 y=755，比 hz=761 还高——硬切会把地形顶上几行抹平，
    #   看起来像被刀砍了一道（2026-11-07 用户指出）。
    Lm = A.mean(2)
    Hh = A.shape[0]
    y0, y1 = 520, min(Hh, 1100)
    above = Lm[y0:y1] > 6      # 底图天空已是 0.02，>6 就是地形
    first = np.argmax(above, axis=0)
    contour = np.where(above.any(axis=0), first + y0, hz).astype(np.int32)
    # ★ 用"窗口内最高点"（滚动最小值）平滑，不能用中位数：
    #   中位数会把孤立的峰削平——实测地形最高处 y=756 的亮度被从 12.1 压到 9.3，
    #   看起来像被"削了个平头"（2026-11-07 用户指出最高处不自然）。
    #   取 min 只会多留几行天空（0.02 与 1.0 差不到 1 级，看不出来）。
    contour = np.array([int(contour[max(0, i - 10):i + 11].min())
                        for i in range(len(contour))], np.int32)

    for x in range(A.shape[1]):
        ye = int(contour[x]) - 2
        if ye > 0:
            A[:ye, x] = flat[:ye, x]
        # ★ 不要再把天空和地形亮色混合做"抗锯齿"：
        #   实测会在地形隆起处留下一条亮边（2026-11-07 用户指出"最高处不自然"）。
        #   底图本身的边缘已经是抗过锯齿的，只要不覆盖它就行。
    base = Image.fromarray(np.clip(A, 0, 255).astype(np.uint8))
    print("天空：%.0f,%.0f,%.0f → 统一 %.0f,%.0f,%.0f（显式指定）" % (*med, *tgt))
else:
    print("天空：保持底图原样（不动）")

# ── ② 星点：默认摘掉（只摘亮点，天空底色不动）
if not a.keep_stars:
    from starless import strip_stars
    A = np.asarray(base).astype(np.float32)
    Hh, Ww = A.shape[:2]
    yy, xx = np.mgrid[0:Hh, 0:Ww]
    # 圆心必须跟 --cx/--cy 走；半径跟 --earth-pct 走（原来圆心写死，传 --cx 会错位）
    _disc = np.hypot(xx - a.cx * Ww, yy - a.cy * Hh) <= (a.earth_pct / 2) * Ww * 0.62

    # ★ 天空 mask 要跟随地形轮廓：按行 hz 切会把山峰高光当星点摘掉
    #   （实测 y=756 处亮度 12.1 → 9.2，顶部像被削平）
    _L = A.mean(2)
    _y0, _y1 = 520, min(Hh, 1100)
    _above = _L[_y0:_y1] > 6
    _first = np.argmax(_above, axis=0)
    _con = np.where(_above.any(axis=0), _first + _y0, hz).astype(np.int32)
    _con = np.array([int(_con[max(0, i - 10):i + 11].min()) for i in range(Ww)], np.int32)
    _sky = yy < _con[None, :]

    A, _n = strip_stars(A, hz, _disc, thresh=8, sky=_sky)
    base = Image.fromarray(np.clip(A, 0, 255).astype(np.uint8))
    print("星点：摘掉 %d 个像素（天空底色未动）" % _n)

# ── ③ 贴地球
earth = Image.open(a.earth).convert("RGB")

# ★ 提亮 + 加饱和（海面偏灰时用）
if abs(a.earth_gamma - 1.0) > 1e-3 or abs(a.earth_sat - 1.0) > 1e-3:
    E = np.asarray(earth).astype(np.float32) / 255.0
    if abs(a.earth_gamma - 1.0) > 1e-3:
        E = np.power(E, a.earth_gamma)
    if abs(a.earth_sat - 1.0) > 1e-3:
        g = E.mean(2, keepdims=True)
        E = np.clip(g + (E - g) * a.earth_sat, 0, 1)
    earth = Image.fromarray(np.clip(E * 255, 0, 255).astype(np.uint8))
    print("地球调色：gamma %.2f  饱和 ×%.2f" % (a.earth_gamma, a.earth_sat))

# ★ 临边变暗：还原球体的三维感（越靠边越暗，物理上对应 cos 入射角衰减）
if a.limb_dark > 0:
    E = np.asarray(earth).astype(np.float32) / 255.0
    h, w = E.shape[:2]
    yy4, xx4 = np.mgrid[0:h, 0:w]
    rr4 = np.hypot(xx4 - (w - 1) / 2, yy4 - (h - 1) / 2) / (w / 2)
    f = 1.0 - a.limb_dark * np.clip(rr4, 0, 1) ** 2.2
    E = np.clip(E * f[..., None], 0, 1)
    earth = Image.fromarray((E * 255).astype(np.uint8))
    print("临边变暗：强度 %.2f（边缘亮度 ×%.2f）" % (a.limb_dark, 1 - a.limb_dark))

# ★ 压高光：只做软膝，不做全局缩放
#   （2026-11-05 修正：以前用 E *= 200/255/p99 全局缩放，会把中间调一起压暗，
#     实测把 gamma+饱和的效果全抵消了：均亮 85.1 → 70.4）
if a.earth_p99 > 0:
    E = np.asarray(earth).astype(np.float32) / 255.0
    k = 0.62
    hi = E > k
    E[hi] = k + (1 - k) * np.tanh((E[hi] - k) / (1 - k) * 1.15) / np.tanh(1.15)
    earth = Image.fromarray(np.clip(E * 255, 0, 255).astype(np.uint8))
    print("高光软膝：截止 %.2f（不做全局缩放），p99 → %.0f"
          % (k, np.percentile(np.asarray(earth).mean(2), 99)))

# ★ 暗面微提：豆包把暗面压到 2，和星空一样黑，圆就"缺了一半"
if a.dark_lift > 1.0:
    E = np.asarray(earth).astype(np.float32)
    yy2, xx2 = np.mgrid[0:E.shape[0], 0:E.shape[1]]
    d2 = np.hypot(xx2 - E.shape[1] / 2, yy2 - E.shape[0] / 2) <= E.shape[1] / 2 * 0.99
    Ld = E.mean(2)
    dark = (Ld < 30) & d2
    E[dark] = np.clip(E[dark] * a.dark_lift, 0, 30)
    earth = Image.fromarray(np.clip(E, 0, 255).astype(np.uint8))
    print("暗面提亮：×%.2f（暗部均值 %.1f）"
          % (a.dark_lift, float(E.mean(2)[dark].mean()) if dark.any() else 0))

# ★ 亮度下限：让暗面一直延伸到球缘（否则圆会缺一块，看着不居中）
if a.dark_floor > 0:
    E = np.asarray(earth).astype(np.float32)
    yy3, xx3 = np.mgrid[0:E.shape[0], 0:E.shape[1]]
    d3 = np.hypot(xx3 - E.shape[1] / 2, yy3 - E.shape[0] / 2) <= E.shape[1] / 2 * 0.995
    for c in range(3):
        ch = E[..., c]
        ch[d3] = np.maximum(ch[d3], a.dark_floor)
        E[..., c] = ch
    earth = Image.fromarray(np.clip(E, 0, 255).astype(np.uint8))
    print("球面亮度下限：%.0f" % a.dark_floor)

# ★ 旋转（逆时针），让亮面对齐月面光照（月面亮部朝左上）
if abs(a.earth_rot) > 0.1:
    earth = earth.rotate(a.earth_rot, resample=Image.BICUBIC, expand=False)
    print("地球旋转：%.0f°（逆时针）" % a.earth_rot)

D = int(W * a.earth_pct)
earth = earth.resize((D, D), Image.LANCZOS)
mask = Image.new("L", (D, D), 0)
ImageDraw.Draw(mask).ellipse((0, 0, D - 1, D - 1), fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(1.0))

cx, cy = int(W * a.cx), int(H * a.cy)
# ★ 贴之前先把源图的"外圈天空"削掉：
#   地相图是正方形，圆盘外面还有它自己的背景（灰 8~12）。
#   如果圆盘没有精确内切，掩膜边缘会带进一圈源图天空
#   → 地球周围出现一圈淡淡的灰，像盖住了底图（2026-11-07 用户指出）。
#   做法：把掩膜半径收到 0.985D，再用羽化过渡；地球边缘本来就有大气渐变，收 1.5% 看不出。
_m2 = Image.new("L", (D, D), 0)
_pad = max(1, int(D * 0.0075))
ImageDraw.Draw(_m2).ellipse((_pad, _pad, D - 1 - _pad, D - 1 - _pad), fill=255)
mask = _m2.filter(ImageFilter.GaussianBlur(max(1.0, D * 0.002)))
base.paste(earth, (cx - D // 2, cy - D // 2), mask)
# ★ 月面加细颗粒：让月面与地球的"材质"统一
#   实测地球高频 std≈23、月面≈13，比值 1.8，看起来不像同一个镜头
if a.moon_grain > 0:
    A = np.asarray(base).astype(np.float32)
    hz = int(H * 0.595)
    rng = np.random.default_rng(20081026)
    sigma = 12.0 * a.moon_grain
    noise = rng.normal(0.0, sigma, (H - hz, W, 1)).astype(np.float32)
    # 按亮度加权：深阴影里少加（否则像雪花点），中间调加满
    base_lum = A[hz:].mean(2, keepdims=True)
    w = np.clip(base_lum / 55.0, 0.22, 1.0)
    A[hz:] = np.clip(A[hz:] + noise * w, 0, 255)
    base = Image.fromarray(A.astype(np.uint8))
    print("月面颗粒：sigma=%.1f（强度 %.2f）" % (sigma, a.moon_grain))

base.save(a.out)

print("输出 %s  %dx%d" % (a.out, W, H))
print("  地球直径 %d（%.0f%% 画宽）  中心 (%d,%d)" % (D, 100 * a.earth_pct, cx, cy))
print("  地球下缘 y=%d  地平线 y=%d  间距 %d px（占画高 %.1f%%）"
      % (cy + D // 2, hz, hz - (cy + D // 2), 100 * (hz - (cy + D // 2)) / H))
