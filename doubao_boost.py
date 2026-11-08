"""doubao_boost.py —— 对月面合成图做"提升清晰度"的豆包工序

流程（用户 2026-11-05 指定）：
  ① 把最新的月面合成图丢给豆包，提示词固定（PROMPT_BOOST）
  ② 处理完点「引用右边的下载原图」（第三人称图标，已有方法）
  ③ 拿到图后【压回地球暗部亮度】——豆包会自动提亮暗部
  ④ 还原成 1920×1280（豆包固定返回 1536 方图，需要按内容裁回 3:2）

用法:
  python doubao_boost.py <月面图> [--out 输出.png]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image
from layout import EARTH_CX, EARTH_CY, EARTH_PCT, disc_geom

HERE = os.path.dirname(os.path.abspath(__file__))
import config as _cfg
NODE = _cfg.NODE

PROMPT_BOOST = ("提高地球清晰度，加强锐度，把地球亮面做成更自然的卫星照片质感："
                "减少硬锐边，恢复一点真实压缩感和大气柔边，同时保留比原图更高的清晰度。"
                # ★ 暗面约束（2026-11-05）：实测能把暗面提亮从 ×11 降到 ×4
                "严格保持地球暗部原有的深黑，不要提亮暗部，"
                "不要在暗部补充或添加任何云层、陆地、细节。"
                # ★ 亮度约束（2026-11-08 用户确认）：豆包曾把地球亮面压暗 34%
                #   （实测 2002-10-01：99.8 → 65.5），只改清晰度、不动曝光。
                "【亮度不可变】地球的整体亮度与曝光必须与原图保持一致，"
                "不要压暗也不要提亮；只提高清晰度，不确定时保持原亮度不变。")

LAST = {"title": "", "url": ""}


def run_once(image_path, out_dir, prompt, timeout_ms=900000):
    req = {"prompt": prompt, "refImages": [image_path], "outDir": out_dir,
           "newChat": True, "timeoutMs": timeout_ms}
    rf = os.path.join(out_dir, "_req_boost.json")
    with open(rf, "w", encoding="utf-8") as f:
        json.dump(req, f, ensure_ascii=False)
    p = subprocess.run([NODE, os.path.join(HERE, "doubao_run.mjs"), rf],
                       capture_output=True, timeout=timeout_ms / 1000 + 240)
    out = p.stdout.decode("utf-8", "ignore").strip()
    for ln in out.splitlines():
        if ln.startswith(("[页面]", "[上传]")):
            print("   " + ln)
        if ln.startswith("CONV_TITLE="):
            LAST["title"] = ln.split("=", 1)[1].strip()
            print("   [对话] " + LAST["title"])
        if ln.startswith("CONV_URL="):
            LAST["url"] = ln.split("=", 1)[1].strip()
    k = out.find("RESULT_JSON=")
    if k < 0:
        raise RuntimeError("doubao_run 无结果：" + (p.stderr.decode("utf-8", "ignore"))[-300:])
    data = json.loads(out[k + len("RESULT_JSON="):].splitlines()[0])
    if not data.get("ok"):
        raise RuntimeError("豆包失败：" + str(data.get("error"))[:300])
    return data["files"]


def download_original(out_dir):
    """点「下载原图」（引用右边第三个图标）"""
    dl = os.path.join(out_dir, "_official_dl_boost")
    r = subprocess.run([NODE, os.path.join(HERE, "doubao_download.mjs"),
                        "--out", dl, "--wait", "60000"],
                       capture_output=True, text=True, timeout=300)
    for ln in (r.stdout or "").splitlines():
        if ln.startswith(("[下载原图]", '{"ok"')):
            print("   " + ln[:150])
    for ln in (r.stdout or "").splitlines():
        if ln.startswith('{"ok"'):
            j = json.loads(ln)
            if j.get("ok") and os.path.exists(j["file"]):
                return j["file"]
    return None


def crop_to_content(img):
    """豆包返回 1536 方图，找出真正的画面范围（裁掉黑边）"""
    a = np.asarray(img.convert("L")).astype(np.float32)
    m = a > 6
    rows = np.where(m.sum(1) > a.shape[1] * 0.02)[0]
    cols = np.where(m.sum(0) > a.shape[0] * 0.02)[0]
    if not len(rows) or not len(cols):
        return img
    return img.crop((cols.min(), rows.min(), cols.max() + 1, rows.max() + 1))




def align_to_source(img, src, max_shift=120):
    """把豆包返回的图对齐到原图：只用平移（豆包只裁剪、不缩放）。

    做法：两张图缩到 240 宽，穷举竖直/水平位移，取相关性最高的一组。
    比"检测圆盘"稳——豆包输出常带 JPEG 噪点，阈值法会把半径算大。
    """
    w0, h0 = src.size
    sw = 240
    sh = int(h0 * sw / w0)
    a = np.asarray(src.convert("L").resize((sw, sh), Image.LANCZOS)).astype(np.float32)
    b = np.asarray(img.convert("L").resize((sw, sh), Image.LANCZOS)).astype(np.float32)

    best = None
    step = 2 if max_shift > 60 else 1
    for dy in range(-max_shift, max_shift + 1, step):
        for dx in range(-max_shift // 2, max_shift // 2 + 1, step):
            bb = np.roll(np.roll(b, -dy, axis=0), -dx, axis=1)
            c = float(np.corrcoef(a.ravel(), bb.ravel())[0, 1])
            if best is None or c > best[0]:
                best = (c, dx, dy)
    c, dx, dy = best
    k = w0 / sw
    DX, DY = dx * k, dy * k
    out = img.transform((w0, h0), Image.AFFINE, (1, 0, -DX, 0, 1, -DY),
                        resample=Image.BICUBIC)
    print("   对齐：平移 (%+.0f, %+.0f) px，相关 %.4f" % (DX, DY, c))
    return out


def remove_watermark(img, source=None):
    """去右下角水印：取原图同位置小块，用【梯度域融合】消掉接缝。

    做法：
      1. 取原图同一位置的一块（那里没有水印）
      2. 计算"豆包版 − 原图块"在边界上的差值
      3. 把这个差值做成平滑场，加回去 → 边界自然连续
    """
    from PIL import ImageFilter

    if source is None:
        print("   没有原图可参考，跳过去水印")
        return img

    A = np.asarray(img.convert("RGB")).astype(np.float32)
    B = np.asarray(source.convert("RGB").resize(img.size, Image.LANCZOS)).astype(np.float32)
    H, W = A.shape[:2]

    x0, y0, x1, y1 = int(W * 0.855), int(H * 0.928), W, H
    pad = 30
    px0, py0 = max(0, x0 - pad), max(0, y0 - pad)

    patch = B[y0:y1, x0:x1].copy()
    target = A[y0:y1, x0:x1]

    # 差值场（豆包版 - 原图），只在边界附近可信，用大半径模糊外推
    diff = (target - patch)
    big = np.zeros_like(A)
    big[y0:y1, x0:x1] = diff
    d_img = Image.fromarray(np.clip(big + 128, 0, 255).astype(np.uint8))
    d_blur = np.asarray(d_img.filter(ImageFilter.GaussianBlur(28))).astype(np.float32) - 128

    merged = patch + d_blur[y0:y1, x0:x1]
    A[y0:y1, x0:x1] = np.clip(merged, 0, 255)

    out = Image.fromarray(np.clip(A, 0, 255).astype(np.uint8))
    print("   去水印：原图小块 + 梯度域融合（%dx%d）" % (x1 - x0, y1 - y0))
    return out



def _apply_gain_soft(A, gain, knee=0.80, ceil=0.941):
    """线性乘增益 + 高光软膝：中间调按物理提亮，高光渐近 ceil（约 248）永不削顶。

    ceil 不能取 1.0——tanh 的渐近线就是渐近线，取 1.0 依然会顶到 255。
    0.941 ≈ 240：再高冰盖会有一半像素挤在 245+，丢掉明暗层次。
    """
    x = np.clip(A / 255.0 * gain[..., None], 0, None)
    hi = x > knee
    span = ceil - knee
    y = np.where(hi, knee + span * np.tanh((x - knee) / span * 1.4) / np.tanh(1.4), x)
    return np.clip(y, 0, ceil) * 255.0


def blend_by_phase(boosted, original, lo=40.0, hi=150.0, soft=0):
    """按原图的相位做平滑过渡：暗面用原图，亮面用豆包版。

    alpha 由【二值掩膜的模糊】得到（按距离过渡），
    不能模糊亮度——那样亮边的亮度会扩散进暗面，
    导致暗面 alpha 虚高、豆包的亮块漏进来。
    """
    from PIL import ImageFilter

    A = np.asarray(boosted.convert("RGB")).astype(np.float32)
    B = np.asarray(original.convert("RGB").resize(boosted.size, Image.LANCZOS)).astype(np.float32)
    H, W = A.shape[:2]
    cx, cy, _R = disc_geom(W, H)
    cx, cy, D = int(cx), int(cy), int(2 * _R)
    yy, xx = np.mgrid[0:H, 0:W]
    disc = (np.hypot(xx - cx, yy - cy) <= D / 2 * 1.01)

    Lb = B.mean(2)
    # 直接按源图亮度做平滑过渡：40 以下纯暗面，150 以上纯豆包
    t = np.clip((Lb - lo) / max(hi - lo, 1e-3), 0, 1)
    alpha = (t * t * (3 - 2 * t))[..., None]
    alpha = np.where(disc[..., None], alpha, 0.0)

    # 亮部统一增益（只改亮度，不改对比）
    litmask = disc & (Lb > hi)
    La = A.mean(2)
    if litmask.sum() > 2000:
        g = float(Lb[litmask].mean() / max(La[litmask].mean(), 1e-3))
        g = float(np.clip(g, 0.5, 1.8))
        A = _apply_gain_soft(A, np.float32(g))
        print("   亮部增益 ×%.3f（线性 + 高光软膝）" % g)

    out = A * alpha + B * (1 - alpha)
    band = (alpha[..., 0] > 0.02) & (alpha[..., 0] < 0.98)
    out = np.where(band[..., None], np.maximum(out, B * 0.94), out)

    frac = float((alpha[..., 0] < 0.5).mean() * 100)
    print("   按相位融合：暗面 %.0f%% 用原图，亮面 %.0f%% 用豆包版（过渡 %d px）"
          % (frac, 100 - frac, soft))
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

def restore_scene(boosted, original):
    """把地球圆盘以外的部分（月面+星空）亮度拉回原图水平。

    豆包会顺手改整体曝光；只在盘内做直方图匹配的话，
    盘外的月面还是会跟着变（实测 -3.5%）。
    """
    A = np.asarray(boosted.convert("RGB")).astype(np.float32)
    B = np.asarray(original.convert("RGB").resize(boosted.size, Image.LANCZOS)).astype(np.float32)
    H, W = A.shape[:2]
    cx, cy, _R = disc_geom(W, H)
    cx, cy, D = int(cx), int(cy), int(2 * _R)
    yy, xx = np.mgrid[0:H, 0:W]
    outside = np.hypot(xx - cx, yy - cy) > D / 2 * 1.02   # 圆盘外（留 2% 余量）

    La, Lb = A.mean(2), B.mean(2)
    m = outside & (Lb > 8)          # 只统计有内容的月面，避开纯黑天空
    if m.sum() < 5000:
        return boosted
    cur, ref = float(La[m].mean()), float(Lb[m].mean())
    k = ref / max(cur, 1e-3)
    print("   月面亮度：豆包版 %.1f → 目标 %.1f（×%.3f）" % (cur, ref, k))
    if abs(k - 1.0) < 0.01:
        return boosted
    A = np.where(outside[..., None], np.clip(A * k, 0, 255), A)
    return Image.fromarray(np.clip(A, 0, 255).astype(np.uint8))



def match_disc(boosted, original, label="地球"):
    """把地球**圆盘内**的亮度拉回原图水平。

    豆包"提清晰度"时会顺手改曝光；restore_scene 只还原盘外，
    盘内曾出现整体被压暗 36% 的情况（实测 2002-10-01 提升/月面 = 0.64）。
    """
    A = np.asarray(boosted.convert("RGB")).astype(np.float32)
    B = np.asarray(original.convert("RGB").resize(boosted.size, Image.LANCZOS)).astype(np.float32)
    H, W = A.shape[:2]
    cx, cy, _R = disc_geom(W, H)
    D = int(2 * _R)
    yy, xx = np.mgrid[0:H, 0:W]
    inside = np.hypot(xx - cx, yy - cy) <= D / 2 * 0.98

    La, Lb = A.mean(2), B.mean(2)
    m = inside & (Lb > 8)          # 只统计有内容的盘内像素，避开纯黑夜面
    if m.sum() < 5000:
        return boosted
    cur, ref = float(La[m].mean()), float(Lb[m].mean())
    k = ref / max(cur, 1e-3)
    print("   %s亮度：豆包版 %.1f → 目标 %.1f（×%.3f）" % (label, cur, ref, k))
    if abs(k - 1.0) < 0.02:
        return boosted
    A = np.where(inside[..., None], np.clip(A * k, 0, 255), A)
    return Image.fromarray(np.clip(A, 0, 255).astype(np.uint8))


def keep_night_side(boosted, original, thresh=22, feather=14):
    """暗面用原图，亮面用豆包版。

    豆包会往暗面里"补"出云和地形——那些是它编的，不是真实夜面。
    亮度可以匹配回来，编出来的结构匹配不掉，所以直接换回原图。
    """
    from PIL import ImageFilter

    A = np.asarray(boosted.convert("RGB")).astype(np.float32)
    B = np.asarray(original.convert("RGB").resize(boosted.size, Image.LANCZOS)).astype(np.float32)
    Lb = B.mean(2)

    m = (Lb < thresh).astype(np.float32)
    m_img = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(feather))
    m = np.asarray(m_img).astype(np.float32) / 255.0
    m = np.clip(m * 1.15, 0, 1)[..., None]

    out = A * (1 - m) + B * m
    frac = float((m > 0.5).mean())
    print("   暗面换回原图：覆盖画面 %.0f%%（阈值 %.0f，羽化 %d px）"
          % (frac * 100, thresh, feather))
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))



def deglint(img, date, utc, strength=0.55):
    """把渲染端"耀斑压制"压掉的日下点亮度补回来（只在受光面内）。

    渲染端为了压白斑，把 cos(入射角) 附近乘了 (1 - k*exp(-(ang/0.4)^2))。
    这里乘它的倒数，让"亮度 ∝ cos(入射角)"恢复。
    """
    import math as _m
    import ephem_hp as _E

    if not date or utc is None or strength <= 0:
        return img

    def unit(lat, lon):
        la, lo = _m.radians(lat), _m.radians(lon)
        return np.array([_m.cos(la) * _m.cos(lo), _m.cos(la) * _m.sin(lo), _m.sin(la)])

    lat0, lon0 = _E.sublunar_point(date, utc)
    S = unit(*_E.subsolar_point(date, utc))
    V = unit(lat0, lon0)

    A = np.asarray(img.convert("RGB")).astype(np.float32)
    H, W = A.shape[:2]
    _cx, _cy, R = disc_geom(W, H)
    cx, cy = int(_cx), int(_cy)
    yy, xx = np.mgrid[0:H, 0:W]
    u = (xx - cx) / R
    v = -(yy - cy) / R
    z2 = 1 - u * u - v * v
    inside = z2 > 0
    z = np.sqrt(np.clip(z2, 0, None))

    e_x = np.cross([0, 0, 1.0], V); e_x /= np.linalg.norm(e_x)
    e_y = np.cross(V, e_x)
    nx = u * e_x[0] + v * e_y[0] + z * V[0]
    ny = u * e_x[1] + v * e_y[1] + z * V[1]
    nz = u * e_x[2] + v * e_y[2] + z * V[2]
    cosi = nx * S[0] + ny * S[1] + nz * S[2]
    ang = np.arccos(np.clip(cosi, -1, 1))

    gain = 1.0 / np.clip(1.0 - strength * np.exp(-(ang / 0.40) ** 2), 0.35, 1.0)

    L = A.mean(2)
    lit = inside & (cosi > -0.02) & (L > 12)
    before = float(A[lit].mean()) if lit.any() else 0
    # 用伽马方式提亮，而不是直接乘：高光渐近 255，永远不会被削平
    #   （直接乘会把云推到 255，实测过曝占比 14.9%）
    tmp = _apply_gain_soft(A, gain.astype(np.float32))
    A[lit] = tmp[lit]
    after = float(A[lit].mean()) if lit.any() else 0
    print("   光照补偿：受光面均亮 %.1f → %.1f（强度 %.2f）" % (before, after, strength))
    return Image.fromarray(np.clip(A, 0, 255).astype(np.uint8))




def clean_rim(img, feather=2.0, ss=4):
    """按设计半径重建一圈抗锯齿边缘。

    原因：合成时用的是 1px 羽化的圆，豆包提清晰度会把这 1px 放大成毛边，
    在纯黑背景上（尤其南极冰盖那种高亮边缘）就成了一圈锯齿。
    这里用 4 倍超采样画圆再降采样，得到真正平滑的边界。
    """
    from PIL import ImageDraw, ImageFilter

    A = img.convert("RGB")
    W, H = A.size
    cx, cy, R = disc_geom(W, H)

    big = int(max(W, H) * ss / 4) if ss > 1 else max(W, H)    # 控制内存
    k = ss / 4.0 if ss > 1 else 1.0
    bw, bh = int(W * k), int(H * k)

    m = Image.new("L", (bw, bh), 0)
    d = ImageDraw.Draw(m)
    r = R * k
    d.ellipse((cx * k - r, cy * k - r, cx * k + r, cy * k + r), fill=255)
    if feather > 0:
        m = m.filter(ImageFilter.GaussianBlur(feather * k))
    m = m.resize((W, H), Image.LANCZOS)

    # ★ 只在"地球圆盘 + 外扩 4px"的范围内重画，其余（月面、星空）一个像素不动
    pad = 4
    x0 = max(0, int(cx - R) - pad)
    y0 = max(0, int(cy - R) - pad)
    x1 = min(W, int(cx + R) + pad)
    y1 = min(H, int(cy + R) + pad)

    out = A.copy()
    disc = A.crop((x0, y0, x1, y1))
    orig = A.crop((x0, y0, x1, y1))
    mm = m.crop((x0, y0, x1, y1))
    # ★ 圆盘外要保留"原图的天空"，不能填黑——
    #   填黑会在框内留下一块纯黑矩形（天空原本是 2~3 的灰），
    #   于是图上出现一个看得见的方框（2026-11-06 踩过）。
    fixed = Image.composite(disc, orig, mm)
    out.paste(fixed, (x0, y0))
    return out



def finish_tone(img, date, utc, desat=0.0, limb_gain=0.22):
    """收尾两道：

    ① 晨昏线去色偏（默认关闭：实测那个蓝主要是海水+暮光，去色反而发灰），
       真实是"偏蓝"但不是这种青绿。只在 cosi 0~0.25 做部分去饱和。
    ② 亮缘大气弧：亮侧球缘加一层极淡的蓝白光，
       真实照片里对着太阳那一侧的大气弧最明显。
    """
    import math as _m
    import ephem_hp as _E

    if not date or utc is None:
        return img

    def unit(lat, lon):
        la, lo = _m.radians(lat), _m.radians(lon)
        return np.array([_m.cos(la) * _m.cos(lo), _m.cos(la) * _m.sin(lo), _m.sin(la)])

    lat0, lon0 = _E.sublunar_point(date, utc)
    S = unit(*_E.subsolar_point(date, utc))
    V = unit(lat0, lon0)

    A = np.asarray(img.convert("RGB")).astype(np.float32)
    H, W = A.shape[:2]
    cx, cy, R = int(0.50 * W), int(0.31 * H), int(0.36 * W / 2)
    yy, xx = np.mgrid[0:H, 0:W]
    u = (xx - cx) / R
    v = -(yy - cy) / R
    rr = np.hypot(u, v)
    z = np.sqrt(np.clip(1 - rr ** 2, 0, 1))
    e_x = np.cross([0, 0, 1.0], V); e_x /= np.linalg.norm(e_x)
    e_y = np.cross(V, e_x)
    nx = u * e_x[0] + v * e_y[0] + z * V[0]
    ny = u * e_x[1] + v * e_y[1] + z * V[1]
    nz = u * e_x[2] + v * e_y[2] + z * V[2]
    cosi = nx * S[0] + ny * S[1] + nz * S[2]
    inside = rr < 0.995

    # ① 晨昏线去色偏：cosi 0.02~0.25 区间把色度往亮度拉
    # 蓝绿偏色其实落在"刚入夜"那一侧（cosi ≈ 0 ~ -0.1），
    # 所以区间要往夜面延伸：峰值在 cosi=0，两侧衰减
    t = np.clip(1.0 - np.abs(cosi - 0.01) / 0.16, 0, 1)
    w = (t * t * (3 - 2 * t)) * inside * desat
    L = A.mean(2, keepdims=True)
    A = A + (L - A) * w[..., None]

    # ② 亮缘大气弧：球缘 0.965~1.0 之间，亮侧加一点蓝白
    rim = np.exp(-((rr - 0.985) / 0.012) ** 2) * np.clip(cosi, 0, 1) ** 1.5
    rim = rim * inside * limb_gain * 60.0
    A = np.clip(A + rim[..., None] * np.array([0.72, 0.85, 1.0], np.float32), 0, 255)

    print("   收尾：晨昏线去色偏 %d%%（cosi 0~0.25）　亮缘大气弧 +%.0f%%"
          % (desat * 100, limb_gain * 100))
    return Image.fromarray(A.astype(np.uint8))


def physics_report(img, date, utc):
    """按星历核算光照，输出体检报告；返回是否通过。"""
    import math as _m
    import ephem_hp as _E

    if not date or utc is None:
        return True

    def unit(lat, lon):
        la, lo = _m.radians(lat), _m.radians(lon)
        return np.array([_m.cos(la) * _m.cos(lo), _m.cos(la) * _m.sin(lo), _m.sin(la)])

    lat0, lon0 = _E.sublunar_point(date, utc)
    S = unit(*_E.subsolar_point(date, utc))
    V = unit(lat0, lon0)

    A = np.asarray(img.convert("L")).astype(np.float32)
    H, W = A.shape
    cx, cy, R = disc_geom(W, H)
    yy, xx = np.mgrid[0:H, 0:W]
    u = (xx - cx) / R
    v = -(yy - cy) / R
    rr = np.hypot(u, v)
    z = np.sqrt(np.clip(1 - rr ** 2, 0, 1))
    e_x = np.cross([0, 0, 1.0], V); e_x /= np.linalg.norm(e_x)
    e_y = np.cross(V, e_x)
    nx = u * e_x[0] + v * e_y[0] + z * V[0]
    ny = u * e_x[1] + v * e_y[1] + z * V[1]
    nz = u * e_x[2] + v * e_y[2] + z * V[2]
    cosi = nx * S[0] + ny * S[1] + nz * S[2]
    inside = rr < 0.97

    night = inside & (cosi < -0.35)
    term = inside & (np.abs(cosi) < 0.15)
    sub_m = inside & (cosi > 0.85)
    edge_m = inside & (cosi > 0.2) & (cosi < 0.45)
    over = inside & (A > 245)

    nightL = float(A[night].mean()) if night.any() else 0
    termL = float(np.median(A[term])) if term.any() else 0
    subL = float(np.median(A[sub_m])) if sub_m.any() else 0
    edgeL = float(np.median(A[edge_m])) if edge_m.any() else 0
    overp = float(over.sum()) / max(inside.sum(), 1) * 100

    # 只判两项能判的：
    #   ① 夜面必须暗（漏光就是错的）
    #   ② 不能有过曝（削顶会丢层次）
    # 日下点 vs 斜射区的亮度**不能用来判断光照**——
    #   日下点常在深海（反照率 0.06），斜射区常是云（0.6~0.8），
    #   反照率差异本身就会让"正对太阳"的地方更暗。这里只打印，不作为判据。
    ok = True
    notes = []
    if nightL > 12:
        ok = False
        notes.append("夜面偏亮 %.1f" % nightL)
    if overp > 2:
        ok = False
        notes.append("过曝 %.2f%%" % overp)

    print("   物理体检：夜面 %.1f | 晨昏线 %.0f | 日下点 %.0f | 斜射区 %.0f | 过曝 %.2f%%%s"
          % (nightL, termL, subL, edgeL, overp,
             "" if ok else "  ← 不通过：" + "；".join(notes)))
    print("     （日下点/斜射区的亮度差受反照率影响，仅供参考，不作判据）")
    return ok



def night_crush(img, date, utc, target=0.020):
    """夜面压到物理量级（≈0），与太空同黑 —— 真实照片里暗部就是看不见的。

    物理依据：夜面只靠星光+月照，约为昼面的 10⁻⁵。
    按昼面曝光时，整个暗部（含轮廓）完全消失。

    历史（都试错了）：
      · 压到 0.3 但天空是 11  → 成"黑洞"，轮廓更扎眼
      · 填成天空亮度（全平）   → 像平面图，没有球体感
      · 抬到天空 + 55% 结构    → 有质感，但比真实亮 2000 倍
      · 现在：0.3（物理量级）   → 真实

    做法：夜面按 cosi 在晨昏线处平滑过渡到 ≈0，不动亮面。
    """
    import math as _m
    import ephem_hp as _E

    if not date or utc is None:
        return img

    def unit(lat, lon):
        la, lo = _m.radians(lat), _m.radians(lon)
        return np.array([_m.cos(la) * _m.cos(lo), _m.cos(la) * _m.sin(lo), _m.sin(la)])

    lat0, lon0 = _E.sublunar_point(date, utc)
    S = unit(*_E.subsolar_point(date, utc))
    V = unit(lat0, lon0)

    A = np.asarray(img.convert("RGB")).astype(np.float32)
    H, W = A.shape[:2]
    _cx, _cy, R = disc_geom(W, H)
    cx, cy = int(_cx), int(_cy)
    yy, xx = np.mgrid[0:H, 0:W]
    u = (xx - cx) / R
    v = -(yy - cy) / R
    rr = np.hypot(u, v)
    inside = rr <= 0.995
    z = np.sqrt(np.clip(1 - rr ** 2, 0, None))
    e_x = np.cross([0, 0, 1.0], V); e_x /= np.linalg.norm(e_x)
    e_y = np.cross(V, e_x)
    nx = u * e_x[0] + v * e_y[0] + z * V[0]
    ny = u * e_x[1] + v * e_y[1] + z * V[1]
    nz = u * e_x[2] + v * e_y[2] + z * V[2]
    cosi = nx * S[0] + ny * S[1] + nz * S[2]

    L = A.mean(2)
    night = inside & (cosi < -0.30)
    if not night.any():
        return img

    cur = float(L[night].mean())

    # ── 夜面处理：保留球体质感，只把对比压到极低
    #    · 整块填平 → 看起来像平面图（用户 2026-11-07 指出）
    #    · 原样保留 → 能清楚看出大陆
    #    正确做法：把结构压缩到 ~1/4 强度，再整体抬到天空亮度，
    #    最后叠一层临边变暗（球缘融进太空，不出现硬圆边）。

    from PIL import ImageFilter as _IF

    # 当地天空亮度（圆盘挖掉后归一化卷积外推）
    disc_m = (rr <= 1.02).astype(np.float32)
    keep = 1.0 - disc_m
    num = (A.mean(2) * keep)
    def _blur(im):
        return im.filter(_IF.GaussianBlur(121))
    num_b = np.asarray(_blur(Image.fromarray(np.clip(num, 0, 255).astype(np.uint8)))).astype(np.float32)
    den_b = np.asarray(_blur(Image.fromarray((keep * 255).astype(np.uint8)))).astype(np.float32) / 255.0
    sky_map = num_b / np.maximum(den_b, 1e-3)

    # 夜面结构 = 原始亮度 - 夜面均值（去掉整体亮度，只留起伏）
    nm = float(L[night].mean())
    struct = L - nm

    # 临边因子：中心 1，球缘 0（让夜面在边缘融进太空）
    limb = np.clip(z, 0, 1) ** 0.45

    k_struct = 0.02          # 物理版：夜面 ≈ 0，结构也几乎不可见
    night_out = 0.3 + struct * k_struct * limb

    t = np.clip((-cosi - 0.02) / 0.13, 0, 1)
    w = (t * t * (3 - 2 * t)) * inside

    A = np.clip(A + ((night_out - L) * w)[..., None], 0, 255)

    # 补噪点，和太空的颗粒感一致
    sigma = float(L[(rr > 1.15) & (rr < 1.45)].std()) if ((rr > 1.15) & (rr < 1.45)).any() else 1.2
    rng = np.random.default_rng(11)
    noise = rng.normal(0, max(0.5, min(sigma, 2.0)), (H, W, 1)).astype(np.float32)
    A = np.clip(A + noise * (w > 0.25)[..., None], 0, 255)

    print("   夜面校正（物理）：%.1f → %.1f"
          % (cur, float(A.mean(2)[night].mean())))
    return Image.fromarray(A.astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", default=None)
    ap.add_argument("--date", default=None, help="日期（配合 --utc 做光照补偿）")
    ap.add_argument("--utc", type=float, default=None)
    ap.add_argument("--night-target", type=float, default=0.020,
                    help="夜面亮度目标（相对亮面均值）；0=不处理")
    ap.add_argument("--flat", action="store_true",
                    help="输入是匀光圆盘：只去水印，不做相位融合/夜面/光照补偿"
                    "（光照由 lighting.py 在最后统一施加）")
    ap.add_argument("--deglint", type=float, default=0.55,
                    help="光照补偿强度（抵消渲染端的耀斑压制，0=关）")
    a = ap.parse_args()

    src = a.image
    out = a.out or os.path.splitext(src)[0] + "_boost.png"
    tmp = os.path.join(HERE, "v2", "_boost_tmp")
    os.makedirs(tmp, exist_ok=True)

    w0, h0 = Image.open(src).size
    print("[提升] 原图 %dx%d" % (w0, h0))

    t0 = time.time()

    def _one_round():
        files = run_once(src, tmp, PROMPT_BOOST)
        g = files[-1] if files else None
        print("[提升] 生成完成 %s" % os.path.basename(g or "?"))
        o = download_original(tmp)
        if o:
            g = o
            print("[提升] 采用「下载原图」：", os.path.basename(o))
        return g

    # ★ 尺寸校验：豆包偶尔返回缩略图（384x256），直接用会放大成一片马赛克/黑洞。
    #   实测 2010-07-20 就是这样把亮面 38% 变成纯黑。
    got = None
    for attempt in range(1, 4):
        got = _one_round()
        if not got:
            continue
        sz = Image.open(got).size
        ok = min(sz) >= max(1024, min(w0, h0) * 0.75)
        print("[提升] 第 %d 次返回 %dx%d  %s" % (attempt, sz[0], sz[1], "可用" if ok else "太小，重试"))
        if ok:
            break
    if not got:
        print("[FAILED] 豆包没有返回任何图")
        return 3
    if min(Image.open(got).size) < max(1024, min(w0, h0) * 0.75):
        print("[FAILED] 豆包连续 3 次返回缩略图，中止（不拿它冒充成品）")
        return 3

    print("[提升] 总耗时 %.1fs" % (time.time() - t0))

    # 删对话（默认删；设 DSH_KEEP_CHAT=1 可保留，便于用户回看）
    keep = (os.environ.get("DSH_KEEP_CHAT") == "1"
            or os.environ.get("DSH_KEEP_CONV") == "1")
    if keep:
        print("   [保留对话] DSH_KEEP_CHAT=1 → 不删除：%s" % LAST.get("title", ""))
    elif LAST.get("title"):
        try:
            d = subprocess.run([NODE, os.path.join(HERE, "delete_conv.mjs"),
                                LAST["title"].replace(" - 豆包", "")],
                               capture_output=True, text=True, timeout=180)
            print("   [删对话] %s" % ("已删除" if d.returncode == 0 else "失败"))
        except Exception as e:
            print("   [删对话] 失败：", e)

    img = Image.open(got).convert("RGB")
    print("[提升] 豆包返回 %dx%d" % img.size)
    # 尺寸一致就直接用：豆包有时会在顶部加黑边，但尺寸没变。
    # 裁剪再缩放会引入错位（实测地球边缘出现黑月牙）和重采样损失。
    if img.size == (w0, h0):
        print("[提升] 尺寸与原图一致，直接使用（不裁剪不缩放）")
    else:
        img = crop_to_content(img)
        print("[提升] 尺寸不同，裁掉黑边后 %dx%d" % img.size)
        img = align_to_source(img, Image.open(src).convert("RGB"))
    img = remove_watermark(img, Image.open(src))

    if getattr(a, "flat", False):
        # ★ 匀光模式：光照还没施加，这里只做去水印与尺寸对齐
        img = restore_scene(img, Image.open(src))
        img = match_disc(img, Image.open(src))     # ★ 盘内亮度也要还原
        print("   [匀光模式] 跳过相位融合/夜面/光照补偿（打光由 lighting.py 负责）")
    else:
        img = blend_by_phase(img, Image.open(src))
        img = deglint(img, a.date, a.utc, a.deglint)
        img = night_crush(img, a.date, a.utc, a.night_target)
        img = finish_tone(img, a.date, a.utc)
        img = clean_rim(img)
        img = restore_scene(img, Image.open(src))
        physics_report(img, a.date, a.utc)
    img.save(out)
    print("[提升] 已保存 %s（%dx%d）" % (out, *img.size))


if __name__ == "__main__":
    sys.exit(main())
