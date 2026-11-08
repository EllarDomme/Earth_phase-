"""fill_gaps.py —— 空洞补全（参数固化版，2026-11-02 定稿）

流程（固定，不允许临场改）:
    ① Aqua 同日互补      羽化 14 px
    ② 横向渐变补色       crossfade_fill
    ③ 借邻近纹理         源半径 ±30 px 内的高频
    ④ 亮度匹配           迭代 3 轮，gain clamp 0.5 ~ 3.0，羽化 8 px

用法:
    python fill_gaps.py 2021-11-09 [--dir E:\\DeskTop\\地球\\v2]

输入: raw_terra_<date>.jpg, raw_aqua_<date>.jpg
输出: filled_<date>.png  +  filled_<date>.json（质检数据）
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_earth as R
import find_seams as FS

P = dict(
    aqua_feather=14,      # Aqua 互补掩膜羽化
    hf_radius=30,         # 借纹理的搜索半径
    bright_rounds=3,      # 亮度匹配轮数
    bright_lo=0.5,        # gain 下限
    bright_hi=3.0,        # gain 上限
    bright_feather=8,     # 亮度场羽化
)



def _max1d(a, r, axis):
    """沿一个轴的 1D 最大值滤波（半径 r），用二进制分解移位实现，结果与 PIL 一致。"""
    out = a
    rem, s = int(r), 1
    while rem > 0:
        if rem & 1:
            out = out | np.roll(out, s, axis) | np.roll(out, -s, axis)
        rem >>= 1
        s <<= 1
    return out


def _dilate_box(mask, k):
    """严格等价于 PIL MaxFilter(k) 的方形最大值滤波（bool 数组）。
       1D 可分离 + 二进制分解，4096×2048 上约 0.3 秒（PIL 要 23 秒）。
       ★ 半径 r = k//2；先横后纵 ⇒ 方形窗口 (2r+1)×(2r+1) = k×k。"""
    r = max(0, int(k) // 2)
    m = mask.astype(bool)
    if r == 0:
        return m
    return _max1d(_max1d(m, r, 1), r, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "v2"))
    ap.add_argument("--terra", default=None,
                    help="Terra 输入文件；默认 raw_terra_<date>.jpg")
    a = ap.parse_args()
    D, OUT = a.date, a.dir

    _terra_path = a.terra or os.path.join(OUT, f"raw_terra_{D}.jpg")
    T = Image.open(_terra_path).convert("RGB")
    if a.terra:
        print("    使用预处理图:", os.path.basename(_terra_path))
    A = Image.open(os.path.join(OUT, f"raw_aqua_{D}.jpg")).convert("RGB")
    W, H = T.size

    # ① Aqua 互补
    valid = R.valid_mask(T)
    out = np.asarray(T).astype(np.float32)
    ak = np.asarray(A).astype(np.float32)
    vk = R.valid_mask(A)
    sel = (~valid) & vk
    if sel.any():
        m = Image.fromarray((sel * 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(P["aqua_feather"]))
        al = (np.asarray(m).astype(np.float32) / 255.0)[..., None]
        out = out * (1 - al) + ak * al
        aqua_filled = sel.copy()          # Aqua 补过的像素（后面也要做亮度校正）
        valid |= vk
    else:
        aqua_filled = np.zeros_like(valid)
    hole = ~valid
    terra_hole = float(100 * (~R.valid_mask(T)).mean())
    after_aqua = float(100 * hole.mean())

    # ② 横向渐变
    base = np.asarray(R.crossfade_fill(
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)), valid)).astype(np.float32)

    # ③ 借邻近纹理
    lf = np.asarray(Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(10))).astype(np.float32)
    hf = base - lf
    filled = base.copy()
    # 超宽空洞兜底：用季节参考图的内容（没有就退回渐变）
    ref = None
    for cand in ("ref_summer_2020.png", "ref_autumn_2020.png",
                 "ref_spring_2020.png", "ref_winter_2020.png"):
        rp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v2", "ref", cand)
        if os.path.exists(rp):
            ri = Image.open(rp).convert("RGB")
            if ri.size != (W, H):
                ri = ri.resize((W, H), Image.LANCZOS)
            ref = np.asarray(ri).astype(np.float32)
            print("    超宽空洞将用参考图补:", cand)
            break

    # 局部空洞密度：大核模糊后即为"周围有多大比例是洞"
    dens_img = Image.fromarray((hole * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(21))
    dens = np.asarray(dens_img).astype(np.float32) / 255.0
    # 0.55 以下正常借纹理；0.75 以上完全不用高频（宁平不糊）
    w_density = np.clip((0.75 - dens) / 0.20, 0.0, 1.0).astype(np.float32)

    n_ref_rows = 0
    for y in range(H):
        row = hole[y]
        if not row.any():
            continue
        x = 0
        while x < W:
            if not row[x]:
                x += 1
                continue
            s = x
            while x < W and row[x]:
                x += 1
            e = x - 1
            L = e - s + 1
            if s - L - 5 < 0 or e + L + 5 >= W:
                # 太宽、两侧借不到 → 用参考图的那一条，并按两侧亮度拉平
                if ref is not None:
                    seg = ref[y, s:e + 1]
                    ring_l = base[y, max(0, s - 20):s]
                    ring_r = base[y, e + 1:min(W, e + 21)]
                    ring = np.concatenate([ring_l, ring_r]) if ring_l.size or ring_r.size else None
                    if ring is not None and ring.size:
                        g = float(ring.mean() + 1e-3) / float(seg.mean() + 1e-3)
                        g = min(max(g, 0.4), 2.5)
                        patch = np.clip(seg * g, 0, 255)
                        # ★ 两端羽化（2026-11-04）：原来整条硬贴，
                        #   在 s / e 处留下笔直的接缝线，被误认成"拉伸条纹"
                        nseg = int(patch.shape[0])
                        fw = int(min(10, max(1, nseg // 6), max(1, nseg // 3)))
                        al = np.ones(nseg, np.float32)
                        if nseg >= 6 and fw >= 1:
                            ramp = np.linspace(0.0, 1.0, fw, endpoint=False, dtype=np.float32)
                            al[:fw] = ramp
                            al[-fw:] = ramp[::-1][:fw]
                        filled[y, s:e + 1] = (base[y, s:e + 1] * (1 - al[:, None])
                                              + patch * al[:, None])
                        n_ref_rows += 1
                continue
            src = np.r_[np.arange(s - L - 5, s - 5), np.arange(e + 6, e + L + 6)]
            if src.size < L:
                continue
            # 左右高频**按权重渐变**混合（原来在中间"硬切换来源"，
            # 会在缺口正中留下一个菱形的拼接疤）
            n = e - s + 1
            left_idx = np.arange(s - L - 5, s - 5)
            right_idx = np.arange(e + 6, e + L + 6)
            ok_l = valid[y, left_idx]
            ok_r = valid[y, right_idx]
            for j, x0 in enumerate(range(s, e + 1)):
                t = j / max(n - 1, 1)                 # 0→1 从左到右
                li = min(j, left_idx.size - 1)
                ri = min(j, right_idx.size - 1)
                hfl = hf[y, left_idx[li]] if ok_l[li] else None
                hfr = hf[y, right_idx[ri]] if ok_r[ri] else None
                if hfl is None and hfr is None:
                    continue
                if hfl is None:
                    hv = hfr
                elif hfr is None:
                    hv = hfl
                else:
                    hv = (1 - t) * hfl + t * hfr       # 渐变，不是切换
                # ★ 超宽空洞（局部空洞占比高）不硬借纹理：
                #   借来的高频不够，就会糊成一片发白（2026-11-04 发现）
                hv = hv * w_density[y, x0]
                filled[y, x0] = lf[y, x0] + hv

    print("    超宽空洞：%d 行改用参考图，参考图%s" % (n_ref_rows, "已载入" if ref is not None else "未载入"))
    mi = Image.fromarray((hole * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
    al2 = (np.asarray(mi).astype(np.float32) / 255.0)[..., None]
    res = np.clip(base * (1 - al2) + filled * al2, 0, 255)

    # 保存补洞掩膜（供检测器判断"哪些地方是补出来的"）
    try:
        touched = (hole | aqua_filled)
        Image.fromarray((touched * 255).astype(np.uint8)).save(
            os.path.join(OUT, "hole_%s.png" % D))
    except Exception as _e:
        print("    掩膜保存失败:", _e)

    # ④ 亮度匹配
    #   ★ 关键：Aqua 补过的像素也要校正，否则会比周围暗一大截
    bright_zone = hole | aqua_filled
    comps = FS.components((bright_zone * 255).astype(np.uint8))
    ratio_med = None
    for _ in range(P["bright_rounds"]):
        gain = np.ones((H, W), np.float32)
        for Q in comps:
            x0 = max(0, int(Q[:, 0].min()) - P["hf_radius"])
            y0 = max(0, int(Q[:, 1].min()) - P["hf_radius"])
            x1 = min(W, int(Q[:, 0].max()) + P["hf_radius"] + 1)
            y1 = min(H, int(Q[:, 1].max()) + P["hf_radius"] + 1)
            # ★ 逐行算增益：一个洞从北到南亮度差很大，
            #   用"整洞一个常数"会在高亮处过曝、暗处欠曝（出现白带/暗带）
            zone = bright_zone[y0:y1, x0:x1]
            wide = _dilate_box(zone, 31)
            # ★ 逐行增益改成整块向量化（2026-11-04：原来逐行 python 循环每轮要十几秒）
            Lc = res[y0:y1, x0:x1].mean(axis=2)
            ring = wide & ~zone
            nz = zone.sum(axis=1).astype(np.float32)
            nr = ring.sum(axis=1).astype(np.float32)
            mh = np.where(nz > 0, (Lc * zone).sum(axis=1) / np.maximum(nz, 1), 0.0)
            mr = np.where(nr > 0, (Lc * ring).sum(axis=1) / np.maximum(nr, 1), 0.0)
            ok = (nz > 0) & (nr >= 8) & (mh >= 5)
            ratio = np.ones_like(mh, dtype=np.float32)
            ratio[ok] = np.clip(mr[ok] / mh[ok], P["bright_lo"], P["bright_hi"])
            gview = gain[y0:y1, x0:x1]
            np.copyto(gview, np.where(zone, ratio[:, None], gview))
        g2 = np.asarray(Image.fromarray(np.clip((gain - 1) * 100 + 128, 0, 255)
                                        .astype(np.uint8))
                        .filter(ImageFilter.GaussianBlur(P["bright_feather"]))).astype(np.float32)
        gg = (1 + (g2 - 128) / 100.0)[..., None]
        al3 = (np.asarray(Image.fromarray((bright_zone * 255).astype(np.uint8))
                          .filter(ImageFilter.GaussianBlur(P["bright_feather"])))
               .astype(np.float32) / 255.0)[..., None]
        res = np.clip(res * (1 + al3 * (gg - 1)), 0, 255)

    # ⑤b 亮度比自校正：把每个缺口的平均亮度向"环"拉平（只改洞内像素）
    #     2026-11-04 加：2026-09-13 出现 1.252 超上限（>1.25）的情况
    for Q in comps:
        x0 = max(0, int(Q[:, 0].min()) - 30)
        y0 = max(0, int(Q[:, 1].min()) - 30)
        x1 = min(W, int(Q[:, 0].max()) + 31)
        y1 = min(H, int(Q[:, 1].max()) + 31)
        sub = hole[y0:y1, x0:x1]
        if sub.sum() < 100:
            continue
        ring = _dilate_box(sub, 31)
        ring &= ~sub
        if ring.sum() < 100:
            continue
        Lsub = res[y0:y1, x0:x1].mean(axis=2)
        mh = float(Lsub[sub].mean())
        mr = float(Lsub[ring].mean())
        if mr < 5 or mh < 1:
            continue
        r = mh / mr
        if r < 0.92 or r > 1.08:
            k = float(np.clip((1.0 / r) ** 0.85, 0.75, 1.33))
            view = res[y0:y1, x0:x1]
            view[sub] = np.clip(view[sub] * k, 0, 255)
            print("   [亮度校正] 缺口 (x%d-%d y%d-%d) 比值 %.3f → ×%.3f"
                  % (x0, x1, y0, y1, r, k))

    # 质检：洞内 / 环 亮度比
    L = res.mean(axis=2)
    rings = []
    for Q in comps:
        x0 = max(0, int(Q[:, 0].min()) - 30)
        y0 = max(0, int(Q[:, 1].min()) - 30)
        x1 = min(W, int(Q[:, 0].max()) + 31)
        y1 = min(H, int(Q[:, 1].max()) + 31)
        sub = hole[y0:y1, x0:x1]
        ring = _dilate_box(sub, 31)
        ring &= ~sub
        if ring.sum() < 100:
            continue
        rings.append(L[y0:y1, x0:x1][sub].mean() / max(L[y0:y1, x0:x1][ring].mean(), 1))
    if rings:
        ratio_med = float(np.median(rings))

    # ⑤ 黑暗残留兜底：缺口收尖处邻居太少，补法覆盖不到，这里按行线性插值
    dark = hole & (res.mean(axis=2) < 6)
    if dark.any():
        for y in range(H):
            row = dark[y]
            if not row.any():
                continue
            x = 0
            while x < W:
                if not row[x]:
                    x += 1
                    continue
                s0 = x
                while x < W and row[x]:
                    x += 1
                e0 = x - 1
                l = res[y, s0 - 1] if s0 > 0 else None
                r = res[y, e0 + 1] if e0 < W - 1 else None
                if l is None and r is None:
                    continue
                if l is None:
                    res[y, s0:e0 + 1] = r
                elif r is None:
                    res[y, s0:e0 + 1] = l
                else:
                    t = np.linspace(0, 1, e0 - s0 + 3)[1:-1][:, None]
                    res[y, s0:e0 + 1] = l * (1 - t) + r * t
        print("  [兜底] 空洞尖端插值 %d px" % int(dark.sum()))

    res8 = np.clip(res, 0, 255).astype(np.uint8)
    Image.fromarray(res8).save(os.path.join(OUT, f"filled_{D}.png"))
    black = float(100 * (res8.mean(axis=2) < 6).mean())
    info = dict(date=D, terra_hole_pct=round(terra_hole, 2),
                after_aqua_pct=round(after_aqua, 2),
                black_pct_after_fill=round(black, 3),
                hole_ring_bright_ratio=None if ratio_med is None else round(ratio_med, 3),
                params=P)
    with open(os.path.join(OUT, f"filled_{D}.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print("[fill] Terra %.2f%% → 互补后 %.2f%% → 补完黑像素 %.3f%%  亮度比 %s"
          % (terra_hole, after_aqua, black,
             "-" if ratio_med is None else "%.2f" % ratio_med))
    return 0


if __name__ == "__main__":
    sys.exit(main())
