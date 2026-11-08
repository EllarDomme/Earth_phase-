"""lighting.py —— 最后一步：按星历给"匀光地球"打光

上游产出的图是"均匀受光、无临边"的圆盘（豆包清过瑕疵）。
这里只做纯数学：
    out = col × limb(z) × (AMBIENT + (1-AMBIENT) × day(cosi))
其中 cosi 由日期/UTC 的日下点算出，limb 只看视角（与太阳无关）。

好处：光照完全确定，同一天跑一百次结果一致，不受 AI 随机性影响。
"""
import math

import numpy as np
from PIL import Image

import ephem_hp as E
from layout import disc_geom


def _unit(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return np.array([math.cos(la) * math.cos(lo),
                     math.cos(la) * math.sin(lo),
                     math.sin(la)])



def _srgb_to_linear(c):
    """sRGB 编码值 → 线性光（0~1）"""
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(x):
    """线性光 → sRGB 编码值（0~255）"""
    x = np.clip(x, 0.0, 1.0)
    v = np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)
    return np.clip(v * 255.0, 0, 255)


def cosi_map(date, utc, W, H, with_normal=False, geom=None):
    """返回 (cosi, z, rr)：cosi=太阳入射余弦，z=视角法向，rr=归一化半径。"""
    lat0, lon0 = E.sublunar_point(date, utc)
    slat, slon = E.subsolar_point(date, utc)

    V = _unit(lat0, lon0)
    S = _unit(slat, slon)

    # geom=(cx, cy, R) 可覆盖默认版面几何：
    #   月面版式用 layout 的 0.50/0.31/0.36，单张地球相用实测圆盘中心
    cx, cy, R = geom if geom is not None else disc_geom(W, H)
    yy, xx = np.mgrid[0:H, 0:W]
    u = (xx - cx) / R
    v = -(yy - cy) / R
    rr = np.hypot(u, v)
    z = np.sqrt(np.clip(1.0 - rr ** 2, 0, 1))

    e_x = np.cross([0, 0, 1.0], V)
    e_x /= np.linalg.norm(e_x)
    e_y = np.cross(V, e_x)

    n_x = u * e_x[0] + v * e_y[0] + z * V[0]
    n_y = u * e_x[1] + v * e_y[1] + z * V[1]
    n_z = u * e_x[2] + v * e_y[2] + z * V[2]
    cosi = n_x * S[0] + n_y * S[1] + n_z * S[2]
    if with_normal:
        return cosi, z, rr, (n_x, n_y, n_z), (V, S)
    return cosi, z, rr


