"""audit_deliverables.py —— 成品体检：反推每张用的是哪张底图、是否符合当前规则

解决的问题：成品目录里可能残留"规则更新之前"的旧图。只看文件在不在
判断不了它符不符合当前规则（2026-11-09 实锤：2% 那张用的是长阴影底图）。

判据：
  1. 由相位算太阳高度 → 应有档位
  2. 用像素相关性反推实际用的底图
  3. 两者必须一致，且月面亮度要落在目标曲线 ±35% 内

用法：python audit_deliverables.py [--strict]
"""
import glob
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = r"E:\DeskTop\地球"
OUT = os.path.join(HERE, "成品")
V2 = os.path.join(HERE, "v2")
BASES = os.path.join(HERE, "素材")
BOX = (300, 900, 1500, 1180)


def tier_of(h):
    if h < 0:
        return "无影"
    if h >= 45:
        return "无影"
    if h >= 22:
        return "短影"
    if h >= 5:
        return "中影"
    return "长影"


def target_l(h):
    if h <= 0:
        return 18.5 - 3.0 * min(1.0, -h / 60.0)
    return max(18.5, 86.0 * (math.sin(math.radians(max(h, 0.5)))
                             / math.sin(math.radians(60.0))) ** 0.7)


def prep(im):
    a = np.asarray(im.convert("L").crop(BOX)).astype(np.float32)
    a = a - a.mean()
    s = a.std()
    return a / s if s > 1e-6 else a


refs = {}
for n in ("无影", "短影", "中影", "长影"):
    p = os.path.join(BASES, "moon_base_%s.png" % n)
    if os.path.exists(p):
        refs[n] = prep(Image.open(p))

rows = []
for p in sorted(glob.glob(os.path.join(OUT, "*_月面_提升_1920x1280.png"))):
    d = os.path.basename(p).split("_")[0]
    j = os.path.join(V2, "_bak_uni_%s_地球相_2048.json" % d)
    if not os.path.exists(j):
        rows.append((d, None, None, None, None, "缺 json（无法判定）"))
        continue
    meta = json.load(open(j, encoding="utf-8"))
    try:
        ph = float(str(meta.get("phase", "")).replace("%", ""))
    except Exception:
        rows.append((d, None, None, None, None, "json 里没有相位"))
        continue
    k = ph / 100.0
    h = 90 - math.degrees(math.acos(max(-1, min(1, 1 - 2 * k))))
    want = tier_of(h)
    a = prep(Image.open(p))
    scores = {n: float((a * r).mean()) for n, r in refs.items()}
    got = max(scores, key=scores.get) if scores else "?"
    # 亮度校验
    A = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    t = A[761:]
    t = t[t > 1]
    med = float(np.median(t)) if t.size else 0.0
    tl = target_l(h)
    ratio = med / tl if tl > 0.1 else 1.0
    # 太暗的图（中位 < 25）纹理几乎是黑的，相关性不可信 → 只校验亮度
    dark = med < 25
    if dark:
        bad = not (0.65 <= ratio <= 1.35)
        why = None if not bad else "亮度偏离 %.0f%%" % ((ratio - 1) * 100)
        if not bad:
            got = got + "(暗·仅校验亮度)"
    else:
        bad = (got != want) or not (0.65 <= ratio <= 1.35)
        why = None if not bad else (
            "档位不符" if got != want else "亮度偏离 %.0f%%" % ((ratio - 1) * 100))
    rows.append((d, ph, want, got, med, why))

print("=" * 68)
print("%-12s %-6s %-6s %-6s %-8s %s" % ("日期", "相位", "应有", "实际", "月面中位", "结论"))
print("-" * 68)
bad_n = 0
for d, ph, want, got, med, why in rows:
    if why is None:
        print("%-12s %-6.0f %-6s %-6s %-8.0f ✓" % (d, ph, want, got, med))
    elif want is None:
        print("%-12s %-6s %-6s %-6s %-8s ⚠ %s" % (d, "-", "-", "-", "-", why))
    else:
        print("%-12s %-6.0f %-6s %-6s %-8.0f ✗ %s" % (d, ph, want, got, med, why))
        bad_n += 1
print("=" * 68)
print("成品 %d 张，不符合当前规则 %d 张" % (len(rows), bad_n))

if "--strict" in sys.argv and bad_n:
    sys.exit(1)
