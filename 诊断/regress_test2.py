"""regress_test2.py —— 注入 --base 捷径，确认行为自检能抓住"""
import os
import shutil
import subprocess
import sys

HERE = r"E:\DeskTop\地球"
PY = sys.executable
F = os.path.join(HERE, "compose_moon.py")
BAK = F + ".behbak"

shutil.copy(F, BAK)
try:
    s = open(F, encoding="utf-8").read()
    # 把 --base 的镜像判断整段关掉（模拟旧 bug）
    s2 = s.replace("    if (not a.no_auto_base) and a.date and (a.utc is not None):\n        try:\n            import math as _m0",
                   "    if False:\n        try:\n            import math as _m0", 1)
    assert s2 != s, "注入失败：没找到目标代码"
    open(F, "w", encoding="utf-8").write(s2)

    r = subprocess.run([PY, os.path.join(HERE, "audit_behavior.py"), "--strict"],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    print("\n注入 --base 捷径后，退出码 = %d" % r.returncode)
    print("结论：%s" % ("✓ 行为自检抓到了" if r.returncode != 0 else "✗ 漏检！"))
finally:
    shutil.copy(BAK, F)
    os.remove(BAK)
    print("已还原 compose_moon.py")
