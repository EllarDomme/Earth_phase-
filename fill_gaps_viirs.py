"""fill_gaps_viirs.py —— 方案B（按"等距"规则修正版）

规则（用户 2026-11-04 定）：
  · 空洞之间**基本等距**（间距 280.5 px），除图像两端
  · 所以"标准空洞"= 每个等距槽位上那个**梭形**
  · **只补超出梭形的部分**（大楔形、横带），梭形内部一律不动

做法：
  ① 用 seams_<date>.json 的曲线 + 相位 + 标准宽度剖面，生成"标准梭形掩膜"
  ② 超出部分 = 空洞 − 标准梭形掩膜
  ③ 这部分用 VIIRS 的真实内容填（逐行增益对齐亮度）
  ④ 输出 prefilled_<date>.png，交给原流程继续补梭形

用法：python fill_gaps_viirs.py <date> [--write-raw]
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, r"E:\DeskTop\地球")
import find_seams as FS

OUT_DEFAULT = r"E:\DeskTop\地球\v2"


def standard_profile(hole, n=64):
    """从"梭形"缺口里统计标准宽度剖面（按相对高度）"""
    comps = FS.components(hole)
    profs = []
    for P in comps:
        h = P[:, 1].max() - P[:, 1].min()
        w = P[:, 0].max() - P[:, 0].min()
        tu, td = FS.tip_taper(P)
        if h < 300 or w > 200 or tu < 6 or td < 6:
            continue
        y0, y1 = int(P[:, 1].min()), int(P[:, 1].max())
        ts, ws = [], []
        for k in range(n):
            y = int(round(y0 + (y1 - y0) * k / (n - 1)))
            r = P[P[:, 1] == y]
            if len(r):
                ts.append(k / (n - 1))
                ws.append(float(r[:, 0].max() - r[:, 0].min()))
        if len(ws) >= n * 0.7:
            profs.append(np.interp(np.linspace(0, 1, n), ts, ws))
    if not profs:
        return None
    p = np.median(np.array(profs), axis=0)
    p[0] = p[-1] = 0
    return p


def build_standard_mask(shape_y, phases, y0, y1, prof, W, H):
    """标准梭形掩膜：每条相位一个细梭形"""
    m = np.zeros((H, W), bool)
    n = len(prof)
    ys = np.arange(y0, y1 + 1)
    t = (ys - y0) / max(1.0, (y1 - y0))
    half = np.interp(t, np.linspace(0, 1, n), prof) / 2.0
    cx = shape_y[ys]
    for ph in phases:
        c = cx + ph
        x_lo = np.floor(c - half).astype(int)
        x_hi = np.ceil(c + half).astype(int)
        for i in range(len(ys)):
            a = max(0, x_lo[i]); b = min(W - 1, x_hi[i])
            if b >= a:
                m[ys[i], a:b + 1] = True
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--dir", default=OUT_DEFAULT)
    ap.add_argument("--viirs", default=None)
    ap.add_argument("--write-raw", action="store_true")
    a = ap.parse_args()
    D, OUT = a.date, a.dir

    mod_path = os.path.join(OUT, "raw_terra_%s.jpg" % D)
    viirs_path = a.viirs or os.path.join(OUT, "raw_NOAA20_%s.jpg" % D)
    if not os.path.exists(viirs_path):
        viirs_path = os.path.join(OUT, "raw_SNPP_%s.jpg" % D)
    seams_path = os.path.join(OUT, "seams_%s.json" % D)
    j = json.load(open(seams_path, encoding="utf-8"))

    M = np.asarray(Image.open(mod_path).convert("RGB")).astype(np.float32)
    V = np.asarray(Image.open(viirs_path).convert("RGB")).astype(np.float32)
    H, W, _ = M.shape
    Lm, Lv = M.mean(axis=2), V.mean(axis=2)
    hole = Lm < 10

    prof = standard_profile(hole)
    if prof is None:
        raise SystemExit("找不到可用的梭形来估宽度剖面")
    print("标准梭形：峰宽 %.0f px" % prof.max())

    # 用 seams.json 的曲线
    c = np.array(j["cubic_coeff"])
    K, pu, pd = j["K"], j["p_up"], j["p_down"]
    Y0, Y1 = int(j["gap_rows"][0]), int(j["gap_rows"][1])
    ANC = (Y0 + Y1) // 2
    yy = np.arange(H, dtype=float)
    S = np.polyval(c, yy)
    S_anc = float(np.polyval(c, ANC))
    k = np.ones(H)
    m1 = yy < Y0
    k[m1] = 1 + (K - 1) * ((Y0 - yy[m1]) / max(Y0, 1)) ** pu
    m2 = yy > Y1
    k[m2] = 1 + (K - 1) * ((yy[m2] - Y1) / max(H - Y1, 1)) ** pd
    shape_y = S_anc + k * (S - S_anc)

    phases = j.get("phases") or [i * j["spacing_px"] for i in range(j["seam_count"])]
    std = build_standard_mask(shape_y, phases, Y0, Y1, prof, W, H)

    beyond = hole & ~std
    fill_mask = beyond & (Lv >= 10)
    print("空洞 %.2f%%   标准梭形 %.2f%%   超出梭形 %.2f%%   可用 VIIRS 补 %.2f%%"
          % (100 * hole.mean(), 100 * (hole & std).mean(),
             100 * beyond.mean(), 100 * fill_mask.mean()))

    both_ok = (~hole) & (Lv >= 10)
    ratio = np.where(both_ok, Lm / np.maximum(Lv, 1.0), np.nan)
    gain = np.ones(H, np.float32)
    for y in range(H):
        row = ratio[y][np.isfinite(ratio[y])]
        if row.size >= 30:
            gain[y] = float(np.median(row))
    kk = np.ones(31, np.float32) / 31.0
    gain_s = np.clip(np.convolve(np.pad(gain, 15, mode="edge"), kk, mode="valid"), 0.5, 2.0)

    out = M.copy()
    out[fill_mask] = np.clip((V * gain_s[:, None, None])[fill_mask], 0, 255)
    al = Image.fromarray((fill_mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
    al = (np.asarray(al).astype(np.float32) / 255.0)[..., None]
    img = np.clip(M * (1 - al) + out * al, 0, 255).astype(np.uint8)

    dst = os.path.join(OUT, "prefilled_%s.png" % D)
    Image.fromarray(img).save(dst)
    if a.write_raw:
        Image.fromarray(img).save(os.path.join(OUT, "raw_terra_%s_viirsfill.jpg" % D), quality=95)

    rec = dict(date=D, hole_pct=round(100 * hole.mean(), 3),
               standard_pct=round(100 * (hole & std).mean(), 3),
               beyond_pct=round(100 * beyond.mean(), 3),
               filled_pct=round(100 * fill_mask.mean(), 3),
               gain_median=round(float(np.median(gain_s)), 3), output=dst)
    json.dump(rec, open(os.path.join(OUT, "prefilled_%s.json" % D), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("增益中位 %.3f  已保存: %s" % (float(np.median(gain_s)), dst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
