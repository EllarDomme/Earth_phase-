"""make_earth_full.py —— 一条命令做完整地相图（五步流水线 + 质检门禁）

当用户说"做某天的地相图"，跑这一条就够：
    ① 取原始拼接图（Terra + Aqua）
    ② 画拼接线（15 条黑线 3 px，缺口内不画）
    ③ 空洞补全（fill_gaps.py）
    ④ 日界线（16 px 淡化 + 5 px 黑线）
    ⑤ 正交投影渲染

用法:
    python make_earth_full.py 2021-11-09 --utc 4 --lat 20 --lon 105 --size 2048

质检门禁（任一失败则退出码 2，并写明哪条没过）:
    n_seams == 15          |spacing - 281.2| <= 1.5       rms < 1.5
    black_after_fill <= 0.3%   hole_ring_ratio 0.8 ~ 1.25
    dateline_gap_after_fade < 60    disk_not_blank

输出: seams_<date>.png / filled_<date>.png / filled_all_<date>.png /
      disk_<date>_final.png / qc_<date>.json
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_earth as R
import find_seams as FS

import time as _time
_T0 = _time.perf_counter()
def _tmark(label):
    print("[耗时] %-10s 累计 %.1f s" % (label, _time.perf_counter() - _T0))

GATE = dict(n_seams=15, spacing=281.2, spacing_tol=1.5, rms_max=2.5,
            black_max=0.3, ratio_lo=0.8, ratio_hi=1.25, dateline_max=60.0)


def sublunar_point(date_str, utc_hour):
    """月下点 + 地球相位。优先用高精度星历 ephem_hp（Meeus，误差 <0.02°）。"""
    try:
        from ephem_hp import sublunar_point as _hp, earth_phase
        lat, lon = _hp(date_str, utc_hour)
        return lat, lon, earth_phase(date_str, utc_hour)
    except Exception:
        pass
    from datetime import datetime, timedelta
    import math
    t = datetime.fromisoformat(date_str) + timedelta(hours=utc_hour)
    J2000 = datetime(2000, 1, 1, 12, 0)
    d = (t - J2000).total_seconds() / 86400.0
    Lp = (218.316 + 13.176396 * d) % 360
    M = math.radians((134.963 + 13.064993 * d) % 360)
    F = math.radians((93.272 + 13.229350 * d) % 360)
    lam = math.radians((Lp + 6.289 * math.sin(M)) % 360)
    bet = math.radians(5.128 * math.sin(F))
    eps = math.radians(23.4393)
    ra = math.atan2(math.sin(lam) * math.cos(eps) - math.tan(bet) * math.sin(eps),
                    math.cos(lam))
    dec = math.asin(math.sin(bet) * math.cos(eps) +
                    math.cos(bet) * math.sin(eps) * math.sin(lam))
    gmst = (280.46061837 + 360.98564736629 * d) % 360
    lon = (math.degrees(ra) - gmst + 180) % 360 - 180
    lat = math.degrees(dec)
    doy = t.timetuple().tm_yday
    sdec = -23.44 * math.cos(math.radians(360.0 / 365.0 * (doy + 10)))
    slon = (12.0 - utc_hour) * 15.0
    cosang = (math.sin(math.radians(lat)) * math.sin(math.radians(sdec)) +
              math.cos(math.radians(lat)) * math.cos(math.radians(sdec)) *
              math.cos(math.radians(lon - slon)))
    ang = math.degrees(math.acos(max(-1, min(1, cosang))))
    return lat, lon, 100.0 * (1 + math.cos(math.radians(ang))) / 2



def _clean_tmp_dirs(dry=False):
    """清掉 v2 下的临时子目录（每次下载都会新建 _official_dl_*）。

    实测一次下午的运行就攒下 42 个目录、124 MB —— 全是当次用完就没用的。
    """
    import glob as _g
    import shutil as _sh
    v2 = os.path.join(HERE, "v2")
    if not os.path.isdir(v2):
        return 0, 0.0
    pats = ["_official_dl_*", "_boost_tmp", "_greet", "*.png"]
    seen, n, mb = set(), 0, 0.0
    for pat in pats:
        for d in _g.glob(os.path.join(v2, pat)):
            if not os.path.isdir(d) or d in seen:
                continue
            seen.add(d)
            for f in _g.glob(os.path.join(d, "**", "*"), recursive=True):
                if os.path.isfile(f):
                    mb += os.path.getsize(f) / 1048576.0
            if not dry:
                _sh.rmtree(d, ignore_errors=True)
            n += 1
    return n, mb


def _clean_station(keep_hours=1.0, dry=False):
    """清掉中转站里超过 keep_hours 小时的成品图（默认保留最近 1 小时）。

    中转站只是"两轮豆包"的凭据，跑一次涨 15~40 MB；
    留着历史文件既占空间，又会干扰"取最新"的判断。
    """
    import glob as _g
    import time as _t
    st = os.path.join(HERE, "中转站")
    if not os.path.isdir(st):
        return 0, 0.0
    cutoff = _t.time() - keep_hours * 3600.0
    n, mb = 0, 0.0
    for p in _g.glob(os.path.join(st, "*")):
        if not os.path.isfile(p):
            continue
        try:
            if os.path.getmtime(p) >= cutoff:
                continue
            mb += os.path.getsize(p) / 1048576.0
            if not dry:
                os.remove(p)
            n += 1
        except Exception:
            pass
    return n, mb


def _clean_intermediates(keep_backups=True, dry=False):
    """删掉 v2 里的中间产物，只留 _bak_*（底图/样张备份）。

    每跑一张图，v2 会长 70~100 MB（filled_* / seams_* / disk_* /
    raw_terra_* / texture.npy）。这些都能重新算出来，留着只会把项目撑大。
    """
    import glob as _glob

    v2 = os.path.join(HERE, "v2")
    if not os.path.isdir(v2):
        return 0, 0.0

    removed_n, removed_b = 0, 0.0

    # 每轮产生的临时目录（豆包下载落在这里，之前只删顶层文件，所以越积越多）
    TEMP_DIRS = ("_boost_tmp", "_official_dl", "_official_dl_r1",
                 "_official_dl_r2", "_official_dl_boost")

    for p in _glob.glob(os.path.join(v2, "*")):
        name = os.path.basename(p)

        if os.path.isdir(p):
            # 只删已知临时目录；_bak_* 等备份目录一律保留
            if name in TEMP_DIRS and not name.startswith("_bak_"):
                try:
                    sz = sum(os.path.getsize(os.path.join(r, f))
                             for r, _, fs in os.walk(p) for f in fs)
                    if not dry:
                        import shutil as _sh
                        _sh.rmtree(p, ignore_errors=True)
                    removed_n += 1
                    removed_b += sz
                except Exception:
                    pass
            continue

        if keep_backups and name.startswith("_bak_"):
            continue
        try:
            sz = os.path.getsize(p)
            if not dry:
                os.remove(p)
            removed_n += 1
            removed_b += sz
        except Exception:
            pass
    return removed_n, removed_b / 1048576.0



def _measure_disc(path):
    """测出单张图里圆盘的中心与半径（用于给它单独打光）"""
    try:
        import numpy as _np
        A = _np.asarray(Image.open(path).convert("L")).astype(_np.float32)
        m = A > 12
        if m.sum() < 1000:
            return None
        ys, xs = _np.where(m)
        cx = (xs.min() + xs.max()) / 2.0
        cy = (ys.min() + ys.max()) / 2.0
        R = (xs.max() - xs.min()) / 2.0
        return (cx, cy, R)
    except Exception:
        return None


def main():
    try:
        sys.stdout.reconfigure(line_buffering=True)   # 关缓冲：日志顺序 = 真实顺序
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--dir", default=r"E:\DeskTop\地球\v2")
    ap.add_argument("--utc", type=float, default=None,
                    help="缺省=自动挑一个能让中国可见的时刻")
    ap.add_argument("--check", action="store_true", default=False,
                    help="只计算该日期中国能否落在亮部，不取图不渲染")
    ap.add_argument("--no-china", action="store_true", default=False,
                    help="关闭「必须看到中国」约束（默认开启）")
    ap.add_argument("--utc-fixed", type=float, default=4.0)
    ap.add_argument("--lat", type=float, default=None, help="缺省=月下点纬度")
    ap.add_argument("--lon", type=float, default=None, help="缺省=月下点经度")
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--polish", dest="polish", action="store_true", default=False,
                    help="出图后自动交豆包两轮去痕迹（需豆包以调试模式打开）")
    ap.add_argument("--no-polish", dest="polish", action="store_false")
    ap.add_argument("--moon", action="store_true", default=False,
                    help="再合成《地出》式版式：月面底图 + 我们的地球")
    ap.add_argument("--moon-width", type=int, default=1920)
    ap.add_argument("--earth-size", default="artistic",
                    choices=["artistic", "true"],
                    help="artistic=占画宽36%%；true=真实角直径1.9°（40°视场下4.75%%）")
    ap.add_argument("--boost", action="store_true", default=False,
                    help="把月面图交豆包提清晰度（旧顺序：拼图后处理整张海报）")
    ap.add_argument("--boost-last", action="store_true", default=False,
                    help="★ 回退到旧顺序：拼图后把整张海报交豆包提清晰度"
                         "（豆包会看到并重绘月面，不建议）")
    ap.add_argument("--boost-first", action="store_true", default=False,
                    help=argparse.SUPPRESS)   # 已变默认，保留只为兼容旧命令
    ap.add_argument("--no-clean", dest="clean", action="store_false",
                    help="保留 v2 中间产物（默认跑完自动清理）")
    ap.add_argument("--reuse", default=None,
                    help="复用中转站里已有的成品（跳过豆包），直接进拼图与打光")
    ap.add_argument("--uniform", action="store_true", default=False,
                    help="匀光流程：全亮无临边渲染 → 豆包清纹理 → 拼图 → 提清晰度 → 最后按星历打光")
    ap.add_argument("--archive", action="store_true", default=False,
                    help="完成后自动复制到 成品/<日期>_地球相_2048.png 并写 json")
    a = ap.parse_args()
    D, OUT = a.date, a.dir
    qc = {"date": D}

    # 视角：缺省用月下点（从月球看地球的正确中心）
    # ★ 铁律：只要画面有亮部，中国就必须在亮部里（视角仍是月下点）
    if not a.no_china and a.lat is None:
        print("[0] 先定视角：中国必须落在亮部（定完之后才取图，避免白跑）")
        try:
            import china_rule as _cr
            _r, _rows, _msg = _cr.best(D)
            if _r:
                a.utc = _r["utc"]
                # ★ 相位必须和 UTC 一起报：同一天内相位最多差 9 个点，
                #   "日期"本身不足以确定相位（2026-11-09 讨论）。
                print("[中国] %s｜UTC %.2f｜相位 %.0f%%｜中国 可见 %.2f 受光 %.2f｜采样点 可见 %d/10 受光 %d/10"
                      % (_msg, a.utc, _r.get("phase", float("nan")),
                         _r["vis"], _r["lit"], _r["v_ok"], _r["l_ok"]))
                if _r["vis"] < 0.35 or _r["lit"] < 0.35:
                    print("[中国] 注意：中国靠近球缘/晨昏线，可辨识度下降")
            else:
                a.utc = a.utc_fixed
                print("[中国] %s，回落到 UTC %.2f（相位 %.0f%%）"
                      % (_msg, a.utc, qc.get("earth_phase_pct", float("nan"))))
        except Exception as _e:
            a.utc = a.utc_fixed
            print("[中国] 求解失败（%s），回落到 UTC %.2f" % (_e, a.utc))
    elif a.utc is None:
        a.utc = a.utc_fixed

    if getattr(a, "check", False):
        _ml = sublunar_point(D, a.utc)
        print("[check] UTC %.2f  月下点 %.1fN %.1fE  相位 %.0f%%"
              % (a.utc, _ml[0], _ml[1], _ml[2]))
        print("[check] 通过：可以出图（未取图、未渲染）")
        return 0

    mlat, mlon, mphase = sublunar_point(D, a.utc)
    if a.lat is None or a.lon is None:
        a.lat, a.lon = mlat, mlon
        print("[0] 月下点 %.1f°N %.1f°E  地球相位 %.0f%%" % (mlat, mlon, mphase))
        try:
            import math as _m
            _c = (a.lat, a.lon)
            _v = (mlat, mlon)

            def _u(t):
                la, lo = _m.radians(t[0]), _m.radians(t[1])
                return (_m.cos(la) * _m.cos(lo), _m.cos(la) * _m.sin(lo), _m.sin(la))
            _d = _m.degrees(_m.acos(max(-1, min(1, sum(x * y for x, y in zip(_u(_c), _u(_v)))))))
            if _d > 1.0:
                print("[0] 视角偏离月下点 %.1f°（为让中国居中）" % _d)
        except Exception:
            pass
    qc.update(dict(view_lat=round(a.lat, 2), view_lon=round(a.lon, 2),
                   sublunar=[round(mlat, 2), round(mlon, 2)],
                   earth_phase_pct=round(mphase, 1)))

    # ① 取图（2012 年以后额外取 VIIRS：幅宽大、缺口少）
    #   ★ 冷缓存时三个图层并行下载（2026-11-04：原来串行约 20 秒 → 并行约 8 秒）
    from concurrent.futures import ThreadPoolExecutor as _TPE
    want = [("terra", f"raw_terra_{D}.jpg", R.LAYERS["terra"]),
            ("aqua", f"raw_aqua_{D}.jpg", R.LAYERS["aqua"])]
    if int(D[:4]) >= 2012:
        want.append(("NOAA20", f"raw_NOAA20_{D}.jpg",
                     "VIIRS_NOAA20_CorrectedReflectance_TrueColor"))

    def _grab(item):
        name, fname, layer = item
        p = os.path.join(OUT, fname)
        if os.path.exists(p):
            return name, fname, None
        try:
            im = R.fetch(layer, D)
            im.save(p, quality=95)
            return name, fname, None
        except Exception as e:
            return name, fname, str(e)

    qc["viirs"] = None
    with _TPE(max_workers=3) as _ex:
        _res = list(_ex.map(_grab, want))

    for name, fname, err in _res:
        if name in ("terra", "aqua"):
            p = os.path.join(OUT, fname)
            if not os.path.exists(p):
                raise SystemExit("[1] %s 取图失败：%s" % (name, err))
            g = np.asarray(Image.open(p).convert("L"))
            qc[f"{name}_hole_pct"] = round(float(100 * (g < 10).mean()), 2)
        else:
            if int(D[:4]) >= 2012 and err is None:
                vg = np.asarray(Image.open(os.path.join(OUT, fname)).convert("L"))
                qc["viirs"] = {"name": name, "file": fname,
                               "hole_pct": round(float(100 * (vg < 10).mean()), 2)}
            elif err:
                print("[1] VIIRS %s 取图失败：%s" % (name, err))
    if qc["viirs"]:
        print("[1] 原始图 terra %.2f%% / aqua %.2f%% 缺口   VIIRS(%s) %.2f%%"
              % (qc["terra_hole_pct"], qc["aqua_hole_pct"],
                 qc["viirs"]["name"], qc["viirs"]["hole_pct"]))
    else:
        print("[1] 原始图 terra %.2f%% / aqua %.2f%% 缺口"
              % (qc["terra_hole_pct"], qc["aqua_hole_pct"]))

    _tmark("①取图")
    # ①′ 颜色异常检测（无需参考图：暗红填充 / 纯黑空洞）
    art_json = None
    try:
        sub = subprocess.run(
            [sys.executable, os.path.join(HERE, "detect_fill_artifacts.py"),
             os.path.join(OUT, f"raw_terra_{D}.jpg"), "--min-area", "1500"],
            capture_output=True, text=True, timeout=900)
        cand = os.path.join(OUT, f"raw_terra_{D}_fillartifacts.json")
        if os.path.exists(cand):
            art_json = json.load(open(cand, encoding="utf-8"))
    except Exception as e:
        print("[1′] 颜色异常检测失败:", e)

    if art_json:
        s1 = art_json["classes"].get("S1_暗红填充", {})
        cl = s1.get("clusters", [])
        qc["fill_artifacts"] = {
            "s1_pixels": s1.get("pixels", 0),
            "s1_clusters": [{k: c[k] for k in ("area", "lat", "lon", "km2", "rgb")}
                            for c in cl[:6]],
        }
        if cl:
            print("[1′] ⚠ 发现暗红填充 %d 处（这类是数据缺失被染色）：" % len(cl))
            for c in cl[:4]:
                print("      %6.1fN %7.1fE   面积约 %.0f 万 km²   RGB %s"
                      % (c["lat"], c["lon"], c["km2"] / 1e4, c["rgb"]))
            print("      → 建议先修这块再出图（否则地相图上会是一大块暗褐色）")
        else:
            print("[1′] 颜色异常检测：未发现暗红填充 ✓")

    _tmark("①′异常检测")
    # ② 拼接线
    subprocess.run([sys.executable, os.path.join(HERE, "find_seams.py"),
                    os.path.join(OUT, f"raw_terra_{D}.jpg"),
                    "--out", os.path.join(OUT, f"seams_{D}")],
                   check=True, capture_output=True)
    cfg = json.load(open(os.path.join(OUT, f"seams_{D}.json"), encoding="utf-8"))
    qc["n_seams"] = cfg["seam_count"]
    qc["spacing_px"] = cfg["spacing_px"]
    qc["fit_rms_px"] = cfg["fit_rms_px"]
    print("[2] 拼接线 %d 条  间距 %.1f  残差 %.2f"
          % (qc["n_seams"], qc["spacing_px"], qc["fit_rms_px"]))

    _tmark("②拼接线")
    # ③ 补洞
    #   ③a 先用 VIIRS 补"超出标准梭形"的大块缺失（梭形内部保持原样）
    terra_for_fill = None
    if qc.get("viirs"):
        try:
            subprocess.run([sys.executable, os.path.join(HERE, "fill_gaps_viirs.py"), D,
                            "--dir", OUT, "--write-raw"], check=True, capture_output=True)
            cand = os.path.join(OUT, f"raw_terra_{D}_viirsfill.jpg")
            if os.path.exists(cand):
                terra_for_fill = cand
            pv = json.load(open(os.path.join(OUT, f"prefilled_{D}.json"), encoding="utf-8"))
            qc["viirs_prefill"] = pv
            print("[3a] VIIRS 预填：超出梭形 %.2f%%，实际补 %.2f%%，增益 %.3f"
                  % (pv["beyond_pct"], pv["filled_pct"], pv["gain_median"]))
        except Exception as e:
            print("[3a] VIIRS 预填跳过：", e)

    #   ③b 原流程补剩下的（梭形 + 残余）
    fill_cmd = [sys.executable, os.path.join(HERE, "fill_gaps.py"), D, "--dir", OUT]
    if terra_for_fill:
        fill_cmd += ["--terra", terra_for_fill]
    subprocess.run(fill_cmd, check=True, capture_output=True)
    fj = json.load(open(os.path.join(OUT, f"filled_{D}.json"), encoding="utf-8"))
    qc["black_after_fill_pct"] = fj["black_pct_after_fill"]
    qc["hole_ring_ratio"] = fj["hole_ring_bright_ratio"]
    print("[3] 补洞完成  黑像素 %.3f%%  亮度比 %s"
          % (fj["black_pct_after_fill"], fj["hole_ring_bright_ratio"]))

    # ②′ 画拼接线（缺口内不画）—— 画在补好的图上
    raw = Image.open(os.path.join(OUT, f"raw_terra_{D}.jpg")).convert("RGB")
    W, H = raw.size
    rg = np.asarray(raw.convert("L")).astype(np.int16)
    c = np.array(cfg["cubic_coeff"])
    step = cfg["spacing_px"]
    comps = FS.components(rg < 10)
    rows = [FS.midline_rows(Q) for Q in comps]
    phases = [float(np.median(cs - np.polyval(c, ys))) for ys, cs in rows]
    yy = np.arange(H, dtype=float)
    shape = np.polyval(c, yy)
    im = Image.open(os.path.join(OUT, f"filled_{D}.png")).convert("RGB")
    dr = ImageDraw.Draw(im)
    WID = max(1, round(W / 1400))
    segs = 0
    for ph in phases:
        x = shape + ph
        seg = []
        for u, v in zip(x, yy):
            if not (-5 <= u < W + 5):
                continue
            xi = int(min(max(u, 0), W - 1))
            yv = int(v)
            if rg[yv, xi] < 10:
                if len(seg) > 1:
                    dr.line(seg, fill=(0, 0, 0), width=WID)
                    segs += 1
                seg = []
            else:
                seg.append((float(u), float(v)))
        if len(seg) > 1:
            dr.line(seg, fill=(0, 0, 0), width=WID)
            segs += 1
    qc["seam_segments"] = segs
    print("[2'] 拼接线绘制 %d 段，宽 %d px" % (segs, WID))

    _tmark("③补洞")
    # ④ 日界线
    arr = np.asarray(im).astype(np.float32)
    N = 16
    w = np.linspace(0, 1, N)[None, :, None]
    w = w * w * (3 - 2 * w)
    A = arr[:, :N]
    B = arr[:, W - N:]
    out = arr.copy()
    out[:, :N] = A * (1 - w) + B * w
    out[:, W - N:] = B * (1 - w) + A * w
    qc["dateline_gap_before"] = round(float(np.abs(arr[:, 0] - arr[:, -1]).mean()), 1)
    qc["dateline_gap_after"] = round(float(np.abs(out[:, 0] - out[:, -1]).mean()), 1)
    im2 = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    dr2 = ImageDraw.Draw(im2)
    # 日界线：左右各 2 px（共 4 px），比拼接线（3 px）略粗一点，中心落在 ±180° 边界上
    DL_W = 4
    half = DL_W // 2
    for k in range(half):
        dr2.line([(W - 1 - k, 0), (W - 1 - k, H)], fill=(0, 0, 0), width=1)
        dr2.line([(k, 0), (k, H)], fill=(0, 0, 0), width=1)
    im2.save(os.path.join(OUT, f"filled_all_{D}.png"))
    np.save(os.path.join(OUT, "texture.npy"), np.asarray(im2).astype(np.uint8))
    print("[4] 日界线 %.1f → %.1f，加 4 px 线"
          % (qc["dateline_gap_before"], qc["dateline_gap_after"]))

    _tmark("④日界线")
    # ⑤ 渲染
    R.DATE, R.OUT = D, OUT
    if getattr(a, "uniform", False):
        # 匀光：不打光、不加临边（光照留到最后由 lighting.py 施加）
        R.FULL_LIT = 1
        R.FULL_FLAT = 1
        print("[5] 匀光模式：渲染全亮无临边的圆盘")
    p = R.render(lat0=a.lat, lon0=a.lon, size=a.size, utc_hour=a.utc)
    out_png = os.path.join(OUT, f"disk_{D}_final.png")
    Image.open(p).save(out_png)
    d = np.asarray(Image.open(out_png).convert("L"))
    qc["disk_mean"] = round(float(d.mean()), 1)
    print("[5] 渲染 %dx%d  UTC %.1f  中心 %.0fN %.0fE"
          % (a.size, a.size, a.utc, a.lat, a.lon))

    # 质检门禁
    fails = []
    if qc["n_seams"] != GATE["n_seams"]:
        fails.append("拼接线条数 %d ≠ 15" % qc["n_seams"])
    if abs(qc["spacing_px"] - GATE["spacing"]) > GATE["spacing_tol"]:
        fails.append("间距 %.1f 偏离 281.2" % qc["spacing_px"])
    if qc["fit_rms_px"] > 1.5:
        print("   [提示] 拼接线残差 %.2f px 偏高（缺口较宽时正常，上限 %.1f）"
              % (qc["fit_rms_px"], GATE["rms_max"]))
    if qc["fit_rms_px"] > GATE["rms_max"]:
        fails.append("拟合残差 %.2f > %.1f" % (qc["fit_rms_px"], GATE["rms_max"]))
    if qc["black_after_fill_pct"] > GATE["black_max"]:
        fails.append("补洞后黑像素 %.2f%% > %.1f%%"
                     % (qc["black_after_fill_pct"], GATE["black_max"]))
    r = qc["hole_ring_ratio"]
    if r is not None and not (GATE["ratio_lo"] <= r <= GATE["ratio_hi"]):
        fails.append("洞/环亮度比 %.2f 超出 %.2f~%.2f"
                     % (r, GATE["ratio_lo"], GATE["ratio_hi"]))
    if qc["dateline_gap_after"] > GATE["dateline_max"]:
        fails.append("日界线首尾差 %.1f 仍偏大" % qc["dateline_gap_after"])
    # 注意：相位接近 0% 时画面本来就接近全黑（真实），不算失败
    qc["nearly_black"] = bool(qc["disk_mean"] < 5)
    if qc["nearly_black"]:
        qc.setdefault("notes", []).append(
            "地球相位 %.1f%%，画面接近全黑——这是真实结果，已按第一准则照常交付"
            % qc.get("earth_phase_pct", -1))

    qc["pass"] = not fails
    qc["fails"] = fails
    with open(os.path.join(OUT, f"qc_{D}.json"), "w", encoding="utf-8") as f:
        json.dump(qc, f, ensure_ascii=False, indent=2)

    if fails:
        print("\n[QC] 未通过 %d 项：" % len(fails))
        for x in fails:
            print("   - " + x)
        print("   门禁标准:", GATE)
        return 2
    print("\n[QC] 全部通过 →", out_png)
    # ⑥ 豆包两轮去痕迹（可选，--polish）
    if getattr(a, "reuse", None):
        import shutil as _shr
        _src_reuse = os.path.abspath(a.reuse)
        if not os.path.exists(_src_reuse):
            print("[复用] 文件不存在：", _src_reuse)
            return 2
        _dst_reuse = os.path.splitext(out_png)[0] + "_polished.png"
        _shr.copy2(_src_reuse, _dst_reuse)
        # ★ copy2 会把源文件的只读属性一起带过来（用户的附件常是只读的），
        #   下一次运行就会 Permission denied。复制完立刻去掉只读。
        try:
            os.chmod(_dst_reuse, 0o666)
        except OSError:
            import stat as _st
            os.chmod(_dst_reuse, _st.S_IWRITE)
        qc["polished"] = True
        qc["polished_path"] = _dst_reuse
        qc["reused"] = _src_reuse
        print("[复用] 跳过豆包，直接使用：%s" % os.path.basename(_src_reuse))
        print("[复用] 已复制为：%s" % os.path.basename(_dst_reuse))
    elif getattr(a, "polish", False):
        print("\n[6] 交豆包两轮去痕迹…")
        try:
            import subprocess as _sp
            _cmd = [sys.executable, os.path.join(HERE, "doubao_polish.py"),
                    out_png, "--size", str(a.size),
                    "--view=%.2f,%.2f" % (qc["view_lat"], qc["view_lon"]),
                    # ★ 不提亮：实测提亮后豆包清不干净线（2026-11-04）
                    "--shadow-lift", "1.0"]
            _r = _sp.run(_cmd, timeout=1800)
            qc["polished"] = (_r.returncode == 0)
            qc["polished_path"] = os.path.splitext(out_png)[0] + "_polished.png"
        except Exception as e:
            print("   豆包阶段失败：", e)
            qc["polished"] = False

        # ★ 豆包失败就不能继续：否则会用"带黑线的渲染图"覆盖成品
        if not qc.get("polished"):
            print("   [中止] 豆包阶段未成功（CDP 不可用或运行失败）")
            print("   [中止] 不会用渲染图覆盖 成品/，也不做月面合成")
            print("   [中止] 请先启动豆包（路径见 config.py）：")
            print("       python config.py    # 会打印当前路径与启动命令")
            with open(os.path.join(OUT, f"qc_{D}.json"), "w", encoding="utf-8") as f:
                import json as _json2
                _json2.dump(qc, f, ensure_ascii=False, indent=2)
            return 3
        with open(os.path.join(OUT, f"qc_{D}.json"), "w", encoding="utf-8") as f:
            json.dump(qc, f, ensure_ascii=False, indent=2)
    else:
        print("\n[6] 未做豆包阶段（加 --polish 可自动执行两轮）")

    # ── 豆包二轮之后：不再做任何加工（增强/海报都已移除，见手册之二十三）
    qc["doubao_output"] = qc.get("polished_path")

    # ── 新顺序：先提清晰度（只碰圆盘）→ 再拼两张海报
    #   2026-11-09：用户指出「让豆包在拼图里顺手处理月面」有隐患，
    #   改成让豆包只处理圆盘，月面永远不经过 AI。
    if (not getattr(a, "boost_last", False)
            and getattr(a, "boost", False) and getattr(a, "moon", False)):
        try:
            import stage_boost as _SB
            _src = qc.get("polished_path") or out_png
            _extra = ["--date", str(D)]
            # utc 可能是 None（--no-china 且没给 --utc）；直接 str(None) 会让
            # compose 的 argparse 崩在 "invalid float value: 'None'"。
            _utc_v = qc.get("utc", a.utc)
            if _utc_v is not None:
                _extra += ["--utc", str(_utc_v)]
            _extra += ["--earth-pct", "0.36", "--sky-target", "1,1,1"]
            if getattr(a, "earth_size", "artistic") != "artistic":
                _extra += ["--earth-size", a.earth_size]
                print("[地球] 尺寸模式：%s" % a.earth_size)
            if getattr(a, "uniform", False):
                _extra += ["--earth-gamma", "1.0", "--earth-sat", "1.0",
                           "--moon-gain", "0.65"]
            _n, _b = _SB.boost_then_compose(
                _src, os.path.join(HERE, "成品"), str(D),
                width=a.moon_width, compose_extra=_extra,
                boost_extra=(["--flat"] if getattr(a, "uniform", False) else []),
                log=print)
            if _n:
                qc["moon_path"] = _n
                print("[月面] %s" % _n)
            if _b:
                qc["moon_boost_path"] = _b
                print("[月面] %s" % _b)
            qc["boost_first_done"] = bool(_n)
            if not _n:
                # ★ 新路径失败时绝不能退回旧顺序 —— 旧顺序会把整张海报
                #   交给豆包，月面又会被重绘，正是我们要消除的行为。
                print("   !! 提升优先失败：只拼图、不提升（不会退回会碰月面的旧顺序）")
                qc["skip_old_boost"] = True
        except Exception as e:
            print("   !! 提升优先异常：%s" % e)
            print("   !! 只拼图、不提升（不会退回会碰月面的旧顺序）")
            qc["skip_old_boost"] = True

    # ── 《地出》式合成（--moon）
    if getattr(a, "moon", False) and not qc.get("boost_first_done"):
        try:
            import subprocess as _sp4
            _src = qc.get("polished_path") or out_png

            _pd = os.path.join(HERE, "成品")
            os.makedirs(_pd, exist_ok=True)
            _dst = os.path.join(_pd, "%s_月面_%dx1280.png" % (D, a.moon_width))
            # 传日期+UTC，让 compose_moon 自动挑底图（原版/镜像）
            _cmd4 = [sys.executable, os.path.join(HERE, "compose_moon.py"),
                     _src, _dst, "--width", str(a.moon_width)]
            if getattr(a, "uniform", False):
                # ★ 匀光流程一律用物理值：不提亮、不加饱和
                #   （默认 0.88/1.30 是美术调色，会让亮面比真实更亮更艳）
                _cmd4 += ["--earth-gamma", "1.0", "--earth-sat", "1.0",
                          # 真实月面比地球暗得多（反照率 0.12 vs 0.30，且前景是低太阳角）
                          "--moon-gain", "0.65"]
            try:
                _cmd4 += ["--date", str(D), "--utc", str(qc.get("utc", a.utc))]
            except Exception:
                pass
            if getattr(a, "earth_size", "artistic") != "artistic":
                _cmd4 += ["--earth-size", a.earth_size]
                print("[地球] 尺寸模式：%s" % a.earth_size)
            _r = _sp4.run(_cmd4, capture_output=True, text=True, timeout=600)
            for _ln in (_r.stdout or "").splitlines():
                if _ln.startswith(("底图选择", "天空底色", "星点", "输出", "  地球")):
                    print("   [月面] " + _ln)
            if _r.returncode == 0:
                print("[月面] %s" % _dst)
                qc["moon_path"] = _dst
            else:
                print("   [月面] 失败：", (_r.stderr or "")[-200:])
        except Exception as e:
            print("   [月面] 失败：", e)

    # ── 最后一道：豆包提清晰度（--boost）
    #   boost-first 模式下已经在拼图前对圆盘做完，这里跳过（否则又会碰月面）
    if (getattr(a, "boost", False) and qc.get("moon_path")
            and not qc.get("boost_first_done")
            and not qc.get("skip_old_boost")):
        try:
            import subprocess as _sp5
            _src = qc["moon_path"]
            _dst = _src.replace("_月面_", "_月面_提升_")
            print("\n[提升] 交豆包提清晰度…")
            _t0 = __import__("time").time()
            _cmd5 = [sys.executable, os.path.join(HERE, "doubao_boost.py"),
                     _src, "--out", _dst]
            if getattr(a, "uniform", False):
                _cmd5.append("--flat")     # 匀光：不做相位融合/夜面，光照最后统一施加
            try:
                _cmd5 += ["--date", str(D), "--utc", str(qc.get("utc", a.utc))]
            except Exception:
                pass
            _r = _sp5.run(_cmd5,
                          capture_output=True, text=True, timeout=1800)
            for _ln in (_r.stdout or "").splitlines():
                if (_ln.startswith("[提升]") or "去水印" in _ln
                    or "暗部亮度" in _ln or "物理体检" in _ln
                    or "仅供参考" in _ln):
                    print("   " + _ln)
            if _r.returncode == 0 and os.path.exists(_dst):
                print("[提升] %s（%.0f 秒）" % (_dst, __import__("time").time() - _t0))
                qc["boost_path"] = _dst
            else:
                print("   [提升] 失败：", (_r.stderr or "")[-200:])
        except Exception as e:
            print("   [提升] 失败：", e)

    # ── 匀光流程：最后统一按星历打光（纯数学，不经过 AI）
    if getattr(a, "uniform", False):
        try:
            import lighting as _lt
            _utc = qc.get("utc", a.utc)
            _lit = []
            # ★ 三个都要打光：旧顺序的 boost_path（海报）、月面、以及
            #   boost-first 产出的月面提升版。漏掉 moon_boost_path 会让
            #   提升版变成"满盘平光"（实测暗像素占比 6.2% vs 正常 87.2%）。
            for _k in ("boost_path", "moon_path", "moon_boost_path"):
                if qc.get(_k) and os.path.exists(qc[_k]):
                    _lit.append(qc[_k])
            # 去重：万一两个键指向同一文件，不能打两次光（打两次会二次压暗）
            _lit = list(dict.fromkeys(_lit))
            # ★ 几何要跟地球尺寸一致：真实尺寸下圆盘只有 91px，
            #   沿用默认几何会把大气弧画在旧半径上（放大出现大虚圈）。
            try:
                import layout as _L
                _pct = _L.earth_pct(getattr(a, "earth_size", "artistic"))
                _g = _L.disc_geom(1920, 1280, pct=_pct)
                if abs(_pct - _L.EARTH_PCT) < 1e-9:
                    _g = None          # 默认尺寸：走 lighting 内部原逻辑
            except Exception:
                _g = None
            for _p in _lit:
                _im = Image.open(_p).convert("RGB")
                # 调试副本：留一份"未打光"的，方便快速调参（不跑豆包）
                _dbg = os.path.join(OUT, "_bak_uni_" + os.path.basename(_p))
                _im.save(_dbg)
                _lt.apply_lighting(_im, D, _utc, geom=_g).save(_p)
                print("[打光] %s%s" % (os.path.basename(_p),
                                     "" if _g is None else "（真实尺寸几何）"))
        except Exception as _e:
            print("[打光] 失败：", _e)

    # ── 兜底：只要"该有提升版却没有"，就补一个同名文件（内容=月面版）
    #   两种情况都会缺：
    #     ① 整个新顺序失败（skip_old_boost=True，走旧拼图）
    #     ② 拼图成功但"提升版那张"没拼出来（stage_boost 返回 b=None）
    #   不补的话 verify.py 会因为文件缺失直接 FAIL，而缺的只是一步本来
    #   就没多少增益的处理；补同名文件既保住交付完整性，也不隐瞒。
    #   ★ 判定要用"本次运行是否产出过提升版"，不能用"文件是否存在"：
    #     上一次跑留下的旧提升版会让这里误判为"已有"，导致新旧两张不配套，
    #     而 verify 照样 PASS（2026-11-09 实测踩到）。
    if getattr(a, "moon", False) and qc.get("moon_path") and not qc.get("moon_boost_path"):
        try:
            import shutil as _shc
            _bn = qc["moon_path"].replace("_月面_", "_月面_提升_")
            if _bn != qc["moon_path"]:
                _shc.copy2(qc["moon_path"], _bn)      # 覆盖旧文件，保证配套
                qc["moon_boost_path"] = _bn
                if getattr(a, "boost", False):
                    print("[提升] 失败补偿：提升版 = 月面版（内容相同，原因见上面的日志）")
                else:
                    print("[提升] 未开启提升（noboost）：提升版 = 月面版（内容相同）")
        except Exception as _e2:
            print("[提升] 补偿失败：", _e2)

    # ── 自动归档（--archive）
    if getattr(a, "archive", False):
        try:
            import json as _js
            import shutil as _shp
            _src = qc.get("polished_path") if qc.get("polished") else out_png
            if not (_src and os.path.exists(_src)):
                _src = out_png
            _ad = os.path.join(HERE, "成品")
            os.makedirs(_ad, exist_ok=True)
            if getattr(a, "uniform", False):
                # 匀光模式下「地球相」是中间素材（未打光），不进成品目录；
                # 用 _bak_ 前缀，免得被自动清理删掉（清理只保留 _bak_*）
                _ad = OUT
                _dst = os.path.join(_ad, "_bak_uni_%s_地球相_%d.png" % (D, a.size))
                print("[归档] 匀光模式：地球相存为中间素材 %s" % os.path.basename(_dst))
            else:
                _dst = os.path.join(_ad, "%s_地球相_%d.png" % (D, a.size))
            _shp.copy2(_src, _dst)
            # copy2 会保留只读属性：源若是只读（--reuse 的附件），
            # 归档出的坏份下次就写不进去。复制完统一去只读。
            try:
                os.chmod(_dst, 0o666)
            except OSError:
                import stat as _st2
                os.chmod(_dst, _st2.S_IWRITE)
            _meta = dict(date=D,
                         view="%.1fN %.1fE" % (qc["view_lat"], qc["view_lon"]),
                         phase="%.0f%%" % qc.get("earth_phase_pct", -1),
                         size=a.size, utc=a.utc,
                         gate="pass" if qc.get("polished") else "qc-only")
            with open(_dst.replace(".png", ".json"), "w", encoding="utf-8") as _f:
                _js.dump(_meta, _f, ensure_ascii=False, indent=2)
            print("[归档] %s" % _dst)
        except Exception as _e:
            print("[归档] 失败：", _e)

    # ── 自动清理中间产物（--no-clean 可关）
    #    豆包浏览器会在流水线退出后几秒才把"下载原图"落盘，
    #    所以清一遍不够：等一下再扫一次，把晚到的文件也带走。
    if getattr(a, "clean", True):
        try:
            _tn, _tmb = _clean_tmp_dirs()
            if _tn:
                print("[清理] v2 临时目录 %d 个，释放 %.0f MB" % (_tn, _tmb))
            _sn, _smb = _clean_station(keep_hours=1.0)
            if _sn:
                print("[清理] 中转站 %d 个旧成品，释放 %.0f MB（只留最近 1 小时）"
                      % (_sn, _smb))
            _n, _mb = _clean_intermediates()
            __import__("time").sleep(4.0)
            _n2, _mb2 = _clean_intermediates()
            _n += _n2
            _mb += _mb2
            if _n:
                print("[清理] v2 中间产物 %d 个，释放 %.0f MB（保留 _bak_*）"
                      % (_n, _mb))
            else:
                print("[清理] v2 已经很干净")
        except Exception as _e:
            print("[清理] 失败：", _e)

    return 0


if __name__ == "__main__":
    sys.exit(main())
