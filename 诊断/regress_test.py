"""regress_test.py —— 故意注入三个旧 bug，确认自检全部报警，然后还原"""
import os
import shutil
import subprocess
import sys

HERE = r"E:\DeskTop\地球"
PY = sys.executable
FILES = ["compose_moon.py", "doubao_boost.py", "verify.py"]

# 备份
for f in FILES:
    shutil.copy(os.path.join(HERE, f), os.path.join(HERE, f + ".regbak"))

try:
    # ── 注入 ①：--base 走捷径（跳过镜像）
    p = os.path.join(HERE, "compose_moon.py")
    s = open(p, encoding="utf-8").read()
    s = s.replace("    if (not a.no_auto_base) and a.date and (a.utc is not None):\n        try:\n            import math as _m0", 
                  "    if False:  # 注入的回归\n        try:\n            import math as _m0", 1)
    open(p, "w", encoding="utf-8").write(s)

    # ── 注入 ②：星点 mask 圆心写死
    p = os.path.join(HERE, "compose_moon.py")
    s = open(p, encoding="utf-8").read()
    s = s.replace("_disc = np.hypot(xx - a.cx * Ww, yy - a.cy * Hh)",
                  "_disc = np.hypot(xx - 0.50 * Ww, yy - 0.31 * Hh)", 1)
    open(p, "w", encoding="utf-8").write(s)

    # ── 注入 ③：verify 写死 0.31
    p = os.path.join(HERE, "verify.py")
    s = open(p, encoding="utf-8").read()
    s = s.replace("disc = np.hypot(xx - _cx, yy - _cy) <= _R * 0.95",
                  "disc = np.hypot(xx - 0.5 * W, yy - 0.31 * H) <= EARTH_PCT * W / 2 * 0.95", 1)
    open(p, "w", encoding="utf-8").write(s)

    r = subprocess.run([PY, os.path.join(HERE, "audit_wiring.py"), "--strict"],
                       capture_output=True, text=True)
    bad_lines = [l for l in r.stdout.splitlines() if l.startswith("✗")]
    print("注入 3 个旧 bug 后，自检报告：")
    for l in bad_lines:
        print("  " + l)
    print("\n退出码 = %d（非 0 = 抓住了）" % r.returncode)
    print("结论：%s" % ("✓ 自检有效" if r.returncode != 0 and len(bad_lines) >= 3 else "✗ 自检漏检！"))
finally:
    for f in FILES:
        shutil.copy(os.path.join(HERE, f + ".regbak"), os.path.join(HERE, f))
        os.remove(os.path.join(HERE, f + ".regbak"))
    print("\n已还原 3 个文件")
