"""stage_boost.py —— 「先提清晰度、再拼图」这一阶段的实现（2026-11-09）

背景：原来的顺序是 compose(海报) → boost(海报)，豆包会看到并重绘月面。
      改成 boost(圆盘) → compose(海报)，月面就永远不经过豆包。

产出仍然是两张（和原来一样）：
  <dst>_月面_1920x1280.png        ← 用未提升的圆盘拼
  <dst>_月面_提升_1920x1280.png   ← 用提升后的圆盘拼
两张除了地球圆盘内部，其余像素完全相同（月面来自同一底图、同一次合成）。

为什么保留两张：提升前后圆盘细节本就有差异，两张并列是历史交付习惯。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DISC_GEOM = "0.5,0.5,0.5"       # 圆盘图：居中铺满


def _default_boost(disc, out, extra):
    cmd = [sys.executable, os.path.join(HERE, "doubao_boost.py"),
           disc, "--out", out, "--disc-geom", DISC_GEOM] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _default_compose(disc, out, width, extra):
    cmd = [sys.executable, os.path.join(HERE, "compose_moon.py"),
           disc, out, "--width", str(width)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def boost_then_compose(disc_path, out_dir, date_w, width=1920,
                       compose_extra=None, boost_extra=None,
                       log=print, boost_runner=None, compose_runner=None):
    """先提清晰度（只碰圆盘），再拼两张海报。

    返回 (path_normal, path_boost)。任一步失败返回 (None, None)，不抛异常。
    """
    compose_extra = list(compose_extra or [])
    boost_extra = list(boost_extra or [])
    boost_runner = boost_runner or _default_boost
    compose_runner = compose_runner or _default_compose

    os.makedirs(out_dir, exist_ok=True)
    dst_n = os.path.join(out_dir, "%s_月面_%dx1280.png" % (date_w, width))
    dst_b = os.path.join(out_dir, "%s_月面_提升_%dx1280.png" % (date_w, width))

    # ① 豆包只处理圆盘（居中几何，绝不含月面）
    # 中间产物放 v2，不要污染 成品/（成品目录只该有交付物）
    _v2 = os.path.join(HERE, "v2")
    os.makedirs(_v2, exist_ok=True)
    boosted = os.path.join(_v2, "_boosted_disc_%s.png" % date_w)
    log("[提升] 先对圆盘提清晰度（不含月面）…")
    rc, out = boost_runner(disc_path, boosted, boost_extra)
    for ln in out.splitlines():
        if ln.startswith(("[提升]", "去水印", "地球亮度")):
            log("   " + ln)
    if rc != 0 or not os.path.exists(boosted):
        log("   [提升] 失败（rc=%s），跳过提升版" % rc)
        boosted = disc_path

    # ② 用未提升的圆盘拼第一张
    rc1, out1 = compose_runner(disc_path, dst_n, width, compose_extra)
    if rc1 != 0:
        log("   [月面] 失败：%s" % out1.strip()[-160:])
        return None, None
    # ③ 用提升后的圆盘拼第二张
    rc2, out2 = compose_runner(boosted, dst_b, width, compose_extra)
    if rc2 != 0:
        log("   [月面·提升] 失败：%s" % out2.strip()[-160:])
        return dst_n, None
    return dst_n, dst_b
