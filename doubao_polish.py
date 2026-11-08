"""doubao_polish.py —— 豆包二次去痕迹（流水线第 ⑥ 步）

流程（2026-11-03 定）：
    地相图(2048) ──① 交豆包(标准提示词)──> 去水印 ──② 再交豆包(同一提示词)──> 去水印 ──> 放大回 2048

规范见《技术手册_地相图》第十四章：
  · 输入必须是**地相图**（球体），不是 2:1 纹理
  · 提示词固定（见 PROMPT）
  · 验收：相关 > 0.95、亮度变化 ±10% 内

用法：
    python doubao_polish.py <地相图.png> [--out 目录] [--size 2048] [--passes 2]

输出：
    <名>_polished.png      成品（无水印，目标尺寸）
    <名>_polished.json     验收数据（每遍的相关/亮度/裁剪）
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
# 2026-11-06：paint.mjs 已复制进项目 tools\，不再依赖 D 盘
PAINT = os.path.join(HERE, "tools", "paint.mjs")
if not os.path.exists(PAINT):
    PAINT = r"D:\deepseek_豆包_生图\dsh-doubao-painter\tools\paint.mjs"
import config as _cfg                          # 路径统一由 config.py 管理
DOUBAO_EXE = _cfg.DOUBAO_EXE
NODE = _cfg.NODE

# ── 第十四章的标准提示词（核心段一字不改）──────────────────────────
PROMPT = """只清除笔直模糊条带和线性遮挡，黑线两边的云层有不自然的，就在消除黑线以后将不自然或者断层的云层绘成自然合理的云层，其他不改真实云系、海洋纹理、陆地轮廓、地球弧面和原始光照；避免把自然云带误删，不产生新的方向伪影。图片所有像素要跟原图像素整体保持一致，不能有重绘感"""

# 旧版（2026-11-04 实测效果最好，保留以便 A/B）
PROMPT_R2_OLD = "将图中竖直白色或浅棕褐色模糊条带、弯曲模糊白色或浅棕色条带给清除，其他都不变"

# 新版（2026-11-06 用户提供，豆包自己优化的提示词）
PROMPT_R2 = ("修复地球卫星图，清除棕黄色、白色薄雾扫描条带伪影，消除海面突兀过亮光斑；"
             "保留原有陆地、自然云、冰盖完全不变，修复后的海面亮度、色彩和周围海面自然融合，"
             "过渡平滑，保持原图细节清晰度")


def build_prompt(image_path, view=None):
    """核心段一字不改；若检测到颜色异常，就在前面加一句"具体在哪、是什么"。"""
    import json as _json
    import subprocess as _sp
    base = os.path.splitext(image_path)[0]
    note = ""
    try:
        cmd = [sys.executable, os.path.join(HERE, "detect_fill_artifacts.py"),
               image_path, "--min-area", "1200"]
        if view:
            cmd += ["--view", view]
        _sp.run(cmd, capture_output=True, timeout=900)
        cand = base + "_fillartifacts.json"
        if os.path.exists(cand):
            j = _json.load(open(cand, encoding="utf-8"))
            cl = j.get("classes", {}).get("S1_暗红填充", {}).get("clusters", [])
            if cl:
                from gazetteer import describe_region
                where = describe_region(cl[0]["lat_range"], cl[0]["lon_range"])
                km2 = cl[0]["km2"] / 1e4
                note = ("【需要特别处理的地方】%s一带（约 %.1f~%.1f°N、%.1f~%.1f°E，"
                        "面积约 %.0f 万平方公里）有一大片暗褐色区域，"
                        "是卫星数据缺失后被填充的痕迹，请按周围真实的沙漠、山地和海洋，"
                        "把它补成颜色和纹理都自然的区域。\n\n"
                        % (where, cl[0]["lat_range"][0], cl[0]["lat_range"][1],
                           cl[0]["lon_range"][0], cl[0]["lon_range"][1], km2))
                print("[提示词] 已加入异常位置：", where)
    except Exception as e:
        print("[提示词] 异常检测跳过：", e)
    return note + PROMPT


# 水印位置（相对尺寸，实测于 1536×1536）
WM_BOX = (0.8177, 0.9857, 0.9390, 0.9820)   # x0, x1, y0, y1


_LAST_CONV = {"title": "", "url": ""}


def _run_quote(prompt, out_dir):
    """第二轮：用「引用」而不是上传（doubao_quote.mjs 会校验引用图 == 最新生成图）"""
    import json as _j
    import subprocess as _sp
    node = NODE
    script = os.path.join(HERE, "doubao_quote.mjs")
    p = _sp.run([node, script, "--prompt", prompt, "--out", out_dir],
                capture_output=True, timeout=900)
    out = p.stdout.decode("utf-8", "ignore")
    for ln in out.splitlines():
        if ln.startswith(("[引用]", "[发送]", "[下载]")):
            print("   " + ln)
    i = out.find('{"ok"')
    if i < 0:
        raise RuntimeError("引用失败：\n" + out[-400:] + "\n" + p.stderr.decode("utf-8", "ignore")[-300:])
    res = _j.loads(out[i:].splitlines()[0])
    if not res.get("ok"):
        raise RuntimeError("引用失败：" + _j.dumps(res, ensure_ascii=False)[:300])
    print("   [引用] 校验通过：引用图 = 最新图 = %s" % res.get("quotedKey"))
    return res["files"], res


def _run_paint(image_path, out_dir, timeout_ms=600000, new_chat=True,
               prompt=None, view=None):
    """调 paint.mjs，返回生成的文件路径列表。"""
    req = {"prompt": prompt if prompt is not None else build_prompt(image_path, view=view),
           "refImages": [image_path],
           "outDir": out_dir, "newChat": new_chat, "timeoutMs": timeout_ms}
    # ★ 改用 doubao_run.mjs：它会先确保"对话"模式（图像生成面板没有上传入口）
    req_file = os.path.join(out_dir, "_req.json")
    with open(req_file, "w", encoding="utf-8") as f:
        json.dump(req, f, ensure_ascii=False)
    p = subprocess.run(
        [NODE, os.path.join(HERE, "doubao_run.mjs"), req_file],
        capture_output=True, timeout=timeout_ms / 1000 + 180)
    out = p.stdout.decode("utf-8", "ignore").strip()
    attach = None
    for ln in out.splitlines():
        if ln.startswith("[页面]") or ln.startswith("[上传]"):
            print("   " + ln)
        if ln.startswith("ATTACH_SIZE="):
            attach = ln.split("=", 1)[1].strip()
        # ★ 2026-11-08 修：这两行原来被缩进到了下面的 else 里，导致标题永远读不到，
        #   于是"每轮结束删对话"从来没生效（侧栏堆了 147 条）。
        if ln.startswith("CONV_TITLE="):
            _LAST_CONV["title"] = ln.split("=", 1)[1].strip()
            print("   [对话] " + _LAST_CONV["title"])
        if ln.startswith("CONV_URL="):
            _LAST_CONV["url"] = ln.split("=", 1)[1].strip()

    # ★ 核对"发出去的附件尺寸"是否等于本地这张图
    try:
        from PIL import Image as _Im
        want = "%dx%d" % _Im.open(image_path).size
    except Exception:
        want = None
    if attach and attach not in ("none", "") and want:
        got = attach.split(",")[0]
        if got != want:
            raise RuntimeError(
                "发错图：本地 %s，豆包页面上的附件是 %s（%s）" % (want, got, image_path))
        print("   [附件核对] 本地 %s = 页面 %s ✓" % (want, got))
    else:
        # 读不到就只告警，不阻断（页面结构变化时不能把整条流水线卡死）
        print("   [附件核对] 页面尺寸读不到，跳过核对（本地 %s）" % want)
    start = out.find("RESULT_JSON=")
    if start < 0:
        raise RuntimeError("doubao_run 无结果：" + (out or p.stderr.decode("utf-8", "ignore"))[-400:])
    data = json.loads(out[start + len("RESULT_JSON="):].splitlines()[0])
    if not data.get("ok"):
        raise RuntimeError("豆包失败：" + str(data.get("error"))[:300])
    return data["files"]


def _paint_with_retry(stage, tmp, prompt, view=None, tries=4):
    """豆包出图失败时：删掉这个对话 → 开新对话 → 再试。最多 tries 次。

    用户要求（2026-11-08）：豆包偶尔"上传了但没生成"，删对话重开往往就好了。
    """
    last = None
    for k in range(tries):
        try:
            return _run_paint(stage, tmp, new_chat=True, prompt=prompt, view=view)
        except Exception as e:
            last = e
            print("   [重试] 第 %d/%d 次失败：%s" % (k + 1, tries, str(e)[:160]))
            _t = _LAST_CONV.get("title")
            if _t:
                try:
                    subprocess.run([NODE, os.path.join(HERE, "delete_conv.mjs"),
                                    _t.replace(" - 豆包", "")],
                                   capture_output=True, text=True, timeout=120)
                    print("   [重试] 已删除该对话，准备开新的")
                    _LAST_CONV["title"] = None
                except Exception as _e2:
                    print("   [重试] 删对话失败：", str(_e2)[:120])
            __import__("time").sleep(3)
    raise last


def _shadow_gain(img: Image.Image, lift: float, mask_path=None):
    """暗部提亮增益图

    · 只在"暗部"提（亮度越低提得越多，knee=90 以上不动）
    · 若给了 mask_path（补洞掩膜），只在**空洞附近**提亮，避免整图变样
    """
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    L = a.mean(axis=2)
    knee = 90.0
    base = np.clip((knee - L) / knee, 0, 1)
    if mask_path and os.path.exists(mask_path):
        m = Image.open(mask_path).convert("L")
        if m.size != img.size:
            m = m.resize(img.size, Image.LANCZOS)
        # 膨胀一圈，覆盖空洞边缘
        m = m.filter(ImageFilter.MaxFilter(25)).filter(ImageFilter.GaussianBlur(8))
        mw = (np.asarray(m).astype(np.float32) / 255.0)
        base = base * mw
    g = 1.0 + max(0.0, lift - 1.0) * base
    return g.astype(np.float32)


def _shadow_lift(img: Image.Image, lift: float, mask_path=None):
    """送图前：暗部提亮，让黑线在暗处也看得见"""
    if lift <= 1.0:
        return img
    g = _shadow_gain(img, lift, mask_path)
    a = np.asarray(img.convert("RGB")).astype(np.float32) * g[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def _shadow_unlift(img: Image.Image, ref: Image.Image, lift: float, mask_path=None):
    """拿到结果后：按同一增益压回（增益图来自原图，保证亮度还原）"""
    if lift <= 1.0:
        return img
    g = _shadow_gain(ref, lift, mask_path)
    gi = Image.fromarray(np.clip(g / max(lift, 1e-6) * 255, 0, 255).astype(np.uint8))
    gi = gi.resize(img.size, Image.LANCZOS)
    gg = np.asarray(gi).astype(np.float32) / 255.0 * max(lift, 1e-6)
    gg = np.clip(gg, 1e-3, 10)
    a = np.asarray(img.convert("RGB")).astype(np.float32) / gg[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def _remove_watermark(img: Image.Image, verbose=True) -> Image.Image:
    """右下角水印：只修补文字窄条，不动球体边缘。"""
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    H, W, _ = a.shape
    x0, x1 = int(W * WM_BOX[0]), int(W * WM_BOX[1])
    y0, y1 = int(H * WM_BOX[2]), int(H * WM_BOX[3])
    mask = np.zeros((H, W), bool)
    mask[y0:y1, x0:x1] = (a[y0:y1, x0:x1].mean(axis=2) > 22)
    mask = np.asarray(Image.fromarray((mask * 255).astype(np.uint8))
                      .filter(ImageFilter.MaxFilter(7))) > 127
    n = int(mask.sum())
    if n > 200:
        ref = a[max(0, y0 - 25):max(1, y0 - 5), x0:x1].reshape(-1, 3)
        mu = ref.mean(axis=0)
        sd = np.maximum(ref.std(axis=0), 0.6)
        rng = np.random.default_rng(41)
        a[mask] = np.clip(mu[None, :] + rng.normal(0, 1, (n, 3)) * sd[None, :], 0, 255)
    if verbose:
        print("   [水印] 修补 %d px" % n)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def _match_brightness(img, ref):
    """把整体亮度拉回参考图（豆包每遍都会轻微提亮，两遍会累加）。"""
    A = np.asarray(img.convert("RGB")).astype(np.float32)
    B = np.asarray(ref.convert("RGB").resize(img.size, Image.LANCZOS)).astype(np.float32)
    disc = B.mean(axis=2) > 3
    ma = A.mean(axis=2)[disc].mean()
    mb = B.mean(axis=2)[disc].mean()
    if ma < 1:
        return img
    g = float(mb / ma)
    return Image.fromarray(np.clip(A * g, 0, 255).astype(np.uint8))


def _keep_shadow(got, ref):
    """暗面用原图（豆包会把暗部抬亮，违反真相位）。亮面用豆包的。"""
    A = np.asarray(got.convert("RGB").resize(ref.size, Image.LANCZOS)).astype(np.float32)
    B = np.asarray(ref.convert("RGB")).astype(np.float32)
    lb = B.mean(axis=2)
    w = np.clip((lb - 2.0) / 10.0, 0, 1)[..., None]      # <2 全用原图，>12 全用豆包
    out = B * (1 - w) + A * w
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def _metrics(img: Image.Image, ref: Image.Image):
    A = np.asarray(img.resize(ref.size, Image.LANCZOS)).astype(np.float32)
    B = np.asarray(ref).astype(np.float32)
    disc = B.mean(axis=2) > 3
    la, lb = A.mean(axis=2), B.mean(axis=2)
    return dict(
        corr=round(float(np.corrcoef(la[disc], lb[disc])[0, 1]), 4),
        bright_ref=round(float(lb[disc].mean()), 2),
        bright_out=round(float(la[disc].mean()), 2),
        bright_delta_pct=round(100 * (la[disc].mean() / max(lb[disc].mean(), 1e-6) - 1), 1),
        max_ref=int(B.max()), max_out=int(A.max()),
    )



def _latest_station(date_tag, station, since=None):
    """从中转站取该日期最新的一张（按文件名里的时分秒数字）。

    文件名格式：<YYYYmmddHHMMSS>_<日期>_<用途>.png

    ★ since：只认"本次运行开始之后"写出的文件。
      不加这个限定会把以前跑留下的（可能更差的）文件当成最新选走——
      实测就因此挑了带黑线的那张去拼图。
    """
    import glob as _g
    import re as _re

    def _stamp_of(p):
        m = _re.match(r"(\d{14})_", os.path.basename(p))
        return m.group(1) if m else ""

    cands = _g.glob(os.path.join(station, "*_%s_*.png" % date_tag))
    if since:
        cands = [p for p in cands if _stamp_of(p) >= str(since)]
    if not cands:
        return None
    return max(cands, key=lambda p: (_stamp_of(p), os.path.getmtime(p)))


def _looks_like(path, ref_path, tol=0.995, diff=1.5):
    """判断 path 是不是"ref_path 本身"（用于识别"下载原图抓成了输入图"）。

    做法：缩到 64x64 灰度，算相关系数和平均绝对差。
    """
    try:
        a = np.asarray(Image.open(path).convert("L").resize((64, 64)), dtype=np.float32)
        b = np.asarray(Image.open(ref_path).convert("L").resize((64, 64)), dtype=np.float32)
        a = a - a.mean()
        b = b - b.mean()
        den = (np.sqrt((a * a).sum()) * np.sqrt((b * b).sum())) + 1e-9
        corr = float((a * b).sum() / den)
        mad = float(np.abs(a - b).mean())
        return corr > tol and mad < diff
    except Exception:
        return False


def _download_official(out_dir, sub="dl", retries=3):
    """点豆包图片上「引用键右边的下载原图」，返回下载到的文件路径（失败返回 None）。

    ★ 2026-11-08：加最多 3 次重试。实测第二轮偶尔"点击了但文件没落盘"，
      以前会静默退回上一轮的结果，导致最终成品用的是错的那张。
    """
    for _attempt in range(retries):
        _got = _download_official_once(out_dir, sub if _attempt == 0 else "%s_r%d" % (sub, _attempt))
        if _got:
            return _got
        if _attempt < retries - 1:
            import time as _tw
            print("   [下载原图] 第 %d 次没拿到，20 秒后重试" % (_attempt + 1))
            _tw.sleep(20)
    return None


def _download_official_once(out_dir, sub="dl"):
    """单次尝试"""
    import json as _json
    import shutil as _shdl
    import time as _tdl
    # ★ 每次下载用全新目录，并记录起始时间：
    #   否则目录里残留的旧文件会被当成"这次下载的结果"返回，
    #   第二轮就可能拿到第一轮的文件（实测会导致最终成品用错图）。
    _t0 = _tdl.time()
    dl_dir = os.path.join(out_dir, "_official_dl_%s_%d" % (sub, int(_t0)))
    _shdl.rmtree(dl_dir, ignore_errors=True)
    try:
        r = subprocess.run([NODE, os.path.join(HERE, "doubao_download.mjs"),
                            "--out", dl_dir, "--wait", "60000"],
                           capture_output=True, text=True, timeout=300)
        for ln in (r.stdout or "").splitlines():
            if ln.startswith("[下载原图]"):
                print("   " + ln[:150])
        for ln in (r.stdout or "").splitlines():
            if ln.startswith('{"ok"'):
                j = _json.loads(ln)
                if j.get("ok") and os.path.exists(j["file"]):
                    # 必须是本次新写出来的文件
                    if os.path.getmtime(j["file"]) >= _t0 - 2:
                        return j["file"]
                    print("   [下载原图] 忽略旧文件：%s" % os.path.basename(j["file"]))
    except Exception as e:
        print("   [下载原图] 失败：", e)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", default=None)
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--shadow-mask", default=None,
                    help="提亮范围限定在这个掩膜（补洞掩膜）附近；不给则全图暗部都提")
    ap.add_argument("--shadow-lift", type=float, default=2.8,
                    help="送图前把暗部提亮的倍数上限（0=不提亮）；拿到结果后按同一增益压回")
    ap.add_argument("--view", default=None,
                    help="球面视点 lat,lon（如 23.41,118.99）；否则自动从 qc_*.json 读")
    ap.add_argument("--passes", type=int, default=2,
                    help="固定 2 轮，不许改（手册规定）")
    a = ap.parse_args()

    src_path = os.path.abspath(a.image)
    out_dir = a.out or os.path.dirname(src_path)
    base = os.path.splitext(os.path.basename(src_path))[0]
    # 先确保豆包以调试模式在跑（否则 paint.mjs 连不上）
    from doubao_ensure import ensure as _ensure
    if not _ensure():
        print("[中止] 豆包 CDP 不可用，无法处理")
        return 2

    # 没给 --view 时，从同名 qc_*.json 里取视点（避免把球面当平面换算经纬度）
    if not a.view:
        import glob as _g
        import json as _j
        cand = _g.glob(os.path.join(os.path.dirname(src_path), "qc_*.json"))
        dates = [os.path.basename(x)[3:-5] for x in cand]
        hit = [d for d in dates if d in base]
        if hit:
            try:
                q = _j.load(open(os.path.join(os.path.dirname(src_path), "qc_%s.json" % hit[0]),
                                 encoding="utf-8"))
                if q.get("view_lat") is not None and q.get("view_lon") is not None:
                    a.view = "%.2f,%.2f" % (q["view_lat"], q["view_lon"])
            except Exception:
                pass
    if a.view:
        print("[视点] %s（用于把异常区域换算成正确地名）" % a.view)

    # 没给 --shadow-mask 时，自动找同目录的补洞掩膜（hole_<日期>.png）
    if a.shadow_lift > 1.0 and not a.shadow_mask:
        _stem = base.replace("_final", "").replace("_polished", "")
        for _cand in (f"hole_{_stem}.png", f"{_stem}_hole.png"):
            _p = os.path.join(os.path.dirname(src_path), _cand)
            if os.path.exists(_p):
                a.shadow_mask = _p
                print("[提亮] 自动找到补洞掩膜:", _cand)
                break
        if not a.shadow_mask:
            print("[提亮] 没找到补洞掩膜，将对全图暗部提亮")

    src = Image.open(src_path).convert("RGB")
    ref = src

    passes = 2                      # ★ 手册规定：严格两轮，不多不少
    report = {"source": src_path, "prompt": PROMPT, "passes": []}
    cur = src
    # ── 自检：两轮各开新对话（2026-11-06 改）──
    import inspect as _ins
    _src = _ins.getsource(_run_paint)
    print("[自检] 两轮对话模式：两轮各开一个新对话；第一轮结束即删")

    tmp = os.path.join(out_dir, "_polish_tmp")
    os.makedirs(tmp, exist_ok=True)

    # ★ 中间成品命名：年月日时分秒_【日期】_最终成品.png（用户 2026-11-06 要求）
    #   目的：第一轮下来的图有个确定的、不重名的文件名，
    #        第二轮上传的就是这个文件，谁也不会拿错。
    import re as _re
    import time as _time
    _m = _re.search(r"\d{4}-\d{2}-\d{2}", os.path.basename(src_path))
    _date_tag = _m.group(0) if _m else "unknown"
    _stamp = _time.strftime("%Y%m%d%H%M%S")
    # 中转站：放在项目内（地球\中转站），方便随项目一起备份。
    # 2026-11-07 从 E:\DeskTop\地相图中转站 搬进来——
    # 它是"第一轮成品 → 第二轮上传"的凭据，属于项目资产，不该散在外面。
    # 需要换位置时设环境变量 DP_STATION 即可。
    STATION = os.environ.get("DP_STATION") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "中转站")
    try:
        os.makedirs(STATION, exist_ok=True)
    except Exception:
        STATION = out_dir
    round1_final = os.path.join(STATION, "%s_%s_最终成品.png" % (_stamp, _date_tag))
    print("[中转站] 目录：%s" % STATION)
    print("[命名] 第一轮成品名：%s" % os.path.basename(round1_final))

    try:
        for i in range(1, passes + 1):
            print("[豆包第 %d 遍] 发送 %s" % (i, cur.size))
            stage = os.path.join(tmp, "in_%d.png" % i)
            if i == 2 and os.path.exists(round1_final):
                # ★ 第二轮必须上传"中转站里第一轮那个成品文件"
                #   直接复制字节（不重新保存），保证上传的就是那个文件本身
                import shutil as _sh3
                _sh3.copy2(round1_final, stage)
                to_send = Image.open(stage).convert("RGB")
                import hashlib as _h2
                _m_st = _h2.md5(open(round1_final, "rb").read()).hexdigest()[:12]
                _m_ss = _h2.md5(open(stage, "rb").read()).hexdigest()[:12]
                print("   [第二轮输入] 取自中转站：%s" % os.path.basename(round1_final))
                print("   [第二轮输入] 中转站 md5=%s   实际发送 md5=%s   %s"
                      % (_m_st, _m_ss, "一致" if _m_st == _m_ss else "不一致！"))
            else:
                to_send = _shadow_lift(cur, a.shadow_lift, a.shadow_mask)
                to_send.save(stage)
            # 落一份存档，便于核对"第二轮到底发的是不是第一轮的结果"
            _keep = os.path.join(out_dir, base + "_in%d.png" % i)
            to_send.save(_keep)
            _mm = float(np.asarray(to_send.convert("L")).mean())
            _ref_mm = float(np.asarray(src.convert("L")).mean())
            print("   [发送存档] %s  亮度 %.1f（原图 %.1f）"
                  % (os.path.basename(_keep), _mm, _ref_mm))
            if a.shadow_lift > 1.0:
                print("   [暗部提亮] ×%.2f（送到豆包前）" % a.shadow_lift)
            # 第一轮：完整提示词（含异常地名）
            # 第二轮：只发"清除白色模糊条带"这一句，其余不动
            # 两轮都在各自的新对话里进行
            pr = build_prompt(stage, view=a.view) if i == 1 else PROMPT_R2
            if i == 1:
                print("   提示词(第1轮):", pr.splitlines()[0][:60], "…")
            else:
                print("   提示词(第2轮):", pr)
            # ★ 两轮各开一个新对话：每次都从"干净输入框"开始，
            #   彻底避免上一轮附件残留被一起发出去（2026-11-04 踩坑）
            # ★ 2026-11-06 起：两轮都用【新对话 + 上传图片】
            #   第一轮结束后会删掉该对话，第二轮是全新对话，
            #   豆包不会带着上一轮的上下文"续改"。
            files = _paint_with_retry(stage, tmp, pr, view=a.view)
            # 记住这次用到的对话（第一轮新建的那个），第二轮结束后要去"同一个对话"取成品
            if _LAST_CONV.get("title"):
                pass
            got = Image.open(files[0]).convert("RGB")
            print("   返回 %s   下载文件 %s" % (got.size, os.path.basename(files[0])))
            # ★ 校验：不能是缩略图，也不能是"没改过的原图"
            _bad = []
            if min(got.size) < 1024:
                _bad.append("尺寸只有 %dx%d（像缩略图）" % got.size)
            _c = _metrics(got, cur)["corr"]
            if _c > 0.9995:
                _bad.append("和输入几乎一样（corr %.5f）" % _c)
            if _bad:
                print("   [校验] 不合格：" + "；".join(_bad) + " → 重试一次")
                files = _paint_with_retry(stage, tmp, pr, view=a.view)
                got = Image.open(files[0]).convert("RGB")
                print("   重试返回 %s   下载文件 %s" % (got.size, os.path.basename(files[0])))
            # 存档：直接复制原始文件（保留 XMP，里面有豆包的 ProduceID）
            import hashlib as _hl
            import shutil as _sh
            _raw_save = os.path.join(out_dir, base + "_out%d.png" % i)
            try:
                _sh.copy2(files[0], _raw_save)      # 保留元数据
            except Exception:
                got.save(_raw_save)                 # 兜底
            with open(files[0], "rb") as _f:
                _md5 = _hl.md5(_f.read()).hexdigest()[:12]
            with open(stage, "rb") as _f:
                _md5_in = _hl.md5(_f.read()).hexdigest()[:12]
            print("   [校验] 发送 md5=%s   返回 md5=%s" % (_md5_in, _md5))
            if a.shadow_lift > 1.0:
                got = _shadow_unlift(got, cur, a.shadow_lift, a.shadow_mask)
            got = _remove_watermark(got)
            raw_m = _metrics(got, ref)
            got = _match_brightness(got, ref)
            # ★ 满相（几乎没有黑夜）时不要做 _keep_shadow：
            #   它会把"纯黑像素"按原图还原，而拼接线也是纯黑 → 线会被贴回来
            ref_dark = float((np.asarray(ref.convert("L")) < 5).mean())
            if ref_dark > 0.02:
                got = _keep_shadow(got, ref)
            elif i == 1:
                print("   [跳过] 满相图不做暗面还原（否则拼接线会被贴回）")
            m = _metrics(got, ref)
            m["raw_bright_delta_pct"] = raw_m["bright_delta_pct"]
            m["size"] = list(got.size)
            report["passes"].append(m)
            print("   相关 %.4f  亮度 %+.1f%%  最大 %d→%d"
                  % (m["corr"], m["bright_delta_pct"], m["max_ref"], m["max_out"]))
            cur = got

            # ★ 第一轮成品另存为"时间戳_日期_最终成品.png"，供第二轮上传与追溯
            if i == 1:
                # ★ 必须走「下载原图」拿官方文件（2026-11-06 用户要求）
                _off1 = _download_official(out_dir, "r1")
                # ★ 只警告、不丢弃：豆包对"改动很小"的图，输出与输入高度相似，
                #   误判丢弃会退回 CDP 抓的脏图（实测把带黑线的原图当成品用了）。
                if _off1 and _looks_like(_off1, stage):
                    print("   [第一轮成品] 注意：下载图与输入高度相似（可能是改动很小的正常输出）")
                if _off1:
                    # ★ 尺寸校验：豆包原生 1536；我们送去的是 2048。
                    #   若拿到 2048，说明又抓成输入图了 → 判失败。
                    _sz_chk = Image.open(_off1).size
                    if _sz_chk[0] > 1700:
                        print("   [第一轮成品] 尺寸 %dx%d 不是豆包原生输出，判为抓错 → 中止"
                              % _sz_chk)
                        return 4
                    import shutil as _sh1
                    _sh1.copy2(_off1, round1_final)      # 原样复制，不重编码
                    print("   [第一轮成品] 用「下载原图」保存：%s"
                          % os.path.basename(round1_final))
                else:
                    # ★ 不再退回 CDP 抓的图：那张可能是我们上传的输入（带黑接缝线），
                    #   一旦当成品用，第二轮会在脏图上继续，最终拼图也带线。
                    #   宁可中止，也不出脏图。
                    print("   [第一轮成品] 没拿到「下载原图」，中止（不退回输入图）")
                    return 4
                import hashlib as _h1
                _m1 = _h1.md5(open(round1_final, "rb").read()).hexdigest()[:12]
                _sz1 = Image.open(round1_final).size
                print("   [第一轮成品] %s（%dx%d）md5=%s"
                      % (os.path.basename(round1_final), _sz1[0], _sz1[1], _m1))

            # ★ 第一轮结束就删掉该对话（用户 2026-11-06 要求）
            if i == 1 and _LAST_CONV.get("title") and not (
                    os.environ.get("DSH_KEEP_CONV") or os.environ.get("DSH_KEEP_CHAT")):
                try:
                    _t = _LAST_CONV["title"].replace(" - 豆包", "")
                    _d = subprocess.run([NODE, os.path.join(HERE, "delete_conv.mjs"), _t],
                                        capture_output=True, text=True, timeout=180)
                    print("   [删对话] 第一轮已删除（%s）"
                          % ("成功" if _d.returncode == 0 else "返回码 %d" % _d.returncode))
                except Exception as _e:
                    print("   [删对话] 第一轮删除失败：", _e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ★ 第二轮结束后：同样点「下载原图」拿官方文件
    try:
        # ★ 先等生成完：实测第二轮刚回来时页面上只有 2 个图标（还没生成好），
        #   此时点下载拿不到文件。第一轮稳定是 4 个图标。
        import time as _tw2
        print("   [下载原图] 第二轮：等 25 秒让豆包生成完再下载")
        _tw2.sleep(25)
        grab = _download_official(out_dir, "r2")
        if grab and os.path.exists(round1_final) and _looks_like(grab, round1_final):
            print("   [下载原图] 注意：第二轮成品与输入高度相似（改动很小，属正常）")
        if grab and os.path.exists(grab):
            g = Image.open(grab).convert("RGB")
            if a.shadow_lift > 1.0:
                g = _shadow_unlift(g, cur, a.shadow_lift, a.shadow_mask)
            g = _remove_watermark(g)
            g = _match_brightness(g, ref)
            m2 = _metrics(g, ref)
            m_cur = _metrics(cur, ref)
            print("   [下载原图] 第二轮 相关 %.4f（CDN 抓的那份 %.4f）"
                  % (m2["corr"], m_cur["corr"]))
            cur = g
            import shutil as _sh2
            _sh2.copy2(grab, os.path.join(out_dir, base + "_out2_official.png"))
            # ★ 第二轮成品也存进中转站，便于核对"最终用的是不是第二轮那张"
            try:
                import time as _t2s
                _stamp2 = _t2s.strftime("%Y%m%d%H%M%S")   # ★ 用当前时分秒，确保是最新那张
                _r2 = os.path.join(STATION, "%s_%s_第二轮成品.png" % (_stamp2, _date_tag))
                _sh2.copy2(grab, _r2)
                import hashlib as _h3
                _m3 = _h3.md5(open(_r2, "rb").read()).hexdigest()[:12]
                print("   [第二轮成品] 采用「下载原图」：%s  md5=%s  已存中转站"
                      % (os.path.basename(grab), _m3))
            except Exception as _e3:
                print("   [第二轮成品] 采用「下载原图」：%s（存中转站失败：%s）"
                      % (os.path.basename(grab), _e3))
        else:
            # ★ 不许静默降级：没拿到第二轮成品就说明"第二轮根本没落到成品上"，
            #   沿用上一轮等于交付第一轮的结果（实测就是这样错的）。
            print("   [下载原图] 第二轮没拿到文件 —— 中止，不拿第一轮的结果充数")
            return 3
    except Exception as e:
        print("   [下载原图] 第二轮整段失败：", e)

    # 删除第二轮用的对话
    _t2 = _LAST_CONV.get("title")
    print("   [对话] 第二轮标题：%s" % (_t2 or "（没取到）"))
    if _t2 and not (os.environ.get("DSH_KEEP_CONV") or os.environ.get("DSH_KEEP_CHAT")):
        try:
            _d2 = subprocess.run([NODE, os.path.join(HERE, "delete_conv.mjs"),
                                  _t2.replace(" - 豆包", "")],
                                 capture_output=True, text=True, timeout=180)
            print("   [删对话] 第二轮：%s"
                  % ("已删除" if _d2.returncode == 0 else "失败（返回码 %d）" % _d2.returncode))
        except Exception as e:
            print("   [删对话] 第二轮失败：", e)
    elif _t2:
        print("   [保留对话] 按环境变量跳过删除：%s" % _t2)

    # ★ 最终结果一律取"中转站里最新那张"（用户要求：带时分秒就是为了用最新的）
    _newest = _latest_station(_date_tag, STATION, since=_stamp)
    if _newest:
        import hashlib as _h4
        _mn = _h4.md5(open(_newest, "rb").read()).hexdigest()[:12]
        print("   [最新成品] 取中转站最新：%s  md5=%s" % (os.path.basename(_newest), _mn))
        try:
            _img_n = Image.open(_newest).convert("RGB")
            if a.shadow_lift > 1.0:
                _img_n = _shadow_unlift(_img_n, cur, a.shadow_lift, a.shadow_mask)
            _img_n = _remove_watermark(_img_n)
            _img_n = _match_brightness(_img_n, ref)
            cur = _img_n
        except Exception as _e4:
            print("   [最新成品] 读取失败，沿用当前：", _e4)
    else:
        print("   [最新成品] 中转站里没有该日期的文件，沿用当前")

    # ★ 不再放大：豆包原生 1536 就是最清晰的，放大只会二次插值变糊
    final = cur
    print("   [尺寸] 交付 %dx%d（原生，不做上采样）" % final.size)
    out_png = os.path.join(out_dir, base + "_polished.png")
    final.save(out_png)
    report["output"] = out_png
    report["final"] = _metrics(final, ref)
    with open(os.path.join(out_dir, base + "_polished.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)

    # 门禁（2026-11-05 改）：不再按相位分档，也不再卡相关值
    #   用户定：月牙形是正常相位，直接交豆包处理即可，不要有顾虑。
    #   只有两种情况算失败：豆包没出图 / 亮度被改得离谱。
    ref_arr = np.asarray(ref.convert("L")).astype(np.float32)
    _H, _W = ref_arr.shape
    _yy, _xx = np.mgrid[0:_H, 0:_W]
    _R = min(_W, _H) / 2.0 * 0.985
    disc = ((_xx - (_W - 1) / 2.0) ** 2 + (_yy - (_H - 1) / 2.0) ** 2) <= _R ** 2
    dark_frac = float((ref_arr[disc] < 8).mean()) if disc.any() else 0.0

    corr = report["final"]["corr"]
    bd = report["final"]["bright_delta_pct"]

    # 只做提示，不做拦阻
    if corr >= 0.90:
        note = "高"
    elif corr >= 0.80:
        note = "正常"
    elif corr >= 0.60:
        note = "偏低（月牙/极端相位属正常，接受）"
    else:
        note = "很低（豆包可能改了整体，建议看一眼成品）"

    ok = True                      # 出了图就算成功
    if abs(bd) > 15:
        print("   [提示] 亮度偏差 %+.1f%% 偏大，建议检查" % bd)

    report["gate"] = {"corr": corr, "dark_frac": round(dark_frac, 3),
                      "note": note, "blocking": False}
    with open(os.path.join(out_dir, base + "_polished.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)
    print("\n[验收] 相关 %.4f（%s）  亮度 %+.1f%%  暗面 %.0f%%  → 出图即通过"
          % (corr, note, bd, dark_frac * 100))
    print("[输出]", out_png)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
