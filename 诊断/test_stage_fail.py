"""test_stage_fail.py —— 三条失败路径的行为（不调豆包）"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
from stage_boost import boost_then_compose  # noqa: E402

DISC = r"E:\DeskTop\地球\v2\_bak_uni_2021-06-30_地球相_2048.png"
OUT = r"E:\DeskTop\草稿\_stage_fail"

COMPOSE_EXTRA = ["--date", "2021-06-30", "--utc", "22.75", "--earth-pct", "0.36",
                 "--moon-gain", "0.65", "--sky-target", "1,1,1",
                 "--earth-gamma", "1.0", "--earth-sat", "1.0"]


def real_compose(disc, out, width, extra):
    import subprocess
    r = subprocess.run([sys.executable, r"E:\DeskTop\地球\compose_moon.py",
                        disc, out, "--width", str(width)] + list(extra),
                       capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def boost_fail(disc, out, extra):
    return 1, "[提升] 假失败"


def compose_ok(disc, out, width, extra):
    return real_compose(disc, out, width, extra)


def compose_fail(disc, out, width, extra):
    return 1, "假的拼图失败"


def run(tag, boost_runner, compose_runner):
    logs = []
    n, b = boost_then_compose(DISC, os.path.join(OUT, tag), "2021-06-30",
                             width=1920, compose_extra=COMPOSE_EXTRA,
                             log=logs.append,
                             boost_runner=boost_runner, compose_runner=compose_runner)
    exists = (bool(n) and os.path.exists(n), bool(b) and os.path.exists(b))
    print("  %-22s 返回 (n=%s, b=%s)  文件存在 (n=%s, b=%s)"
          % (tag, bool(n), bool(b), exists[0], exists[1]))
    for l in logs:
        if l.startswith(("[提升]", "!!")):
            print("      " + l.strip()[:70])
    return n, b, exists


print("=== 失败路径 ===")
# ① 豆包提升失败 → 应回落到"用原圆盘拼两张"
n1, b1, e1 = run("boost_fail", boost_fail, compose_ok)
assert n1 and b1 and e1 == (True, True), "提升失败时应仍产出两张"
A = np.asarray(Image.open(n1).convert("RGB")).astype(np.float32)
B = np.asarray(Image.open(b1).convert("RGB")).astype(np.float32)
print("     两张是否完全相同：", np.abs(A - B).max() < 0.5)

# ② 第一张拼图失败 → 应返回 (None, None)
n2, b2, e2 = run("compose1_fail", boost_fail, compose_fail)
assert n2 is None and b2 is None, "拼图失败应返回 None"

print()
print("三条失败路径行为正确 ✓")
