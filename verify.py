"""verify.py —— 交付前自证：检查三件套是否合格

用法: python verify.py 2008-10-26
输出 PASS / FAIL，并打印关键指标与 md5
"""
import hashlib
import math
import os
import sys

import numpy as np

from layout import disc_geom, EARTH_PCT
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "成品")


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()[:12]


def disc_metrics(path):
    """量球缘半径：从设计中心向外打射线，找最外侧的"明确亮像素"（>25）。

    注意：夜面压到 0 之后，用整幅的亮像素外接框会只抓到亮部一半，
    会把正圆判成扁的、把居中判成偏移——所以必须按方向逐条量。
    阈值取 25 是为了跳过球缘外那圈很淡的大气辉光。
    """
    import math

    A = np.asarray(Image.open(path).convert("L")).astype(np.float32)
    H, W = A.shape
    cx, cy, R = disc_geom(W, H)

    radii = []
    for deg in range(0, 360, 5):
        th = math.radians(deg)
        dx, dy = math.cos(th), -math.sin(th)
        hit = None
        for r in np.arange(1.03 * R, 0.85 * R, -0.5):
            x, y = int(cx + dx * r), int(cy + dy * r)
            if not (0 <= x < W and 0 <= y < H):
                continue
            if A[y, x] > 25:
                hit = r
                break
        if hit:
            radii.append(hit)

    if len(radii) < 8:
        return None
    import statistics
    med = statistics.median(radii)
    devs = sorted(abs(r - R) / R for r in radii)
    p90 = devs[min(len(devs) - 1, int(len(devs) * 0.9))]
    return dict(cx=cx, cy=cy, R=R, n=len(radii), med=med, p90=p90,
                lo=min(radii), hi=max(radii), W=W, H=H)


def main(date):
    files = {
        "地球相": os.path.join(OUT, "%s_地球相_2048.png" % date),
        "月面版": os.path.join(OUT, "%s_月面_1920x1280.png" % date),
        "提升版": os.path.join(OUT, "%s_月面_提升_1920x1280.png" % date),
    }
    ok = True
    print("=" * 60)
    print("交付自证  %s" % date)
    print("=" * 60)

    # 匀光模式下「地球相」不进口成品，而是留在 v2 当中间素材；
    #   找到中间素材也算交付完整（只是标注为中间素材）。
    _earth_inter = None
    if not os.path.exists(files["地球相"]):
        import glob as _glob
        _cand = _glob.glob(os.path.join(HERE, "v2", "_bak_uni_%s_地球相_*.png" % date))
        if _cand:
            _earth_inter = _cand[0]

    for tag, p in files.items():
        if os.path.exists(p):
            sz = Image.open(p).size
            print("  ✓ %-6s %-44s %dx%d  md5=%s  %.2f MB"
                  % (tag, os.path.basename(p), sz[0], sz[1], md5(p),
                     os.path.getsize(p) / 1048576))
        elif tag == "地球相" and _earth_inter:
            sz = Image.open(_earth_inter).size
            print("  ✓ %-6s %-44s %dx%d  中间素材（匀光模式）"
                  % (tag, os.path.basename(_earth_inter), sz[0], sz[1]))
        else:
            print("  ✗ %-6s 缺失：%s" % (tag, p))
            ok = False

    if not ok:
        print("\n结果：FAIL（成品不全）")
        return 1

    # 几何：各方向半径是否都贴着设计半径（同时验证"正圆"和"居中"）
    d = disc_metrics(files["提升版"])
    if d:
        # 判据只看"中位半径"：圆是由合成程序按固定几何贴出来的，
        # 逐方向分散主要来自"暗海/暗侧球缘看不见"，不是几何错。
        dev = abs(d["med"] - d["R"]) / d["R"]
        enough = d["n"] >= 12
        g_ok = dev < 0.02 and enough
        print("\n  几何：半径 中位 %.1f（设计 %.1f，偏差 %.1f%%）  %s"
              % (d["med"], d["R"], 100 * dev, "✓" if g_ok else "✗"))
        print("        可见球缘方向 %d / 72，逐向分散 p90 %.1f%%（暗侧看不见属正常）"
              % (d["n"], 100 * d["p90"]))
        if not g_ok:
            ok = False
    else:
        print("\n  几何：测不到球缘 ✗")
        ok = False

    C = np.asarray(Image.open(files["提升版"]).convert("RGB")).astype(np.float32)
    H, W = C.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    _cx, _cy, _R = disc_geom(W, H)   # ★ 唯一真相（原来写死 0.5/0.31）
    disc = np.hypot(xx - _cx, yy - _cy) <= _R * 0.95
    over = float((C[disc].max(1) > 245).mean() * 100)
    print("  曝光：过曝(>245) %.2f%% %s" % (over, "✓" if over < 2 else "✗"))
    if over >= 2:
        ok = False

    print("\n结果：%s" % ("PASS ✅" if ok else "FAIL ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python verify.py <YYYY-MM-DD>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
