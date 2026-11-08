"""check_deadcalls.py —— 检查流水线里调用的脚本是否都存在（防"死调用"）"""
import os
import re

HERE = r"E:\DeskTop\地球"
FILE = os.path.join(HERE, "make_earth_full.py")

s = open(FILE, encoding="utf-8").read()
calls = sorted(set(re.findall(r'os\.path\.join\(HERE, "([\w.]+\.py)"\)', s)))

print("make_earth_full.py 以子进程调用的脚本：")
bad = 0
for c in calls:
    p = os.path.join(HERE, c)
    ok = os.path.exists(p)
    print("  %s %s" % ("✓" if ok else "✗ 缺失", c))
    if not ok:
        bad += 1

# 再扫一遍所有 .py 里 import 的本地模块
import ast

print("\n本地 import 检查：")
local = set()
for f in os.listdir(HERE):
    if not f.endswith(".py"):
        continue
    try:
        tree = ast.parse(open(os.path.join(HERE, f), encoding="utf-8").read())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module.split(".")[0]]
        for m in mods:
            if os.path.exists(os.path.join(HERE, m + ".py")):
                local.add(m)
for m in sorted(local):
    print("  ✓ %s.py" % m)

# 关键外部工具是否已收进项目
print("\n项目内置工具：")
for rel in (r"tools\paint.mjs", r"tools\lib\bridge.mjs"):
    q = os.path.join(HERE, rel)
    ok = os.path.exists(q)
    print("  %s %s" % ("✓" if ok else "✗ 缺失", rel))
    if not ok:
        bad += 1

print("\n结论：%s" % ("全部存在" if bad == 0 else "%d 个缺失！" % bad))
