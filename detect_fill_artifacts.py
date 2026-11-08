"""detect_fill_artifacts.py —— 无需参考图的"颜色异常"检测器

核心物理依据（不需要任何底图、不需要日期）：
  地球有大气 → 瑞利散射一定给蓝通道加光
  所以真实地表/海面，即使很暗，蓝通道也不会接近 0

  反过来：B≈0 而 R 明显>0 的暗区 → **一定是人为填充**（数据缺失被染色）

检测的三类"不可能色"
  S1 暗红填充   ：B < 10 且 R > 15 且 亮度 < 60
  S2 暗绿/暗青  ：G 或 B 单通道接近 0 但另两通道还有值（同理会是填充）
  S3 纯黑洞     ：三通道全 < 8（真缺失，未补洞）

用法：
  python detect_fill_artifacts.py <图.png|jpg> [--min-area 1500] [--out 前缀]
输出：
  <前缀>_fillartifacts.json   清单（经纬度 + 面积）
  <前缀>_fillartifacts.png    标注图
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

EARTH_R = 6371.0


def label_clusters(mask, min_area):
    from collections import deque
    H, W = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    ys, xs = np.nonzero(mask)
    for sy, sx in zip(ys, xs):
        if seen[sy, sx]:
            continue
        q = deque([(sy, sx)]); seen[sy, sx] = True; pts = []
        while q:
            cy, cx = q.popleft(); pts.append((cy, cx))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; q.append((ny, nx))
        if len(pts) >= min_area:
            py = np.array([p[0] for p in pts]); px = np.array([p[1] for p in pts])
            out.append(dict(area=len(pts),
                            x0=int(px.min()), x1=int(px.max()),
                            y0=int(py.min()), y1=int(py.max()),
                            px=float(px.mean()), py=float(py.mean()),
                            ys=py, xs=px))
    out.sort(key=lambda d: -d["area"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--min-area", type=int, default=1500)
    ap.add_argument("--out", default=None)
    ap.add_argument("--mask", default=None,
                    help="补洞掩膜（白色=补出来的地方）；给了就只查这些区域的糊化")
    ap.add_argument("--view", default=None,
                    help="球体图的视点 lat,lon（如 23.4,119.0）；给等经纬图则不用")
    a = ap.parse_args()

    img = Image.open(a.image).convert("RGB")
    W, H = img.size
    arr = np.asarray(img).astype(np.float32)
    R, G, B = arr[..., 0], arr[..., 1], arr[..., 2]
    L = arr.mean(axis=2)
    tot = arr.sum(axis=2) + 1e-6

    # 大气下"蓝通道占比"的经验下限
    blue_share = B / tot

    s1 = (B < 10) & (R > 15) & (L < 60)                      # 暗红填充
    s2 = (blue_share < 0.04) & (L < 60) & (L > 8) & (B < 10)  # 允许的扩宽：蓝占比极低
    s3 = (R < 8) & (G < 8) & (B < 8)                          # 纯黑空洞

    # 球体图有黑色背景：检测"与图像边框相连的最大黑区"，从 S3 里剔除
    def background_mask(black):
        from collections import deque
        Hh, Ww = black.shape
        seen = np.zeros_like(black, bool)
        q = deque()
        for x in range(Ww):
            for y in (0, Hh - 1):
                if black[y, x] and not seen[y, x]:
                    seen[y, x] = True; q.append((y, x))
        for y in range(Hh):
            for x in (0, Ww - 1):
                if black[y, x] and not seen[y, x]:
                    seen[y, x] = True; q.append((y, x))
        while q:
            cy, cx = q.popleft()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < Hh and 0 <= nx < Ww and black[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; q.append((ny, nx))
        return seen

    def clean(m, k=5):
        return np.asarray(Image.fromarray((m * 255).astype(np.uint8))
                          .filter(ImageFilter.MedianFilter(k))) > 127

    _yy = np.arange(H)[:, None].repeat(W, axis=1)
    _lat = 90.0 - _yy / H * 180.0
    polar_any = np.abs(_lat) > 78          # 极区常年暗/冰盖，排除

    # ── S4 发白/发糊型：像素级颗粒度塔陷──
    #   真实沙漠：颗粒 1.5~5.6；补洞糊掉：0.26~0.67
    _L = arr.mean(axis=2)
    _b1 = np.asarray(Image.fromarray(_L.astype(np.uint8))
                     .filter(ImageFilter.GaussianBlur(1))).astype(np.float32)
    grain = np.abs(_L - _b1)
    grain_s = np.asarray(Image.fromarray(np.clip(grain * 100, 0, 255).astype(np.uint8))
                         .filter(ImageFilter.BoxBlur(6))).astype(np.float32) / 100.0
    # 周围（较大范围）的颗粒水平
    grain_bg = np.asarray(Image.fromarray(np.clip(grain_s * 100, 0, 255).astype(np.uint8))
                          .filter(ImageFilter.BoxBlur(60))).astype(np.float32) / 100.0
    # 海洋/冰盖本来就平，排除
    ocean_like = (B > R * 1.05) & (_L < 95)
    ice_like = (_L > 225) & (arr.std(axis=2) < 14)
    if a.mask and os.path.exists(a.mask):
        mi_ = np.asarray(Image.open(a.mask).convert("L")).astype(np.float32) / 255.0
        if mi_.shape != (H, W):
            mi_ = np.asarray(Image.fromarray((mi_ * 255).astype(np.uint8))
                             .resize((W, H), Image.LANCZOS)).astype(np.float32) / 255.0
        filled_area = mi_ > 0.5
        # 只看"我们补过的地方"：里面颗粒塌陷 = 补糊了
        smear = filled_area & (grain_s < 1.0) & (~ocean_like) & (~ice_like) & (~polar_any)
        print("（已用掩膜限定范围：补洞区域占 %.1f%%）" % (100 * filled_area.mean()))
    else:
        smear = (grain_s < 0.85) & (grain_bg > 1.2) & (_L > 20) & (~ocean_like) & (~ice_like) & (~polar_any)

    bg = background_mask(s3)
    rep_bg = float(bg.mean())
    masks = {"S1_暗红填充": clean(s1 & ~bg),
             "S2_蓝占比异常": clean(s2 & ~s1 & ~bg),
             "S3_纯黑空洞": clean(s3 & ~bg),
             "S4_涂抹发白": clean(smear & ~bg & ~s1, 7)}

    rep = {"image": os.path.abspath(a.image), "size": [W, H], "classes": {}}
    # 背景（球外黑底）单独统计
    rep["background_pct"] = round(100.0 * rep_bg, 2)
    vis = img.copy(); dv = ImageDraw.Draw(vis)
    colors = {"S1_暗红填充": (255, 0, 0), "S2_蓝占比异常": (255, 160, 0),
              "S3_纯黑空洞": (0, 200, 255), "S4_涂抹发白": (255, 0, 255)}

    # 每个像素的经纬（等经纬图直接换算）
    globe = rep_bg > 0.05          # 有明显黑底 → 当作球体图
    cx, cy = (W - 1) / 2.0, (H - 1) / 2.0
    R = min(W, H) / 2.0
    vlat = vlon = None
    if a.view:
        vlat, vlon = [float(v) for v in a.view.split(",")]
    if globe and vlat is None:
        print("⚠ 检测到球体图但没给 --view，地名会不准")
    ex = ey = ez = None
    if globe and vlat is not None:
        p0, l0 = np.radians(vlat), np.radians(vlon)
        ez = np.array([np.cos(p0) * np.cos(l0), np.cos(p0) * np.sin(l0), np.sin(p0)])
        ex = np.array([-np.sin(l0), np.cos(l0), 0.0])
        ey = np.cross(ez, ex)

    def to_ll(px, py):
        if globe and vlat is not None:
            X = (px - cx) / R
            Y = (cy - py) / R
            r2 = X * X + Y * Y
            if r2 > 1:
                return (90 - py / H * 180.0, px / W * 360.0 - 180.0)
            Z = np.sqrt(max(0.0, 1 - r2))
            n = X * ex + Y * ey + Z * ez
            lat = float(np.degrees(np.arcsin(max(-1.0, min(1.0, n[2])))))
            lon = float(np.degrees(np.arctan2(n[1], n[0])))
            return (lat, lon)
        return (90 - py / H * 180.0, px / W * 360.0 - 180.0)

    total_bad = 0
    for name, m in masks.items():
        cl = label_clusters(m, a.min_area)
        total_bad += int(m.sum())
        rep["classes"][name] = {"pixels": int(m.sum()),
                                "pct": round(100.0 * m.sum() / (W * H), 3),
                                "clusters": []}
        for c in cl[:20]:
            lat0, lon0 = to_ll(c["x0"], c["y0"])
            lat1, lon1 = to_ll(c["x1"], c["y1"])
            lat_c, lon_c = to_ll(c["px"], c["py"])
            # 真实面积：每个像素 ≈ (360/W * 111 * cos(lat)) × (180/H * 111) km²
            px_area = (360.0 / W * 111 * np.cos(np.radians(lat_c))) * (180.0 / H * 111)
            km2 = c["area"] * px_area
            item = dict(area=c["area"],
                        lat=round(lat_c, 1), lon=round(lon_c, 1),
                        lat_range=[round(lat0, 1), round(lat1, 1)],
                        lon_range=[round(lon0, 1), round(lon1, 1)],
                        km2=round(km2),
                        box=[c["x0"], c["y0"], c["x1"], c["y1"]],
                        rgb=[round(float(v), 0) for v in
                             arr[c["ys"], c["xs"]].mean(axis=0)])
            rep["classes"][name]["clusters"].append(item)
            dv.rectangle(item["box"], outline=colors[name], width=4)

    out_png = (a.out + "_fillartifacts.png") if a.out else os.path.splitext(a.image)[0] + "_fillartifacts.png"
    vis.save(out_png)
    out_json = os.path.splitext(out_png)[0] + ".json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    print("图 %s  %dx%d" % (os.path.basename(a.image), W, H))
    print("判据（无需参考图）：")
    print("  S1 暗红填充   B<10 且 R>15 且 亮度<60")
    print("  S2 蓝占比异常 蓝通道占总和 <4%%，且亮度 8~60")
    print("  S3 纯黑空洞   三通道均 <8")
    print("  S4 发白发糊   像素级颗粒 <0.85（真实沙漠 1.5~5.6）→ 补洞糊掉的痕迹")
    print()
    # 极夜：高纬的大片纯黑，不算错误
    s3c = rep["classes"]["S3_纯黑空洞"]["clusters"]
    polar = [c for c in s3c if abs(c["lat"]) > 78 and c["area"] > 20000]
    if polar:
        rep["classes"]["S3_纯黑空洞"]["clusters"] = [c for c in s3c if c not in polar]
        rep["polar_night"] = {"count": len(polar),
                              "pixels": sum(c["area"] for c in polar),
                              "note": "高纬极夜，属真实黑暗，不是缺陷"}
    for name, d in rep["classes"].items():
        print("%s ：%d px（%.3f%%）  团块 %d 个" % (name, d["pixels"], d["pct"], len(d["clusters"])))
        for c in d["clusters"][:5]:
            print("   %8d px  %6.1fN %7.1fE   范围 %.1f~%.1fN %.1f~%.1fE  面积 %.0f 万 km²"
                  "   RGB %s"
                  % (c["area"], c["lat"], c["lon"], c["lat_range"][0], c["lat_range"][1],
                     c["lon_range"][0], c["lon_range"][1], c["km2"] / 1e4, c["rgb"]))
    print()
    print("合计异常像素 %.3f%%" % (100.0 * total_bad / (W * H)))
    print("标注图:", out_png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
