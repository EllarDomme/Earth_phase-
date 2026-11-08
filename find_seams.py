"""find_seams.py —— 从 NASA 每日真彩拼图提取拼接线（《技术手册》第九章实现）

用法:
    python find_seams.py <图片> [--out 前缀] [--K 1.18] [--pup 0.75] [--pdn 1.35]

输出:
    <前缀>.png        底图 + 黑色拼接线
    <前缀>_mask.png   二值掩膜（黑底白线）
    <前缀>.json       参数（间距/系数/K/幂次）

算法:
    1. 阈值检测黑缺口，按形状过滤（高>120、高宽比>2、剔除跨日界线残缺段）
    2. 逐行取左右边界 → 中线
    3. 所有线减去各自相位后合并，拟合一条共享三次曲线（样本量×N）
    4. 缺口区间外用非对称放大：上端 r^pup（张开更快），下端 r^pdn（张开更慢）
    5. 验证等距与周期
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw


def components(mask, min_area=40, min_h=120):
    H, W = mask.shape
    seen = np.zeros_like(mask, bool)
    ys, xs = np.nonzero(mask)
    out = []
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        pts = []
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if len(pts) < min_area:
            continue
        P = np.array([(x, y) for y, x in pts], float)
        h = P[:, 1].max() - P[:, 1].min()
        w = P[:, 0].max() - P[:, 0].min()
        if h < min_h or h < 2 * max(w, 1):
            continue
        if w > W * 0.5:          # 横跨半幅以上 = 跨日界线的伪影
            continue
        out.append(P)
    out.sort(key=lambda P: P[:, 0].mean())
    return out


def split_merged(comps, min_sep=30, max_parts=2, width_factor=1.6):
    """把"被暗地表粘在一起"的两个缺口拆开。

    判据：某一行的黑段出现 2 段以上、且间隔 > min_sep。
    拆法：按该行各段的 x 位置排序编号，逐行把像素分给对应的子块；
          单段的行按最近子块中心归属。
    """
    widths = np.array([P[:, 0].max() - P[:, 0].min() for P in comps], float)
    med_w = float(np.median(widths)) if len(widths) else 0
    out = []
    for P in comps:
        # 只有"明显比常规缺口宽"的块才值得尝试拆分（例如宽 311 vs 常规 145）
        if (P[:, 0].max() - P[:, 0].min()) < width_factor * med_w:
            out.append(P)
            continue
        rows = {}
        for x, y in P:
            rows.setdefault(int(y), []).append(int(x))
        merged_rows = []
        kmax = 1
        for y, xs in rows.items():
            xs = sorted(xs)
            runs, cur = [], [xs[0]]
            for a, b in zip(xs, xs[1:]):
                if b - a > min_sep:
                    runs.append((cur[0], cur[-1]))
                    cur = [b]
                else:
                    cur.append(b)
            runs.append((cur[0], cur[-1]))
            if len(runs) >= 2:
                merged_rows.append(y)
                kmax = max(kmax, min(len(runs), max_parts))
        if not merged_rows or kmax < 2:
            out.append(P)
            continue

        # 用"合并行"的中段估计每个子块中心
        centers = []
        for y in merged_rows:
            xs = sorted(rows[y])
            runs, cur = [], [xs[0]]
            for a, b in zip(xs, xs[1:]):
                if b - a > min_sep:
                    runs.append((cur[0], cur[-1]))
                    cur = [b]
                else:
                    cur.append(b)
            runs.append((cur[0], cur[-1]))
            for (a, b) in runs[:max_parts]:
                centers.append((a + b) / 2.0)
        centers = np.sort(np.array(centers))
        # 聚成 kmax 个中心（简单 k-means 一步）
        k = kmax
        cs = np.linspace(centers.min(), centers.max(), k)
        for _ in range(10):
            lab = np.abs(centers[:, None] - cs[None, :]).argmin(axis=1)
            cs = np.array([centers[lab == j].mean() if (lab == j).any() else cs[j]
                           for j in range(k)])

        parts = [[] for _ in range(k)]
        for y, xs in rows.items():
            xs = sorted(xs)
            runs, cur = [], [xs[0]]
            for a, b in zip(xs, xs[1:]):
                if b - a > min_sep:
                    runs.append((cur[0], cur[-1]))
                    cur = [b]
                else:
                    cur.append(b)
            runs.append((cur[0], cur[-1]))
            if len(runs) >= 2:
                for (a, b) in runs[:k]:
                    j = int(np.abs(cs - (a + b) / 2.0).argmin())
                    parts[j].extend((x, y) for x in range(a, b + 1))
            else:
                a, b = runs[0]
                j = int(np.abs(cs - (a + b) / 2.0).argmin())
                parts[j].extend((x, y) for x in range(a, b + 1))

        for pj in parts:
            if len(pj) >= 40:
                out.append(np.array(pj))
            else:
                out.append(P)          # 太小的碎片退回原块
    return out


def tip_taper(P, max_rows=60, w_thr=4):
    """返回 (顶端收尖行数, 底端收尖行数)。行数为"宽度≤w_thr 的连续行数"。"""
    y0, y1 = int(P[:, 1].min()), int(P[:, 1].max())

    def w(y):
        r = P[P[:, 1] == y]
        return int(r[:, 0].max() - r[:, 0].min()) if len(r) else -1

    up = 0
    for y in range(y0, min(y0 + max_rows, y1)):
        v = w(y)
        if v < 0 or v > w_thr:
            break
        up += 1
    dn = 0
    for y in range(y1, max(y1 - max_rows, y0), -1):
        v = w(y)
        if v < 0 or v > w_thr:
            break
        dn += 1
    return up, dn

def midline_rows(P):
    ys, cs = [], []
    for y in np.unique(P[:, 1]):
        xs = P[P[:, 1] == y][:, 0]
        if xs.max() - xs.min() >= 4:
            ys.append(y)
            cs.append((xs.min() + xs.max()) / 2)
    return np.array(ys, float), np.array(cs, float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", default=None)
    ap.add_argument("--thresh", type=float, default=10)
    ap.add_argument("--K", type=float, default=1.18)
    ap.add_argument("--pup", type=float, default=0.75)
    ap.add_argument("--pdn", type=float, default=1.35)
    ap.add_argument("--width", type=int, default=0, help="线宽；0=按图宽自动（约 W/1400，最小 1）")
    ap.add_argument("--draw-through-gaps", action="store_true",
                    help="缺口内部也画线；默认只在缺口外的部分画")
    a = ap.parse_args()

    im = Image.open(a.path).convert("RGB")
    W, H = im.size
    g = np.asarray(im.convert("L")).astype(np.int16)
    raw_gray = g

    comps = components(g < a.thresh)
    # ── 端部清晰度检测：钝头的缺口不参与拟合，位置由邻居推算 ──
    clear_comps, blunt_comps = [], []
    for P_ in comps:
        tu, td = tip_taper(P_)
        (clear_comps if (tu >= 6 and td >= 6) else blunt_comps).append(P_)
    if blunt_comps:
        print(f"[1] 端部模糊的缺口 {len(blunt_comps)} 个 → 改用邻居基准推算")
    if len(clear_comps) >= 5:
        comps = clear_comps
    print(f"[1] {os.path.basename(a.path)}  {W}x{H}  缺口 {len(comps)} 个")
    if len(comps) < 3:
        print("    缺口太少，放弃")
        return 1

    raw, spans = [], []
    for P in comps:
        ys, cs = midline_rows(P)
        raw.append((ys, cs))
        spans.append((int(ys.min()), int(ys.max())))
    # 相位：按间距累加，而不是用每条线的绝对值（避免个别线抖动）
    step = float(np.median([P[:, 0].mean() for P in comps][1:])) if False else None
    xs_mean = [P[:, 0].mean() for P in comps]
    step = float(np.median(np.diff(xs_mean)))
    pooled = [(ys, cs - i * step) for i, (ys, cs) in enumerate(raw)]
    ys_all = np.concatenate([p[0] for p in pooled])
    u_all = np.concatenate([p[1] for p in pooled])
    S = np.polyfit(ys_all, u_all, 3)
    # 用每条线自己的相位重算，并剔一次离群（防跨日界线段污染形状）
    phases = []
    for ys, cs in raw:
        phases.append(float(np.median(cs - np.polyval(S, ys))))
    resid = [float(np.median(np.abs(cs - (np.polyval(S, ys) + ph)))) for (ys, cs), ph in zip(raw, phases)]
    med = float(np.median(resid)) + 1e-6
    keep = [i for i, r in enumerate(resid) if r < max(3.0, 6 * med)]
    ys2 = np.concatenate([raw[i][0] for i in keep])
    u2 = np.concatenate([raw[i][1] - phases[i] for i in keep])
    S = np.polyfit(ys2, u2, 3)
    phases = [float(np.median(cs - np.polyval(S, ys))) for ys, cs in raw]
    # ★ 残差必须用"每条线自己的相位"算；用 索引×间距 会因少检/多检一条而整体错位
    _res = []
    for (ys_, cs_), ph_ in zip(raw, phases):
        _res.append(cs_ - (np.polyval(S, ys_) + ph_))
    _res = np.concatenate(_res)
    rms = float(np.sqrt(np.mean(_res ** 2)))
    print(f"[2] 共享三次拟合：残差 {rms:.2f} px  间距 {step:.1f} px "
          f"→ {360/(step/W*360):.1f} 圈/天")

    Y0 = int(np.median([s[0] for s in spans]))
    Y1 = int(np.median([s[1] for s in spans]))
    ANC = (Y0 + Y1) // 2
    S_anc = float(np.polyval(S, ANC))
    yy = np.arange(H, dtype=float)
    dev = np.polyval(S, yy) - S_anc
    s = np.ones_like(yy)
    s[yy < Y0] = 1 + (a.K - 1) * ((Y0 - yy[yy < Y0]) / Y0) ** a.pup
    s[yy > Y1] = 1 + (a.K - 1) * ((yy[yy > Y1] - Y1) / (H - Y1)) ** a.pdn
    shape = S_anc + s * dev
    print(f"[3] 端部放大 K={a.K}  pup={a.pup}  pdn={a.pdn}")

    # ★ 钝头缺口：位置由最近的清晰缺口推算（同一张图里"明显的空洞"作基准）
    est_phases = []
    if len(clear_comps) >= 5 and len(blunt_comps) > 0:
        cx = np.array([P[:, 0].mean() for P in clear_comps])
        for Q in blunt_comps:
            qx = float(Q[:, 0].mean())
            j = int(np.abs(cx - qx).argmin())
            k = int(round((qx - cx[j]) / step))
            ph_new = phases[j] + k * step
            est_phases.append(ph_new)
            print(f"    推算第 {len(phases)+len(est_phases)} 条：x≈{qx:.0f} "
                  f"← 参照 x≈{cx[j]:.0f}（{'%+d' % k} 个间距）")

    # ★ 补齐缺失的槽位：间距必须接近 step，差 ≥1.5 个间距就说明漏了一条
    _all = sorted(list(phases) + list(est_phases))
    _filled = []
    for _i, _p in enumerate(_all):
        _filled.append(_p)
        if _i + 1 < len(_all):
            _k = int(round((_all[_i + 1] - _p) / step))
            if _k >= 2:
                for _m in range(1, _k):
                    _filled.append(_p + _m * step)
    _added = len(_filled) - len(_all)
    if _added > 0:
        print(f"    补齐缺失槽位 {_added} 条：{len(_all)} → {len(_filled)}")
        est_phases = (_filled[len(phases):] if len(_filled) > len(phases) else [])
        phases = _filled[:len(phases)]

    w = a.width if a.width > 0 else max(1, round(W / 1400))
    out = im.copy()
    d = ImageDraw.Draw(out)
    mask = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(mask)
    all_phases = list(phases) + list(est_phases)
    # 若上面补齐过，以 _filled 为准
    try:
        if len(_filled) > len(all_phases):
            all_phases = sorted(_filled)
    except NameError:
        pass
    for i in range(len(all_phases)):
        x = shape + all_phases[i]
        pts, seg = [], []
        for u, v in zip(x, yy):
            if not (-5 <= u < W + 5):
                continue
            xi = int(min(max(u, 0), W - 1))
            yv = int(v)
            in_gap = (not a.draw_through_gaps) and raw_gray[yv, xi] < 10
            if in_gap:
                if len(seg) > 1:
                    pts.append(seg)
                seg = []
            else:
                seg.append((float(u), float(v)))
        if len(seg) > 1:
            pts.append(seg)
        for s_ in pts:
            d.line(s_, fill=(0, 0, 0), width=w)
            dm.line(s_, fill=255, width=max(1, w - 1))

    # 统一整理一份"最终相位列表"，供下游（建标准梭形掩膜等）使用
    _ph_all = sorted(list(phases) + list(est_phases)) if 'est_phases' in dir() else sorted(phases)
    try:
        if len(_filled) > len(_ph_all):
            _ph_all = sorted(_filled)
    except NameError:
        pass

    prefix = a.out or (a.path.rsplit(".", 1)[0] + "_seams")
    out.save(prefix + ".png")
    mask.save(prefix + "_mask.png")
    cfg = {
        "source": os.path.basename(a.path),
        "size": [W, H],
        # seam_count = 最终画出的条数（清晰 + 推算）；clear_count = 真正测到的
        "seam_count": len(phases) + len(est_phases) if 'est_phases' in dir() else len(comps),
        "phases": [round(float(v), 3) for v in _ph_all],
        "clear_count": len(comps),
        "estimated_count": len(est_phases) if 'est_phases' in dir() else 0,
        "spacing_px": round(step, 2),
        "spacing_deg": round(step / W * 360, 2),
        "orbits_per_day": round(360 / (step / W * 360), 2),
        "cubic_coeff": [float(v) for v in S],
        "fit_rms_px": round(rms, 2),
        "gap_rows": [Y0, Y1],
        "K": a.K,
        "p_up": a.pup,
        "p_down": a.pdn,
        "formula": "x(y) = S_anc + k(y)*(polyval(cubic,y) - S_anc) + i*spacing",
    }
    with open(prefix + ".json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"[4] 已保存 {prefix}.png / _mask.png / .json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
