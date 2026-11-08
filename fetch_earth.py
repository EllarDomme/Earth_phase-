"""fetch_earth.py —— 按日期取"那天的地球"（带真实气象云）

用法:
    python fetch_earth.py 2008-10-26
    python fetch_earth.py 2008-10-26 --out E:\\DeskTop\\地球\\raw --sat aqua
    python fetch_earth.py today

输出: <out>/<date>_<sat>.jpg  （已裁掉黑边，还原成 2048x1024 的等经纬度全球图）
"""
import argparse
import time
import urllib.request
from datetime import date, datetime

import numpy as np
from PIL import Image

W, H = 2048, 1024
REQ_W, REQ_H = 2000, 1000   # 故意不对齐瓦片网格，避免暴露缺块
SAT = {
    "terra": "MODIS_Terra_CorrectedReflectance_TrueColor",
    "aqua": "MODIS_Aqua_CorrectedReflectance_TrueColor",
    "viirs": "VIIRS_SNPP_CorrectedReflectance_TrueColor",
}


def build_url(day: str, layer: str, w: int = REQ_W, h: int = REQ_H) -> str:
    return (
        "https://wvs.earthdata.nasa.gov/api/v1/snapshot?REQUEST=GetSnapshot"
        f"&TIME={day}&BBOX=-180,-90,180,90&CRS=EPSG:4326"
        f"&LAYERS={layer}&FORMAT=image/jpeg&WIDTH={w}&HEIGHT={h}"
    )


def fetch(url: str, timeout: int = 90, retries: int = 3) -> bytes:
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if len(data) < 5000:
                raise ValueError(f"返回内容过小（{len(data)} 字节）")
            return data
        except Exception as e:                      # noqa: BLE001
            last = e
            print(f"  第 {i+1} 次失败: {type(e).__name__} {e}")
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"取图失败（重试 {retries} 次）: {last}")


def strip_black_bands(img: Image.Image) -> Image.Image:
    """GIBS 快照会把全球图压在中间一条带里，上下是黑边——裁掉再拉回 2:1。"""
    a = np.asarray(img.convert("L"))
    rows = np.nonzero(a.max(axis=1) > 12)[0]
    if len(rows) == 0:
        raise ValueError("整张图都是黑的，没取到数据")
    y0, y1 = rows.min(), rows.max()
    if (y1 - y0) < img.height * 0.9:
        img = img.crop((0, y0, img.width, y1 + 1))
    return img.resize((W, H), Image.LANCZOS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("day", help="日期 YYYY-MM-DD，或 today")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw"))
    ap.add_argument("--sat", default="terra", choices=list(SAT))
    args = ap.parse_args()

    day = date.today().isoformat() if args.day == "today" else args.day
    datetime.strptime(day, "%Y-%m-%d")

    import os
    os.makedirs(args.out, exist_ok=True)
    dst = os.path.join(args.out, f"{day}_{args.sat}.jpg")

    t0 = time.time()
    print(f"[1/3] 取图 {day} / {args.sat} ...")
    data = fetch(build_url(day, SAT[args.sat]))
    t1 = time.time()
    print(f"      下载 {len(data)/1024:.0f} KB，用时 {t1-t0:.1f}s")

    import io
    raw = Image.open(io.BytesIO(data))
    print(f"[2/3] 原始尺寸 {raw.size}，裁黑边 + 还原 ...")
    out = strip_black_bands(raw)
    out.save(dst, quality=95)
    print(f"[3/3] 已保存 {dst}  ({out.size[0]}x{out.size[1]})，总用时 {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
