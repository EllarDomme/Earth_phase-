"""compose_matrix.py —— compose_moon 参数矩阵冒烟：看有没有崩的路径"""
import os
import subprocess
import sys

HERE = r"E:\DeskTop\地球"
PY = sys.executable
SRC = os.path.join(HERE, "v2", "_bak_uni_2006-04-05_地球相_2048.png")
OUT = r"E:\DeskTop\草稿"
BASE = os.path.join(HERE, "素材", "moon_base_无影.png")

COMMON = ["--width", "1920", "--earth-pct", "0.36", "--moon-gain", "0.65"]

CASES = [
    ("自动+月夜", ["--date", "2006-04-05", "--utc", "7.75", "--sky-target", "1,1,1"]),
    ("自动+白天", ["--date", "2005-01-01", "--utc", "1.25", "--sky-target", "1,1,1"]),
    ("--base+月夜", ["--base", BASE, "--date", "2006-04-05", "--utc", "7.75",
                    "--sky-target", "1,1,1"]),
    ("--no-auto-base", ["--no-auto-base", "--date", "2006-04-05", "--utc", "7.75",
                        "--sky-target", "1,1,1"]),
    ("无日期", ["--sky-target", "1,1,1"]),
    ("有日期无 utc", ["--date", "2006-04-05", "--sky-target", "1,1,1"]),
    ("非法日期", ["--date", "不是日期", "--utc", "1.0", "--sky-target", "1,1,1"]),
    ("自定义 cx", ["--date", "2006-04-05", "--utc", "7.75", "--cx", "0.42",
                  "--sky-target", "1,1,1"]),
    ("保留星点", ["--date", "2006-04-05", "--utc", "7.75", "--keep-stars",
                 "--sky-target", "1,1,1"]),
    ("不刷天空", ["--date", "2006-04-05", "--utc", "7.75", "--sky-target", "none"]),
    ("月面增益0", ["--date", "2006-04-05", "--utc", "7.75", "--moon-gain", "0",
                  "--sky-target", "1,1,1"]),
]

print("%-14s %-6s %-10s %s" % ("场景", "退出码", "产物", "关键输出"))
bad = 0
for tag, args in CASES:
    dst = os.path.join(OUT, "_mx_%s.png" % tag)
    r = subprocess.run([PY, os.path.join(HERE, "compose_moon.py"), SRC, dst] + COMMON + args,
                       capture_output=True, text=True, timeout=600)
    ok = (r.returncode == 0 and os.path.exists(dst))
    key = [l.strip() for l in (r.stdout or "").splitlines()
           if l.startswith(("月面：", "月面质感", "底图选择"))]
    err = (r.stderr or "").strip().splitlines()
    print("%-14s %-6d %-10s %s" % (tag, r.returncode, "有" if os.path.exists(dst) else "无",
                                   (key[0][:46] if key else (err[-1][:46] if err else "—"))))
    if not ok:
        bad += 1
        if err:
            print(" " * 22 + "stderr: " + err[-1][:70])
print()
print("失败 %d / %d" % (bad, len(CASES)))
