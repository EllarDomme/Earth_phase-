"""rebuild_all.py —— 用当前规则重出全部日期（零额度，不碰豆包）"""
import glob
import json
import os
import subprocess
import sys

HERE = r"E:\DeskTop\地球"
PY = sys.executable


def run(args):
    return subprocess.run([PY] + args, capture_output=True, text=True, timeout=900)


ok, bad = 0, []
for disc in sorted(glob.glob(os.path.join(HERE, "v2", "_bak_uni_*_地球相_2048.png"))):
    d = os.path.basename(disc).replace("_bak_uni_", "").replace("_地球相_2048.png", "")
    j = os.path.join(HERE, "v2", "_bak_uni_%s_地球相_2048.json" % d)
    if not os.path.exists(j):
        print("  %-12s 缺 json，跳过" % d)
        continue
    r = run([os.path.join(HERE, "make_earth_full.py"), d, "--size", "2048",
             "--reuse", disc, "--moon", "--uniform", "--archive"])
    tag = [l for l in r.stdout.splitlines() if "月面：" in l or "用【" in l]
    tier = ""
    for l in tag:
        if "用【" in l:
            tier = l.strip().split("用【")[1].split("】")[0]
    prod = os.path.join(HERE, "成品", "%s_月面_提升_1920x1280.png" % d)
    if r.returncode == 0 and os.path.exists(prod):
        ok += 1
        print("  %-12s ✓ %-6s %s" % (d, tier, os.path.basename(prod)))
    else:
        bad.append(d)
        print("  %-12s ✗ %s" % (d, (r.stderr or "").strip().splitlines()[-1][:70] if r.stderr else "失败"))

print()
print("成功 %d，失败 %d" % (ok, len(bad)))
if bad:
    print("失败日期：", bad)
