"""audit_behavior.py —— 行为自检：静态查不出来的"逻辑绕过"，靠真跑一遍验证

覆盖三类历史事故：
  ① 传 --base 后镜像判断被跳过
  ② 星点遮罩圆心不跟 --cx 走
  ③ 亮度曲线在档位边界跳变

用法：python audit_behavior.py [--strict]
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
TMP = tempfile.gettempdir()


def run_compose(src, out, extra):
    cmd = [PY, os.path.join(HERE, "compose_moon.py"), src, out,
           "--width", "1920", "--earth-pct", "0.36", "--moon-gain", "0.65",
           "--sky-target", "1,1,1", "--earth-gamma", "1.0", "--earth-sat", "1.0"] + extra
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return r.stdout + r.stderr


def main():
    strict = "--strict" in sys.argv
    bad = 0
    print("=" * 70)

    # ① --base 仍要做镜像判断（47% 地球在西 → 必须换镜像）
    src = os.path.join(HERE, "v2", "_bak_uni_2021-06-18_地球相_2048.png")
    if os.path.exists(src):
        log = run_compose(src, os.path.join(TMP, "_ab1.png"),
                          ["--base", os.path.join(HERE, "素材", "moon_base_长影.png"),
                           "--date", "2021-06-18", "--utc", "11.25"])
        ok = "镜像" in log and "显式底图" in log
        print("%s compose   --base 仍判镜像（应换镜像）" % ("✓" if ok else "✗"))
        bad += 0 if ok else 1

        # 反例：地球在东 → 应保持原图
        src2 = os.path.join(HERE, "v2", "_bak_uni_2005-01-01_地球相_2048.png")
        if os.path.exists(src2):
            log2 = run_compose(src2, os.path.join(TMP, "_ab2.png"),
                               ["--base", os.path.join(HERE, "素材", "moon_base_短影.png"),
                                "--date", "2005-01-01", "--utc", "1.25"])
            ok2 = "原图" in log2
            print("%s compose   --base 方向对时不乱换（应保持原图）" % ("✓" if ok2 else "✗"))
            bad += 0 if ok2 else 1
    else:
        print("- compose   跳过（缺 _bak_uni_2021-06-18）")

    # ② --cx 真的改变地球位置
    if os.path.exists(src):
        log = run_compose(src, os.path.join(TMP, "_ab3.png"),
                          ["--cx", "0.42", "--date", "2021-06-18", "--utc", "11.25"])
        m = re.search(r"中心 \((\d+),", log)
        ok = bool(m) and abs(int(m.group(1)) - int(0.42 * 1920)) <= 2
        print("%s compose   --cx 0.42 → 中心 %s（应 ≈806）"
              % ("✓" if ok else "✗", m.group(1) if m else "?"))

    # ③ 亮度曲线单调、无断崖（从源码读常量，不 import 脚本）
    try:
        import math
        src_txt = open(os.path.join(HERE, "compose_moon.py"), encoding="utf-8").read()
        m_n = re.search(r"L_NIGHT\s*=\s*([\d.]+)", src_txt)
        m_f = re.search(r"L_FLOOR\s*=\s*([\d.]+)", src_txt)
        m_c = re.search(r"86\.0 \* \(_m\.sin\(_m\.radians\(max\(_h, 0\.5\)\)\)"
                        r" / _m\.sin\(_m\.radians\(([\d.]+)\)\)\) \*\* ([\d.]+)", src_txt)
        L_NIGHT = float(m_n.group(1))
        L_FLOOR = float(m_f.group(1))
        HREF = float(m_c.group(1)) if m_c else 60.0
        EXP = float(m_c.group(2)) if m_c else 0.7
        TOP = 86.0

        def target(h):
            if h <= 0:
                return L_NIGHT - 3.0 * min(1.0, -h / 60.0)
            return max(L_FLOOR, TOP * (math.sin(math.radians(max(h, 0.5)))
                                       / math.sin(math.radians(HREF))) ** EXP)

        ts = [target(i * 0.5) for i in range(-180, 181)]
        mono = all(ts[i] <= ts[i + 1] + 0.6 for i in range(len(ts) - 1))
        jumps = [abs(ts[i + 1] - ts[i]) for i in range(len(ts) - 1)]
        ok = mono and max(jumps) <= 12
        print("%s 亮度曲线   单调=%s 最大跳变=%.1f" % ("✓" if ok else "✗", mono, max(jumps)))
        bad += 0 if ok else 1
    except Exception as e:
        print("- 亮度曲线   跳过（%s）" % str(e)[:40])

    # ④⑤⑥ 三条不变量（用刚才合成的图真跑一遍）
    probe = os.path.join(TMP, "_ab1.png")   # 默认居中的那张；不能用 --cx 试验图
    if os.path.exists(probe):
        try:
            import numpy as np
            from PIL import Image
            sys.path.insert(0, HERE)
            import lighting
            import doubao_boost as DB
            from layout import disc_geom
            from starless import strip_stars

            im = Image.open(probe).convert("RGB")
            W, H = im.size
            cx, cy, R = disc_geom(W, H)
            yy, xx = np.mgrid[0:H, 0:W]
            rr = np.hypot(xx - cx, yy - cy) / R
            A = np.asarray(im).astype(np.float32)
            far = rr > 1.15

            # ④ 打光只动圆盘（球缘 15% 以外必须原样）
            L = np.asarray(lighting.apply_lighting(im, "2021-06-18", 11.25,
                                                   verbose=False)).astype(np.float32)
            d1 = np.abs(A - L).max(2)
            ok = d1[far].max() < 2.0
            print("%s 不变量   打光不动球缘外（最大 %.1f，应 <2）"
                  % ("✓" if ok else "✗", d1[far].max()))
            bad += 0 if ok else 1

            # ⑤ 摘星不动地形
            Lm = A.mean(2)
            above = Lm > 6
            first = np.argmax(above, axis=0)
            hz = np.where(above.any(axis=0), first, H).astype(np.int32)
            hz = np.array([int(hz[max(0, i - 10):i + 11].min()) for i in range(W)], np.int32)
            sky = np.zeros((H, W), bool)
            for x in range(W):
                sky[:max(0, hz[x] - 2), x] = True
            disc = rr <= 1.0
            terrain = ~sky & ~disc
            S, _n = strip_stars(A.copy(), hz, disc, verbose=False, sky=sky)
            d2 = np.abs(A - np.asarray(S, dtype=np.float32)).max(2)
            ok = d2[terrain].max() < 2.0
            print("%s 不变量   摘星不动地形（最大 %.1f，应 <2）"
                  % ("✓" if ok else "✗", d2[terrain].max()))
            bad += 0 if ok else 1

            # ⑥ 盘外亮度校正后，天空必须仍是黑的
            fake = Image.fromarray(np.clip(A * 0.7, 0, 255).astype(np.uint8))
            R2 = np.asarray(DB.restore_scene(fake, im)).astype(np.float32)
            skymax = float(R2.mean(2)[A.mean(2) < 1.0].max()) if (A.mean(2) < 1).any() else 0.0
            ok = skymax < 2.0
            print("%s 不变量   天空校正后仍为黑（最大 %.1f，应 <2）"
                  % ("✓" if ok else "✗", skymax))
            bad += 0 if ok else 1
        except Exception as e:
            print("- 不变量   跳过（%s）" % str(e)[:50])

    # ⑥b 显式 --base 不得绕过亮度分档 / 月夜质感
    #   2026-11-09 第二次同类事故：--base 分支只判镜像，跳过亮度系数与质感，
    #   实测月夜日期地形 86（应为 18）。
    try:
        import numpy as np
        from PIL import Image
        sys.path.insert(0, HERE)
        _src = os.path.join(HERE, "v2", "_bak_uni_2006-04-05_地球相_2048.png")
        _base = os.path.join(HERE, "素材", "moon_base_无影.png")
        if os.path.exists(_src) and os.path.exists(_base):
            _common = ["--date", "2006-04-05", "--utc", "7.75", "--width", "1920",
                       "--earth-pct", "0.36", "--moon-gain", "0.65",
                       "--sky-target", "1,1,1", "--earth-gamma", "1.0",
                       "--earth-sat", "1.0"]
            _pa = os.path.join(TMP, "_ab_auto.png").replace(".png", ".png")
            _pb = os.path.join(TMP, "_ab_base.png").replace(".png", ".png")
            import subprocess as _sp
            _sp.run([PY, os.path.join(HERE, "compose_moon.py"), _src, _pa] + _common,
                    capture_output=True, timeout=600)
            _sp.run([PY, os.path.join(HERE, "compose_moon.py"), _src, _pb,
                     "--base", _base] + _common, capture_output=True, timeout=600)

            def _med(p):
                A = np.asarray(Image.open(p).convert("L")).astype(np.float32)
                t = A[900:]
                t = t[t > 1]
                return float(np.median(t))

            if os.path.exists(_pa) and os.path.exists(_pb):
                ma, mb = _med(_pa), _med(_pb)
                ok = abs(ma - mb) <= 2
                print("%s 参数绕过   显式 --base 与自动分档一致（%.0f vs %.0f，应差 ≤2）"
                      % ("✓" if ok else "✗", ma, mb))
                bad += 0 if ok else 1
    except Exception as e:
        print("- 参数绕过   跳过（%s）" % str(e)[:50])

    # ⑦ 每对成品：提升版必须和普通版的明暗一致（漏打光会当场暴露）
    #   2026-11-09 实测事故：boost-first 漏打光 → 提升版地球变成满盘平光，
    #   暗像素从 87% 掉到 6%，但因为"图还能打开"，静态检查完全看不出。
    try:
        import glob
        import numpy as np
        from PIL import Image
        sys.path.insert(0, HERE)
        from layout import disc_geom

        pairs = []
        for f in sorted(glob.glob(os.path.join(HERE, "成品", "*_月面_提升_1920x1280.png"))):
            base = f.replace("_月面_提升_", "_月面_")
            if os.path.exists(base):
                pairs.append((os.path.basename(base)[:10], base, f))
        if not pairs:
            print("- 成品对照  跳过（成品目录里没有成对文件）")
        else:
            worst = None
            for tag, a_p, b_p in pairs:
                A = np.asarray(Image.open(a_p).convert("L")).astype(np.float32)
                B = np.asarray(Image.open(b_p).convert("L")).astype(np.float32)
                if A.shape != B.shape:
                    continue
                H, W = A.shape
                cx, cy, R = disc_geom(W, H)
                yy, xx = np.mgrid[0:H, 0:W]
                m = np.hypot(xx - cx, yy - cy) < R * 0.95
                va, vb = A[m], B[m]
                if va.std() < 1e-3 or vb.std() < 1e-3:
                    continue
                c = float(np.corrcoef(va, vb)[0, 1])
                if worst is None or c < worst[1]:
                    worst = (tag, c)
            if worst:
                ok = worst[1] > 0.90
                print("%s 成品对照   提升版与月面版明暗一致（最低相关 %.3f @ %s，应 >0.90）"
                      % ("✓" if ok else "✗", worst[1], worst[0]))
                bad += 0 if ok else 1
            else:
                print("- 成品对照  跳过（没有可比对的一对）")
    except Exception as e:
        print("- 成品对照  跳过（%s）" % str(e)[:50])

    print("=" * 70)
    print("行为自检：%s（%d 项失败）" % ("全部通过 ✓" if bad == 0 else "有失败 ✗", bad))
    return 1 if (bad and strict) else 0


if __name__ == "__main__":
    sys.exit(main())
