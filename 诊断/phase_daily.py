"""phase_daily.py —— 同一天内相位随 UTC 的变化（验证是不是真的会变）"""
import sys

sys.path.insert(0, r"E:\DeskTop\地球")
import ephem_hp as E  # noqa: E402

for date in ("2021-06-30", "2009-06-21", "2006-04-05"):
    print("=== %s：相位随 UTC ===" % date)
    vals = []
    for h in range(0, 24, 3):
        p = E.earth_phase(date, float(h))
        vals.append((h, p))
        print("   %2d:00  相位 %5.1f%%" % (h, p))
    lo = min(v for _, v in vals)
    hi = max(v for _, v in vals)
    print("   一天内跨度 %.1f 个点（%.1f%% ~ %.1f%%）" % (hi - lo, lo, hi))
    print()
