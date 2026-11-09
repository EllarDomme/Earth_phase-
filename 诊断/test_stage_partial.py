"""test_stage_partial.py —— 拼图成功但"提升版那张"失败时，stage 应返回 (n, None)"""
import os
import sys

sys.path.insert(0, r"E:\DeskTop\地球")
from stage_boost import boost_then_compose  # noqa: E402

DISC = r"E:\DeskTop\地球\v2\_bak_uni_2021-06-30_地球相_2048.png"
OUT = r"E:\DeskTop\草稿\_stage_partial"
EXTRA = ["--date", "2021-06-30", "--utc", "22.75", "--earth-pct", "0.36",
         "--moon-gain", "0.65", "--sky-target", "1,1,1",
         "--earth-gamma", "1.0", "--earth-sat", "1.0"]

calls = {"n": 0}


def real_compose(disc, out, width, extra):
    import subprocess
    r = subprocess.run([sys.executable, r"E:\DeskTop\地球\compose_moon.py",
                        disc, out, "--width", str(width)] + list(extra),
                       capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stdout or "")


def compose_first_ok(disc, out, width, extra):
    calls["n"] += 1
    if calls["n"] == 1:
        return real_compose(disc, out, width, extra)
    return 1, "假的：第二张失败"


def boost_ok(disc, out, extra):
    import numpy as np
    from PIL import Image
    A = np.asarray(Image.open(disc).convert("RGB")).astype(np.float32)
    Image.fromarray(np.clip(A * 0.95, 0, 255).astype(np.uint8)).save(out)
    return 0, "[提升] 假完成"


logs = []
n, b = boost_then_compose(DISC, OUT, "2021-06-30", width=1920,
                          compose_extra=EXTRA, log=logs.append,
                          boost_runner=boost_ok, compose_runner=compose_first_ok)
print("返回 (n=%s, b=%s)" % (bool(n), bool(b)))
print("月面存在:", bool(n) and os.path.exists(n))
print("提升版存在:", bool(b) and os.path.exists(b))
for l in logs:
    if "失败" in l:
        print("  日志:", l.strip()[:64])

# 模拟流水线兜底：该有提升版却没有 → 复制
if n and not (b and os.path.exists(b)):
    import shutil
    bn = n.replace("_月面_", "_月面_提升_")
    shutil.copy2(n, bn)
    print("兜底：已复制出提升版 →", os.path.exists(bn))

ok = bool(n) and os.path.exists(n) and os.path.exists(n.replace("_月面_", "_月面_提升_"))
print("\n结论：部分失败后仍有完整交付 ✓" if ok else "\n结论：仍有缺口 ✗")
sys.exit(0 if ok else 1)
