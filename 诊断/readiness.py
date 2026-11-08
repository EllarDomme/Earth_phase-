"""readiness.py —— 评估"别人拿去能不能跑"的硬障碍"""
import os
import re

ROOT = r"E:\DeskTop\地球"

print("=== ① 硬编码绝对路径 ===")
hits = {}
for fn in sorted(f for f in os.listdir(ROOT) if f.endswith((".py", ".cmd"))):
    if fn.startswith("_"):
        continue
    p = os.path.join(ROOT, fn)
    try:
        t = open(p, encoding="utf-8", errors="ignore").read()
    except Exception:
        continue
    n = len(re.findall(r"[A-Za-z]:\\\\?|E:\\\\|C:\\\\Users", t))
    n2 = t.count("E:\\") + t.count("C:\\Users")
    if n2:
        hits[fn] = n2
tot = sum(hits.values())
print("  含绝对路径的文件: %d 个，共 %d 处" % (len(hits), tot))
for fn, n in sorted(hits.items(), key=lambda x: -x[1])[:8]:
    print("    %-26s %3d 处" % (fn, n))

print()
print("=== ② 第三方依赖 ===")
mods = set()
for fn in os.listdir(ROOT):
    if not fn.endswith(".py"):
        continue
    try:
        t = open(os.path.join(ROOT, fn), encoding="utf-8", errors="ignore").read()
    except Exception:
        continue
    for m in re.findall(r"^\s*(?:import|from)\s+([a-zA-Z_][\w]*)", t, re.M):
        mods.add(m)
std = {"os", "sys", "re", "json", "math", "time", "glob", "shutil", "subprocess",
       "argparse", "hashlib", "datetime", "tempfile", "io", "random", "collections",
       "itertools", "pathlib", "typing", "warnings", "textwrap", "urllib",
       "concurrent", "functools", "traceback", "base64", "shlex", "string",
       "pickle", "csv", "struct", "zipfile", "copy", "unicodedata", "bisect", "heapq"}
third = sorted(m for m in mods if m not in std and not m.startswith("_"))
print("  非标准库:", ", ".join(third) if third else "无")

print()
print("=== ③ 仓库必备文件 ===")
for f in ("README.md", "requirements.txt", "LICENSE", ".gitignore", "pyproject.toml", "setup.py"):
    print("  %-18s %s" % (f, "有" if os.path.exists(os.path.join(ROOT, f)) else "缺"))

print()
print("=== ④ 平台相关 ===")
print("  run.cmd / verify.cmd    : %s" % ("存在（仅 Windows）"
      if os.path.exists(os.path.join(ROOT, "run.cmd")) else "无"))
print("  依赖豆包 (paint.mjs)    : %s" % ("是"
      if os.path.exists(os.path.join(ROOT, "tools", "paint.mjs")) else "否"))