def apply_lighting(img, date, utc, ambient=0.0002, limb_k=0.72, limb_p=0.45,
                   haze=0.0, arc=0.0, verbose=True, term_w=0.08, edge_soft=0.0,
                   geom=None):
    """给匀光圆盘打光。只改圆盘内，盘外一个像素不动。"""
    # ★ 打光必须在线性光空间做（2026-11-08）：
    #   sRGB 是伽马编码，直接乘光照系数会把中间调压暗，
    #   以前用 gamma 0.88 硬提亮来补偿 —— 那是错的。
    A_srgb = np.asarray(img.convert("RGB")).astype(np.float32)
    A = _srgb_to_linear(A_srgb) * 255.0          # 线性光，仍用 0~255 刻度

    # ★ 反照率上限（2026-11-08）：地表反射率不可能超过 1，
    #   现实中最亮的雪也只有 ~0.85。纹理里被上游提亮的云会到 1.5，
    #   那是物理上不存在的值，会在打光后变成纯白并丢层次。
    ALBEDO_CAP = float(globals().get("ALBEDO_CAP", 0.85))
    if ALBEDO_CAP > 0:
        A = np.minimum(A, ALBEDO_CAP * 255.0)
    H, W = A.shape[:2]

    # ★ ambient 在线性空间里的含义变了（2026-11-08）：
    #   真实夜/昼比约 1e-5 → sRGB 编码后就是 0，与太空无法区分（这正是物理事实）。
    #   取 0.002 使夜面 sRGB ≈ 2，和太空（≈1~2）同黑，既真实又不出现"黑洞"。
    cosi, z, rr, _NORMS, _VS = cosi_map(date, utc, W, H, with_normal=True, geom=geom)
    n_x, n_y, n_z = _NORMS
    Vw, Sw = _VS

    # 受光因子：过渡带宽度 term_w（cosi 单位）。
    # ★ 太窄会让"可见边界"在亮云/暗海之间跳，看着像折线；
    #   真实晨昏线被大气散射摊开很宽，所以这里默认就比渲染端宽。
    day = np.clip((cosi + 0.02) / term_w, 0, 1)
    day = day * day * (3 - 2 * day)

    # ★ 交界带柔化地表（在打光之前做！打光后再糊会把亮云和黑太空混成灰带）
    #   目的：抹掉"云块凸出导致的锯齿轮廓"，但不动亮面中心。
    EDGE_SOFT = edge_soft
    if EDGE_SOFT > 0:
        from PIL import ImageFilter as _IF
        import numpy as _np
        _g = A.astype(_np.uint8)
        _bl = np.asarray(Image.fromarray(_g).filter(
            _IF.GaussianBlur(2.0))).astype(np.float32)
        _w = np.exp(-((cosi / 0.13) ** 2)) * EDGE_SOFT
        A = A * (1.0 - _w[..., None]) + _bl * _w[..., None]

    limb = limb_k + (1.0 - limb_k) * np.clip(z, 0, 1) ** limb_p
    # ★ 暮光漫射（2026-11-07 补）：晨昏线附近，太阳已落到地平线下，
    #   但大气仍把光散射到地表 —— 这就是暮光。缺了它，明暗会"一刀切"
    #   （实测相邻两档 2.6 → 90.4，太硬）。
    #   强度取昼面的 ~6%，范围到 cosi≈-0.15（对应太阳低下 9°）。
    TWILIGHT = float(globals().get("TWILIGHT", 0.025))
    _tw = 0.0
    if TWILIGHT > 0:
        _tw = np.clip((cosi + 0.15) / 0.20, 0, 1)
        _tw = _tw * _tw * (3 - 2 * _tw) * (1.0 - day) * TWILIGHT

    # ★ 朗伯余弦定律（2026-11-08 关键修正）：
    #   真实漫反射体 radiance ∝ cos(入射角)，太阳越低越暗。
    #   以前 shade 只用 day（阶跃：受光=1），等于把整个亮面拉平，
    #   所以画面"没有球体感"、交界处不自然。
    #   曝光是相机选择，用 EXPOSURE 把整体拉回合适亮度（不改变相对关系）。
    EXPOSURE = float(globals().get("EXPOSURE", 1.70))
    lambert = np.clip(cosi, 0.0, 1.0)
    # ★ 暮光必须独立于朗伯余弦（2026-11-08 修）：
    #   暮光是大气散射光，cosi<0（已入夜）时地表照样被照亮；
    #   之前写成 day*lambert，lambert 在夜侧为 0，把暮光整项乘没了。
    shade = (ambient + (1.0 - ambient) * (day * lambert + _tw)) * limb * EXPOSURE

    # ★ 只改圆盘内！盘外的月面与星空一个像素都不许动
    #   （第一版忘了这层掩膜，把左半边月面一起打暗了）
    inside = rr <= 1.0
    edge = np.clip((1.0 - rr) / 0.004, 0, 1)        # 球缘 1px 过渡，避免硬边
    w = (inside.astype(np.float32) * edge)[..., None]

    out = A * (1.0 - w) + A * shade[..., None] * w

    # ★ 夜面地板（2026-11-08）：真实月相照里，月面夜部亮度 4.6、天空 2.5，
    #   夜面略亮于天空；而我们打光后夜面掉到 0，比太空还暗，轮廓像"洞"。
    #   这里给盘内一个极小的底板，让夜面与真实照片的观感一致。
    NIGHT_SRGB = float(globals().get("NIGHT_SRGB", 3.5))
    if NIGHT_SRGB > 0:
        _floor = float(_srgb_to_linear(np.array([[[NIGHT_SRGB]]], dtype=np.float32))[0, 0, 0])
        _in = (rr <= 1.0)[..., None]
        out = np.where(_in, np.maximum(out, _floor * 255.0), out)

    # ★ 输出封顶（2026-11-08）：EXPOSURE 是显示增益，会把亮云推出物理上限，
    #   打光后云边出现"过曝白边"（实测 p99 226 → 254，裁切像素 63 → 686）。
    #   这里把漫反射结果收在反照率上限（0.85）以内，高光层次保住、不再裁切。
    #   大气弧与耀斑是附加光，不在此列。
    if ALBEDO_CAP > 0:
        out = np.minimum(out, ALBEDO_CAP * 255.0)

    # ★ 太阳耀斑（2026-11-08 补）：海面对太阳的镜面反射。
    #   物理：反射最强处 = 表面法线平分"太阳方向"与"视线"。
    #   正交投影下视线恒为 e_z（指向观察者），故：
    #       H = normalize(S + e_z)      glint ∝ (N·H)^n
    #   n 由海面粗糙度决定（越大越锐），只作用在海面。
    # ★ 大气辉光（2026-11-08 补）：纹理是"去大气"的校正反射率，
    #   而地球上空的瑞利散射正是"地球从太空看是蓝的"的主因。
    #   这里按受光段加一层极淡的蓝色气辉，把它补回来（物理上是还原，不是美化）。
    HAZE_K = float(globals().get("HAZE_K", 0.0))   # 全局浊光：会把云和陆地一起冲淡，默认关
    if HAZE_K > 0:
        # 视线穿过的大气量 ~ 1/cos(视天顶角)，用 z 近似
        airmass_view = 1.0 / np.maximum(z, 0.12)
        # 基础量（垂直路径也有大气）+ 临边增强（斜穿更厚）
        haze_amt = HAZE_K * 255.0 * (1.0 + 0.5 * np.clip(airmass_view - 1.0, 0, 2.0))
        haze_amt = haze_amt * day * (rr <= 1.0)
        # 瑞利散射的三通道权重（蓝最强），再压一点红
        haze_col = np.array([0.22, 0.48, 1.00], np.float32)
        out = out + haze_amt[..., None] * haze_col

    # ★ 太阳耀斑（Cox–Munk 波面斜率 + 菲涅尔，2026-11-08 强化）
    #   真实海面不是镜面，而是无数倾斜小面；它们的斜率服从高斯分布。
    #   菲涅尔反射率随入射角上升（掠射趋近 1），所以光斑边缘会有渐变。
    #     R(θi) = 0.02 + 0.98·(1-cosθi)^5
    #     p(β)  = exp(-tan²β / 2σ²) / (2πσ² cos³β)
    #     σ²    = 0.003 + 0.00512·U      （U=风速 m/s，Cox-Munk）
    GLINT_SUN = float(globals().get("GLINT_SUN", 0.0))   # 关：数据无浪面细节，合成出来像雾团
    GLINT_GAIN = float(globals().get("GLINT_GAIN", 0.0))   # 旧的附加增益，默认关
    WIND_MS = float(globals().get("WIND_MS", 0.8))
    if GLINT_SUN > 0 or GLINT_GAIN > 0:
        Hx, Hy, Hz = Sw[0] + Vw[0], Sw[1] + Vw[1], Sw[2] + Vw[2]
        _hn = np.sqrt(Hx * Hx + Hy * Hy + Hz * Hz) + 1e-9
        Hx, Hy, Hz = Hx / _hn, Hy / _hn, Hz / _hn

        # 半角向量与法线夹角 β（碟外法线不是单位向量，先归一）
        _nn = np.sqrt(n_x ** 2 + n_y ** 2 + n_z ** 2) + 1e-9
        cosb = np.clip((n_x * Hx + n_y * Hy + n_z * Hz) / _nn, 0.02, 1.0)
        beta = np.arccos(cosb)

        # 菲涅尔：入射角 = 太阳与半角向量夹角
        cos_i = np.clip(Sw[0] * Hx + Sw[1] * Hy + Sw[2] * Hz, 0.0, 1.0)
        fres = 0.02 + 0.98 * (1.0 - cos_i) ** 5

        # Cox-Munk 斜率分布
        sigma2 = 0.003 + 0.00512 * max(WIND_MS, 0.5)
        tanb = np.tan(np.clip(beta, 0, 1.53))
        pdf = np.exp(-tanb ** 2 / (2 * sigma2)) / (2 * np.pi * sigma2 * np.maximum(cosb, 0.05) ** 3)
        # ★ 不再"归一化后再放大"——那会把高斯顶部压成一片白平台。
        #   真实耀斑 = 太阳辐亮度 × 菲涅尔 × 波面斜率概率：
        #   只有最正对太阳的一小块会饱和，其余按 pdf 平滑衰减。
        spec = fres * pdf * GLINT_SUN
        spec = spec * (rr <= 1.0)

        # ★ 海面掩膜收紧（2026-11-08）：原先模糊 3px 会溢到云和陆地上，
        #   豆包反馈"像一团贴上去的白雾"。现在只取纯海水，并把边缘收进海面内部。
        _L0 = A_srgb.mean(2)
        _raw = ((A_srgb[..., 2] - A_srgb[..., 0]) > 6) & (_L0 < 72)
        from PIL import ImageFilter as _IF3
        _m = Image.fromarray((_raw * 255).astype(np.uint8)).filter(_IF3.GaussianBlur(1))
        wmask = np.clip((np.asarray(_m).astype(np.float32) / 255.0 - 0.35) / 0.5, 0, 1)

        # ★ 浪面碎光（2026-11-08）：真实耀斑是无数浪面的碎反光，不是一片均匀亮。
        #   用画面自身高频 + 固定种子噪声调制，让它碎开（种子固定，结果可复现）。
        _blur = Image.fromarray(_L0.astype(np.uint8)).filter(_IF3.GaussianBlur(6))
        _hf = np.abs(_L0 - np.asarray(_blur).astype(np.float32))
        _hf = _hf / (_hf.max() + 1e-6)
        speckle = 0.35 + 1.65 * _hf
        _rng = np.random.default_rng(7)
        _nz = _rng.normal(0, 1, _L0.shape).astype(np.float32)
        _nz = np.asarray(Image.fromarray(((_nz * 40) + 128).clip(0, 255).astype(np.uint8))
                         .filter(_IF3.GaussianBlur(1))).astype(np.float32)
        speckle = speckle * np.clip(1.0 + 0.55 * (_nz - 128) / 40.0, 0.25, 2.2)
        speckle = np.where(rr <= 1.0, speckle, 0.0)

        if GLINT_GAIN > 0:
            spec = spec + spec * GLINT_GAIN / 255.0
        out = out + (spec * wmask * speckle)[..., None]

    # ★ 海面补蓝（2026-11-08）：纹理是"去大气"的，海水的蓝被一起削掉了。
    #   但整幅加蓝雾会冲淡云和陆地（试过，很难看），所以只补海面：
    #   按"偏蓝且暗"识别海水，只在受光侧加蓝，云和陆地一个像素不动。
    WATER_BLUE = float(globals().get("WATER_BLUE", 0.0))   # 关：人工补蓝属于调色，豆包指出蓝色过艳
    if WATER_BLUE > 0:
        _R0, _B0 = A_srgb[..., 0], A_srgb[..., 2]
        _water = ((_B0 - _R0) > 5) & (A_srgb.mean(2) < 75)
        from PIL import ImageFilter as _IF4
        _wm2 = Image.fromarray((_water * 255).astype(np.uint8)).filter(_IF4.GaussianBlur(4))
        _wmask2 = np.asarray(_wm2).astype(np.float32) / 255.0
        _wmask2 = _wmask2 * day * (rr <= 1.0)
        out = out + _wmask2[..., None] * np.array([0.0, WATER_BLUE * 0.23, WATER_BLUE], np.float32)

    # ★ 大气弧：紧贴球缘、只出现在受光侧（cosi>0），打光后叠加
    # ★ 大气弧要"细"：真实照片里只是球缘一条很窄的亮线（不是宽光晕）。
    #   2026-11-07 用户反馈"太宽不真实"，从 0.020/0.55 收到 0.006/0.20。
    # 严格物理：蓝光核心 30~40 km ≈ 0.5% 半径；散射尾到 100 km ≈ 1.6%
    ARC_W = float(globals().get("ARC_W", 0.004))
    ARC_A = float(globals().get("ARC_A", 0.020))
    if ARC_W > 0 and ARC_A > 0:
        _rr = np.sqrt(np.clip(rr, 0, 1.2))
        ring = np.exp(-((_rr - 1.0) / ARC_W) ** 2)
        # ★ 弧光不能到 cosi=0 就断：大气柱在晨昏线外仍被照亮（暮光带），
        #   所以用软过渡，从夜侧 cosi=-0.12 渐入、到 +0.18 全亮，
        #   这样弧光看起来是"绕着受光缘一整圈"，而不是只有半截。
        # 暮光带宽度按物理定：大气顶 100 km → 太阳落到地平线下 ~9° 仍受光
        #   cosi = -sin(9°) ≈ -0.15 … 这里取 -0.09~+0.09 的对称软过渡
        _w = np.clip((cosi + 0.09) / 0.18, 0, 1)
        _w = _w * _w * (3 - 2 * _w)
        # ★ 瑞利光谱（2026-11-08）：散射截面 ∝ 1/λ⁴，蓝比红强约 4.4 倍。
        #   受光缘光程短 → 蓝白；越靠晨昏线光程越长 → 蓝被散掉，转琥珀（日落）。
        #   光学厚度用"大气质量"近似：airmass = 1 / sin(太阳高度)
        air = np.clip(1.0 / np.maximum(np.clip(cosi, 0.0, 1.0), 0.03), 1.0, 12.0)
        t = np.clip((air - 1.0) / 6.0, 0, 1) ** 0.8

        wR, wG, wB = 1 / 650.0 ** 4, 1 / 546.0 ** 4, 1 / 435.0 ** 4
        mx = max(wR, wG, wB)
        ray = np.array([wR / mx, wG / mx, wB / mx], np.float32)   # ≈ .20/.40/1.0
        sunset = np.array([1.00, 0.55, 0.22], np.float32)
        col = ray[None, None, :] * (1 - t[..., None]) + sunset[None, None, :] * t[..., None]

        # ★ 亮度关系（2026-11-08 修）：不能用 sqrt(air)。
        #   air 变大只是因为光程更长，但那部分气体受照更弱；
        #   真实观测是"白昼段最亮（蓝白），靠晨昏变暗、变深红"。
        _gain = 1.0 / (1.0 + 0.35 * (air - 1.0))     # 光程越长越暗
        ring = ring * _w * _gain * ARC_A * 255.0

        # ★ 外延薄晕（2026-11-08）：真实大气辉光 = 亮核心 + 淡而宽的外层，
        #   那是同一层大气散射的尾部（瑞利 + 多次散射），不是镜头效果。
        #   强度只有核心的 1/4，宽度约 4%，几像素就融进黑太空。
        ARC_W2 = float(globals().get("ARC_W2", 0.018))
        ARC_A2 = float(globals().get("ARC_A2", 0.008))
        if ARC_W2 > 0 and ARC_A2 > 0:
            halo = np.exp(-((_rr - 1.0) / ARC_W2) ** 2)
            halo = halo * _w * _gain * ARC_A2 * 255.0
            ring = ring + halo

        out = out + ring[..., None] * col
    out = np.clip(out, 0, 255)

    # ★ 晨昏带局部柔化（2026-11-07）：
    #   边界在"亮云/暗海"之间跳，放大看像折线。真实晨昏线被大气散射糊开，
    #   所以在 cosi≈0 附近把图像往低频拉一点，折角就被抹平。
    ATM_BLUR = 0.0
    if ATM_BLUR > 0:
        from PIL import ImageFilter as _IF
        import numpy as _np
        _g = _np.clip(out * 255.0, 0, 255).astype(_np.uint8)
        _bl = _np.asarray(Image.fromarray(_g).filter(
            _IF.GaussianBlur(3.0))).astype(_np.float32)
        _w = _np.exp(-((cosi / 0.16) ** 2)) * ATM_BLUR
        out = out * (1.0 - _w[..., None]) + _bl * _w[..., None]


    if verbose:
        m = rr < 0.95
        o = _linear_to_srgb(out / 255.0)
        print("   打光：昼面均亮 %.0f   夜面均亮 %.0f"
              % (o[m & (cosi > 0.3)].mean(), o[m & (cosi < -0.3)].mean()))
    return Image.fromarray(_linear_to_srgb(out / 255.0).astype(np.uint8))
