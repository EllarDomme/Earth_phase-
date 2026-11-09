"""repair_2005.py —— 零额度修复：用已存下的提升圆盘重拼 + 打光

不重新调豆包，只重跑「拼图 + 打光」两步。
"""
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
sys.path.insert(0, HERE)
import lighting  # noqa: E402

DATE = "2005-01-01"
UTC = 1.25
BOOSTED = os.path.join(HERE, "成品", "_boosted_disc_%s.png" % DATE)
DST = os.path.join(HERE, "成品", "%s_月面_提升_1920x1280.png" % DATE)

if not os.path.exists(BOOSTED):
    sys.exit("缺少提升后的圆盘：%s" % BOOSTED)
print("用已存的提升圆盘重拼（不调豆包）：%s" % BOOSTED)

r = subprocess.run([sys.executable, os.path.join(HERE, "compose_moon.py"),
                    BOOSTED, DST, "--width", "1920",
                    "--date", DATE, "--utc", str(UTC),
                    "--earth-pct", "0.36", "--sky-target", "1,1,1",
                    "--earth-gamma", "1.0", "--earth-sat", "1.0",
                    "--moon-gain", "0.65"], capture_output=True, text=True)
for ln in (r.stdout or "").splitlines():
    if ln.startswith(("月面：", "底图选择", "输出")):
        print("  " + ln)
if r.returncode != 0:
    sys.exit("拼图失败：" + (r.stderr or "")[-300:])

im = Image.open(DST).convert("RGB")
lighting.apply_lighting(im, DATE, UTC, verbose=True).save(DST)
print("已打光：%s" % DST)

# 中间产物挪出 成品/
_v2 = os.path.join(HERE, "v2")
os.makedirs(_v2, exist_ok=True)
shutil.move(BOOSTED, os.path.join(_v2, os.path.basename(BOOSTED)))
print("提升圆盘已挪到 v2/")

A = np.asarray(Image.open(DST).convert("L")).astype(np.float32)
d = A[100:700, 700:1200]
print("复查 提升版地球区：最小 %.0f 中位 %.0f 暗像素 %.1f%%"
      % (d.min(), np.median(d), 100.0 * (d < 20).mean()))
