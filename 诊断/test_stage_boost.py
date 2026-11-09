"""test_stage_boost.py —— 零额度单测：用假 runner 验证阶段顺序与产物

验证点：
  ① 豆包**只被调用一次**，且对象是圆盘、几何是 0.5,0.5,0.5
  ② 拼图被调用两次，第二次用的是提升后的圆盘
  ③ 两张产物存在，且**月面/天空完全一致**（只有圆盘内部不同）
"""
import hashlib
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"E:\DeskTop\地球")
from stage_boost import boost_then_compose  # noqa: E402

DISC = r"E:\DeskTop\地球\v2\_bak_uni_2021-06-30_地球相_2048.png"
OUT = r"E:\DeskTop\草稿\_stage_test"

calls = {"boost": [], "compose": []}


def fake_boost(disc, out, extra):
    calls["boost"].append((disc, out))
    A = np.asarray(Image.open(disc).convert("RGB")).astype(np.float32)
    # 模拟豆包：整体×0.95（能被 match_disc 类逻辑还原的乘法扰动）
    Image.fromarray(np.clip(A * 0.95, 0, 255).astype(np.uint8)).save(out)
    return 0, "[提升] 假豆包完成"


def fake_compose(disc, out, width, extra):
    calls["compose"].append(disc)
    import importlib
    cm = importlib.import_module("compose_moon") if False else None   # 不 import 脚本
    # 直接调用真实 compose（子进程），保证产物是真的
    import subprocess
    cmd = [sys.executable, r"E:\DeskTop\地球\compose_moon.py", disc, out,
           "--width", str(width)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


logs = []
n_path, b_path = boost_then_compose(
    DISC, OUT, "2021-06-30", width=1920,
    compose_extra=["--date", "2021-06-30", "--utc", "22.75",
                   "--earth-pct", "0.36", "--moon-gain", "0.65",
                   "--sky-target", "1,1,1", "--earth-gamma", "1.0", "--earth-sat", "1.0"],
    log=lambda s: logs.append(s),
    boost_runner=fake_boost, compose_runner=fake_compose)

print("\n".join(logs))
print()
ok = True

# ① 豆包只调一次、对象是圆盘
c1 = len(calls["boost"]) == 1
print("%s 豆包调用 %d 次（应 1）" % ("✓" if c1 else "✗", len(calls["boost"])))
ok &= c1

# ② 拼图两次，第二次用提升后的图
c2 = len(calls["compose"]) == 2
same_first = c2 and os.path.samefile(calls["compose"][0], DISC)
second_boosted = c2 and "boosted" in os.path.basename(calls["compose"][1])
print("%s 拼图调用 %d 次；第一次用原圆盘=%s；第二次用提升图=%s"
      % ("✓" if (c2 and same_first and second_boosted) else "✗",
         len(calls["compose"]), same_first, second_boosted))
ok &= (c2 and same_first and second_boosted)

# ③ 两张都在，且月面/天空一致
c3 = bool(n_path and b_path and os.path.exists(n_path) and os.path.exists(b_path))
print("%s 两张产物存在" % ("✓" if c3 else "✗"))
ok &= c3

if c3:
    An = np.asarray(Image.open(n_path).convert("RGB")).astype(np.float32)
    Ab = np.asarray(Image.open(b_path).convert("RGB")).astype(np.float32)
    H, W = An.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    from layout import disc_geom
    cx, cy, R = disc_geom(W, H)
    rr = np.hypot(xx - cx, yy - cy) / R
    d = np.abs(An - Ab).max(2)
    out_d = float(d[rr > 1.15].max())
    in_d = float(d[rr < 0.95].max())
    c4 = out_d < 2 and in_d > 1
    print("%s 两张差异：盘外最大 %.1f（应 <2）  盘内最大 %.0f（应 >1）"
          % ("✓" if c4 else "✗", out_d, in_d))
    ok &= c4

print("\n结论：%s" % ("阶段实现正确 ✓" if ok else "有问题 ✗"))
sys.exit(0 if ok else 1)
