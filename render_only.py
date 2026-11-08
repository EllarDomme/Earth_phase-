"""render_only.py —— 只用现有 texture.npy 渲染（不再重建纹理）

用法: python render_only.py <date> <utc> <size> <lat> <lon> <out>
"""
import os
import sys

sys.path.insert(0, r"E:\DeskTop\地球")
import render_earth as RE

date = sys.argv[1]
utc = float(sys.argv[2])
size = int(sys.argv[3])
lat = float(sys.argv[4])
lon = float(sys.argv[5])
out = sys.argv[6]

RE.DATE = date
RE.OUT = os.path.dirname(out) or "."
p = RE.render(lat0=lat, lon0=lon, size=size, utc_hour=utc)
if os.path.abspath(p) != os.path.abspath(out):
    os.replace(p, out)
print("已保存", out)
