"""audit_wiring.py —— 流水线自检：确认关键改动真的接进了代码与手册

用法: python audit_wiring.py          # 只报告
      python audit_wiring.py --strict # 有 ✗ 就用非零退出码（可挂 CI）
      python audit_wiring.py --fix    # 发现 docx 过期就自动重新生成

为什么需要它：
  改脚本时最常见的事故是"改了但没接上"——比如
  · 参数加了却没传进子进程
  · 校正算了却没重建输出变量
  · 手册写了但代码没同步
  这个脚本把这些点逐条断言一遍。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
F = {
    "full": os.path.join(HERE, "make_earth_full.py"),
    "polish": os.path.join(HERE, "doubao_polish.py"),
    "render": os.path.join(HERE, "render_earth.py"),
    "moon": os.path.join(HERE, "compose_moon.py"),
    "verify": os.path.join(HERE, "verify.py"),
    "starless": os.path.join(HERE, "starless.py"),
    "agents": r"E:\DeskTop\AGENTS.md",
    "boost": os.path.join(HERE, "doubao_boost.py"),
    "light": os.path.join(HERE, "lighting.py"),
    "run": os.path.join(HERE, "run.cmd"),
    "md": os.path.join(HERE, "技术手册_地相图.md"),
    "config": os.path.join(HERE, "config.py"),
    "readme": os.path.join(HERE, "README.md"),
    "req": os.path.join(HERE, "requirements.txt"),
    "agents_repo": os.path.join(HERE, "AGENTS.md"),
    "stage": os.path.join(HERE, "stage_boost.py"),
    "layout": os.path.join(HERE, "layout.py"),
}

# (文件, 说明, 正则)
CHECKS = [
    # ── 主流程开关
    ("full", "开关 --polish", r'"--polish"'),
    ("full", "开关 --archive", r'"--archive"'),
    # ── 主流程调用
    ("full", "调用 doubao_polish", r"doubao_polish\.py"),
    ("full", "归档在流程末尾", r"# ── 自动归档"),
    # ── 豆包链
    ("polish", "第2轮走引用", r"doubao_quote\.mjs"),
    ("polish", "取成品点下载原图", r"doubao_download\.mjs"),
    ("polish", "两轮各开新对话", r"new_chat=True"),
    ("polish!", "旧的兜底取标题已废弃", r"兜底取到"),
    # ── 海报几何
    # ── 增强
    ("render", "渲染环境光 0.01~0.03（暗但可见）",
     r'AMBIENT = float\(globals\(\)\.get\("AMBIENT", 0\.0(1|2|3)'),
    # ── 手册
    ("md", "之十三 引用", r"第十一条之十三"),
    ("md", "之十七 归档时机", r"第十一条之十七"),
    ("full!", "确认已删除 --enhance", r'"--enhance"'),
    ("full!", "确认已删除 --poster", r'"--poster"'),
    ("full!", "确认不再调用 post_enhance", r"post_enhance\.py"),
    ("full!", "确认不再调用 make_poster_ref", r"make_poster_ref\.py"),
    ("full", "接入中国可见规则", r"china_rule"),
    ("full", "默认开启中国约束", r"--no-china"),
    ("md", "之二十四 中国在亮部", r"第十一条之二十四"),
    ("polish", "第一轮结束即删对话", r"第一轮已删除"),
    ("polish!", "确认没有把删除丢到后台线程", r"_th\.Thread\(target=_del_conv"),
    ("polish", "日志会打印删对话结果", r"\[删对话\] 第二轮"),
    ("md", "之二十五 交图规范", r"第十一条之二十五"),
    ("md", "之二十六 同步删对话", r"第十一条之二十六"),
    ("md", "之二十七 最高原则", r"第十一条之二十七"),
    ("md", "真实第一", r"真实第一，中国第二"),
    ("full", "视角仍是月下点", r"sublunar_point"),
    ("render", "大气弧光参数 ARC_W", r"ARC_W\s*=\s*float"),
    ("render", "云顶自阴影 RELIEF", r"RELIEF\s*=\s*float"),
    ("render", "高光余量 knee=0.48", r"knee = 0\.48"),
    ("polish", "交付原生尺寸（不放大）", r"原生，不做上采样"),
    ("md", "之二十八 质感四项", r"第十一条之二十八"),
    ("full", "接入 --moon 版式", r"compose_moon\.py"),
    ("moon", "月面底图存在", r"moon_base\.png"),
    ("md", "之二十九 地出式版式", r"第十一条之二十九"),
    ("full", "豆包失败就中止（不覆盖成品）", r"豆包阶段未成功"),
    ("md", "之三十 豆包失败中止", r"第十一条之三十"),
    ("moon", "默认底图是原版（非镜像）", r'"moon_base\.png"'),
    ("moon", "地球默认不旋转", r"earth-rot\", type=float, default=0"),
    ("md", "之三十一 光照判据", r"第十一条之三十一"),
    ("moon", "地球提亮默认 gamma 0.88", r"earth-gamma\", type=float, default=0\.88"),
    ("moon", "地球饱和默认 1.30", r"earth-sat\", type=float, default=1\.30"),
    ("moon", "暗面不额外提亮", r"dark-lift\", type=float, default=1\.0"),
    ("md", "之三十二 调色与暗面", r"第十一条之三十二"),
    ("moon", "高光只软膝（无全局缩放）", r"高光软膝"),
    ("moon!", "确认没有全局缩放高光", r"earth_p99 / 255 / p99"),
    ("md", "之三十三 高光软膝", r"第十一条之三十三"),
    ("full", "接入 --boost", r'"--boost"'),
    ("boost", "提示词固定", r"提高地球清晰度"),
    ("boost", "按相位融合（暗面用原图）", r"blend_by_phase"),
    ("boost", "去水印", r"remove_watermark"),
    ("md", "之三十五 豆包提清晰度", r"第十一条之三十五"),
    ("boost", "明暗按相位过渡", r"alpha"),
    ("polish", "出图即通过（无门禁分档）", r"ok = True"),
    ("polish!", "旧的 corr_need 已删除", r"corr_need"),
    ("md", "之三十六 月牙正常", r"第十一条之三十六"),
    ("boost", "只改盘内（盘外不动）", r"只在盘内"),
    ("boost", "月面回正 restore_scene", r"restore_scene"),
    ("boost", "过渡带不压暗原图", r"np\.maximum"),
    ("render", "云顶悬照 CLOUD_TOP", r"CLOUD_TOP", ),
    ("md", "之三十七 云顶悬照", r"第十一条之三十七"),
    ("moon", "自动选底图", r"自动选底图"),
    ("md", "之三十一 已更正", r"亮壁在受光的【对面】"),
    ("moon", "按整圆盘居中（非亮部）", r"cx - D // 2"),
    ("md", "月牙居中规则", r"圆的几何中心永远在 x = 960"),
    ("moon", "颗粒默认关闭", r'moon-grain", type=float, default=0\.0'),
    ("boost", "光照补偿 deglint", r"deglint"),
    ("md", "之三十八 光照补偿在最后", r"第十一条之三十八"),
    ("boost", "高光封顶 240", r"ceil=0\.941"),
    ("md", "之三十九 高光封顶", r"第十一条之三十九"),
    ("md", "之四十 光照体检", r"第十一条之四十"),
    ("polish", "第二轮新提示词", r"清除棕黄色"),
    ("polish", "旧提示词已保留", r"PROMPT_R2_OLD"),
    ("md", "之四十一 三轮提示词", r"第十一条之四十一"),
    ("boost", "物理体检 physics_report", r"physics_report"),
    ("boost", "尺寸一致不重采样", r"直接使用（不裁剪不缩放）"),
    ("md", "之四十二 科学修正", r"第十一条之四十二"),
    ("polish", "中转站目录在项目内", r"中转站"),
    ("polish", "第二轮字节复制", r"copy2\(round1_final"),
    ("polish", "两轮都下载原图", r'_download_official\(out_dir, "r2"\)'),
    ("md", "之四十三 中转站流程", r"第十一条之四十三"),
    ("boost", "夜面校正 night_crush", r"night_crush"),
    ("boost", "夜面压到物理量级", r"night_out = 0\.3"),
    ("md", "之四十四 物理真实版", r"夜面就该看不见"),
    ("verify", "交付自证脚本存在", r"disc_metrics"),
    ("agents", "十二条致命约束", r"十二条最致命的约束"),
    ("agents", "必须跑 verify", r"verify\.cmd"),
    ("md", "之四十五 防死调用", r"第十一条之四十五"),
    ("boost", "球缘抗锯齿 clean_rim", r"clean_rim"),
    ("boost", "羽化 2px", r"feather=2\.0"),
    ("md", "之四十七 球缘抗锯齿", r"第十一条之四十七"),
    ("boost", "缩略图拒收（重试）", r"太小，重试"),
    ("boost", "连续 3 次中止", r"连续 3 次返回缩略图"),
    ("md", "之四十八 缩略图拒收", r"第十一条之四十八"),
    ("md", "之四十九 取图机制", r"第十一条之四十九"),
    ("moon", "天空默认刷到近黑", r'sky-target\", default=\"1,1,1'),
    ("moon", "遮罩内收 1.5%（防源图天空漏出）", r"_pad = max\(1, int\(D \* 0\.0075\)\)"),
    ("moon", "earth-pct 默认 0.36", r'earth-pct", type=float, default=0\.36'),
    ("moon", "天空按轮廓填（不硬切）", r"contour\[x\]"),
    ("starless", "摘星支持逐像素天空", r"sky=None"),
    ("moon", "摘星用地形轮廓 mask", r"_sky = yy < _con"),
    ("moon", "轮廓平滑用滚动最小值", r"i \+ 11\]\.min\(\)"),
    ("md", "之五十三 最高处三因", r"地形最高处.*不自然"),
    ("full", "自动清理中间产物", r"_clean_intermediates"),
    ("full", "清理覆盖临时子目录", r"_boost_tmp"),
    ("full", "清理开关 --no-clean", r"--no-clean"),
    ("full", "收尾清两遍（豆包晚落盘）", r"sleep\(4\.0\)"),
    ("md", "之五十四 自动清理", r"中间产物自动清理"),
    ("full", "匀光流程 --uniform", r'"--uniform"'),
    ("full", "匀光时开全亮渲染", r"R.FULL_LIT = 1"),
    ("full", "收尾统一打光", r"apply_lighting"),
    ("boost", "匀光模式 --flat", r'"--flat"'),
    ("render", "全亮开关 FULL_LIT", r"FULL_LIT"),
    ("render", "无临边开关 FULL_FLAT", r"FULL_FLAT"),
    ("render", "超采样 SS", r'SS = int\(globals\(\)\.get\("SS"'),
    ("light", "打光模块 lighting.py", r"def apply_lighting"),
    ("light", "大气弧窄 0.004", r'ARC_W = float\(globals\(\)\.get\("ARC_W", 0\.004\)\)'),
    ("md", "之五十五 匀光流程", r"光照最后施加"),
    ("light", "弧光暮光带 ±0.09", r"cosi \+ 0\.09"),
    ("md", "之五十五 弧光绕满受光缘", r"弧光必须.{0,4}绕满受光缘"),
    ("light", "暮光漫射 TWILIGHT", r"TWILIGHT = float"),
    ("light", "sRGB→线性解码", r"_srgb_to_linear"),
    ("light", "线性→sRGB 编码", r"_linear_to_srgb"),
    ("light", "打光在线性空间", r"_srgb_to_linear\(A_srgb\)"),
    ("full", "匀光用物理色彩 gamma=1", r'"--earth-gamma", "1\.0"'),
    ("md", "之五十五 线性光打光", r"打光必须在线性光空间做"),
    ("light", "太阳耀斑模型", r"GLINT_GAIN"),
    ("light", "耀斑菲涅尔", r"0\.02 \+ 0\.98"),
    ("light", "Cox-Munk 波面斜率", r"sigma2 = 0\.003 \+ 0\.00512"),
    ("light", "海况参数 WIND_MS", r"WIND_MS"),
    ("light", "弧光瑞利光谱", r"1 / 650\.0"),
    ("light", "暮光转琥珀", r"sunset = np\.array"),
    ("light", "朗伯余弦定律", r"lambert = np\.clip\(cosi"),
    ("light", "曝光系数 EXPOSURE", r"EXPOSURE"),
    ("light", "反照率上限 0.85", r"ALBEDO_CAP"),
    ("md", "之五十五 朗伯余弦修正", r"朗伯余弦：一个存在很久的物理错误"),
    ("md", "之五十五 反照率上限", r"反照率上限 0\.85"),
    ("moon", "月面亮度系数 --moon-gain", r"--moon-gain"),
    ("full", "匀光流程压暗月面", r'"--moon-gain", "0\.65"'),
    ("light", "弧光亮度随光程衰减", r"1\.0 / \(1\.0 \+ 0\.35"),
    ("md", "之五十五 地球亮度与月面对比", r"地球.{0,4}够不够亮"),
    ("md", "之五十五 弧光亮度关系修正", r"弧光亮度关系写反了"),
    ("light", "暮光独立于朗伯余弦", r"day \* lambert \+ _tw"),
    ("light", "大气外晕 ARC_A2", r"ARC_A2"),
    ("light", "输出按反照率封顶", r"np\.minimum\(out, ALBEDO_CAP"),
    ("md", "之五十五 暮光bug", r"暮光被朗伯余弦乘没了"),
    ("md", "之五十五 大气辉光两层", r"核心 \+ 外晕"),
    ("md", "之五十五 云白边根因", r"云边白边.{0,6}是我们自己"),
    ("run", "默认模式走匀光", r"goto :run_uniform"),
    ("full", "匀光地球相不进成品", r"_bak_uni_%s_地球相"),
    ("md", "之五十五 匀光成为默认", r"匀光流程成为默认"),
    ("verify", "自证支持中间素材", r"_bak_uni_.{0,30}地球相"),
    ("md", "之五十五 verify 跟随策略", r"verify 必须跟着策略变"),
    ("polish", "中转站取最新", r"_latest_station"),
    ("polish", "第二轮用当下时间戳", r"_stamp2"),
    ("polish", "最终取站里最新", r"取中转站最新"),
    ("polish", "第二轮失败就中止", r"不拿第一轮的结果充数"),
    ("polish", "下载目录每次新建", r"official_dl_%s_%d"),
    ("md", "之五十五 中转站取最新", r"中转站的正确用法"),
    ("polish", "不退回 CDP 抓图", r"不退回输入图"),
    ("polish", "尺寸 1536 判据", r"不是豆包原生输出"),
    ("full", "复用中转站成品 --reuse", r'"--reuse"'),
    ("full", "中转站只留最近 1 小时", r"_clean_station|keep_hours=1\.0"),
    ("boost", "提清晰度：亮度不可变", r"亮度不可变"),
    ("light", "夜面地板 NIGHT_SRGB", r"NIGHT_SRGB"),
    ("md", "之五十五 夜面地板", r"夜面不该比太空还黑"),
    ("md", "流水线总览（一页）", r"流水线总览（一页看懂"),
    ("md", "早期步骤已标注过时", r"早期版本，与现行流程不完全对应"),
    ("full", "v2 临时目录自动清理", r"_clean_tmp_dirs"),
    ("md", "之五十五 临时目录清理", r"v2 临时目录也要清"),
    ("config", "路径集中到 config.py", r"^DOUBAO_EXE = |doubao_exe"),
    ("config", "豆包路径可配置", r"doubao_exe"),
    ("config", "Node 路径可配置", r"DSH_NODE"),
    ("readme", "README 写明需要 Node", r"Node\.js（豆包驱动需要）"),
    ("readme", "README 声明豆包必需", r"必须配合「豆包」使用|本项目必须配合"),
    ("req", "requirements.txt", r"numpy>=1\.24"),
    ("agents_repo", "仓库内 AGENTS.md 存在", r"给 AI 助手看的"),
    ("readme", "README 说明 AI 助手用法", r"用 AI 助手驱动"),
    ("md", "之五十五 开源前置", r"开源前的改造"),
    ("moon", "四张底图分档", r"BASE_TIERS"),
    ("moon", "亮度系数只压不提", r"_BASE_SCALE"),
    # ── 规则不绕过（2026-11-09 用户发现的第三类 bug：参数一给就绕过后续逻辑）
    ("moon", "分档只有一条路径", r"底图 / 亮度 / 质感：一条路径"),
    ("moon", "--base 也走亮度分档", r"_tname = next\(\(n for n in BASE_TIERS"),
    ("moon", "月面物理量只算一次", r"def _phys\(date, utc\)"),
    ("moon!", "旧的重复星历代码已删", r"def _unit0\("),
    ("boost", "几何格式校验", r"需要三个归一化数"),
    ("verify", "宽度不写死 1920", r"_pick\(date, "),
    ("layout", "真实尺寸常量", r"EARTH_PCT_TRUE"),
    ("moon", "earth-size 参数", r"--earth-size"),
    ("full", "earth-size 传下去", r"a\.earth_size"),
    ("full", "noboost 也补齐提升版", r"noboost）：提升版 = 月面版"),
    ("moon", "星点 mask 跟随 --cx", r"a\.cx \* Ww"),
    ("moon!", "星点 mask 不再写死圆心", r"xx - 0\.50 \* Ww"),
    ("moon", "--cx 真的传进几何", r"a\.cx\b"),
    ("moon", "--cy 真的传进几何", r"a\.cy\b"),
    ("boost", "提清晰度走 disc_geom", r"disc_geom\(W, H\)"),
    ("boost!", "finish_tone 不再写死 0.36", r"int\(0\.36 \* W / 2\)"),
    ("verify", "自证走 disc_geom", r"disc_geom\(W, H\)"),
    ("verify!", "自证不再写死 0.31", r"yy - 0\.31 \* H"),
    ("light", "打光走 layout", r"disc_geom"),
    # ── 晨昏线宽度：0.08 是"真实优先"的定稿值，改它要先问用户
    ("light", "晨昏线宽度 0.08（真实优先）", r"term_w=0\.08"),
    ("md", "之五十五 橡皮筋判定", r"橡皮筋绑在球上"),
    ("moon", "月夜质感补偿 4.0", r"NIGHT_CONTRAST.*4\.0"),
    ("md", "之五十五 质感补偿", r"月夜档的.*质感补偿.*4\.0"),
    # ── 提升优先（2026-11-09：让豆包只碰圆盘，不碰月面）
    ("boost", "几何可覆盖", r"def _geom\(W, H\)"),
    ("stage", "圆盘几何用居中值", r"DISC_GEOM = \"0\.5,0\.5,0\.5\""),
    ("stage", "先提升再拼图", r"boost_then_compose"),
    ("full", "回退开关 --boost-last", r'"--boost-last"'),
    ("full", "默认走提升优先", r'not getattr\(a, "boost_last", False\)'),
    ("full", "旧提升会跳过", r"boost_first_done"),
    ("run", "run.cmd 支持 boostlast 回退", r"boostlast"),
    ("moon", "太阳高度符号已修正", r"方向相反"),
    ("md", "之五十五 底图分档", r"四张底图按"),
    ("md", "之五十五 符号坑", r"ephem 的方向是反的"),
    ("md", "之五十五 尺寸判据", r"尺寸 2048 vs 1536"),
    ("md", "之五十五 跨运行污染", r"中转站跨运行的污染"),
    ("md", "之五十五 耀斑升级", r"Cox–Munk 波面斜率"),
    ("md", "之五十五 弧光瑞利", r"大气弧升级：瑞利光谱"),
    ("light", "耀斑限定盘内", r"spec \* \(rr <= 1\.0\)"),
    ("md", "之五十五 太阳耀斑", r"太阳耀斑：海面的镜面反射"),
    ("md", "之五十五 真实度边界", r"仍是近似"),
    ("md", "之五十五 暮光漫射", r"暮光漫射"),
    ("md", "之五十五 光照体检五指标", r"光照体检的五个指标"),
    ("md", "之五十二 占比与轮廓", r"地球占比 0\.36"),
    ("moon", "摘星默认开启", r"星点：摘掉"),
    ("moon", "地平线用固定 0.595H", r"hz = int\(H \* 0\.595\)"),
    ("boost", "clean_rim 盘外保留原天空", r"Image\.composite\(disc, orig"),
    ("starless", "只摘亮点（不改底色）", r"lum > bg \+ thresh"),
    ("md", "之五十 天空统一", r"第十一条之五十"),
]


def _base_sky_check():
    """底图的天空必须已经是近黑（否则成品会出现一圈灰）"""
    try:
        import numpy as np
        from PIL import Image
        p = os.path.join(HERE, "素材", "moon_base.png")
        A = np.asarray(Image.open(p).convert("L")).astype(np.float32)
        sky = A[:600, :].mean()
        return sky < 2.0, sky
    except Exception as e:
        return False, -1


# 这些文件**可以不在仓库里**（比如项目外的 AGENTS.md）。
# 别人 clone 下来跑自检时，缺了就跳过，不算失败。
OPTIONAL = {"agents"}


def main():
    strict = "--strict" in sys.argv
    bad = 0
    skipped = 0
    print("=" * 70)
    for key, desc, pat in CHECKS:
        p = F[key.rstrip("!")]
        if not os.path.exists(p):
            if key.rstrip("!") in OPTIONAL:
                print("- %-8s %-26s 跳过（本机没有该文件，属正常）" % (key, desc))
                skipped += 1
                continue
            print("✗ %-8s %-26s 文件不存在" % (key, desc))
            bad += 1
            continue
        txt = open(p, encoding="utf-8").read()
        want_absent = key.endswith("!")
        found = re.search(pat, txt) is not None
        ok = (not found) if want_absent else found
        if ok:
            print("✓ %-8s %-26s" % (key, desc))
        else:
            print("✗ %-8s %-26s  ← 没找到" % (key, desc))
            bad += 1
    # ── docx 时效检查（md 改了但忘了导出）
    # ── 底图天空是否已刷黑（否则成品圆盘外会出现一圈灰）
    try:
        _ok, _sky = _base_sky_check()
        if _ok:
            print("✓ base     底图天空已刷黑（%.2f）" % _sky)
        else:
            print("✗ base     底图天空还是灰的（%.2f）← 跑 诊断\\blacken_base_sky.py" % _sky)
            bad += 1
    except Exception as _e:
        print("· base     底图检查跳过:", _e)

    md_p = F["md"]
    dx_p = os.path.join(HERE, "技术手册_地相图.docx")
    if os.path.exists(md_p) and os.path.exists(dx_p):
        t_md, t_dx = os.path.getmtime(md_p), os.path.getmtime(dx_p)
        if t_dx >= t_md:
            print("✓ docx    比 md 新（%.0f KB）" % (os.path.getsize(dx_p) / 1024))
        else:
            lag = (t_md - t_dx) / 60.0
            print("✗ docx    比 md 旧 %.0f 分钟  ← 请重新生成" % lag)
            bad += 1
            if "--fix" in sys.argv:
                try:
                    import subprocess as _sp
                    _r = _sp.run([sys.executable, os.path.join(HERE, "md2docx.py"),
                                  md_p, dx_p], capture_output=True, text=True, timeout=600)
                    print("   [fix] " + (_r.stdout or "").strip().splitlines()[-1])
                    bad -= 1
                except Exception as e:
                    print("   [fix] 失败：", e)
    else:
        print("· docx    未生成（可选）")

    # ── 死调用检查：流水线引用的脚本是否都存在
    dead_total = 0
    try:
        dc = os.path.join(HERE, "check_deadcalls.py")
        if os.path.exists(dc):
            import subprocess as _sp2
            r = _sp2.run([sys.executable, dc], capture_output=True, text=True, timeout=120)
            out = r.stdout or ""
            bads = [ln for ln in out.splitlines() if ln.strip().startswith("✗")]
            calls = [ln for ln in out.splitlines() if "✓" in ln and ".py" in ln]
            if bads:
                for ln in bads:
                    print("✗ deadcall %s" % ln.strip())
                dead_total = len(bads)
            else:
                print("✓ deadcall %-26s %d 个被调用脚本全部存在" % ("防死调用", len(calls)))
        else:
            print("✗ deadcall 缺少 check_deadcalls.py")
            dead_total = 1
    except Exception as e:
        print("✗ deadcall 检查失败：", e)
        dead_total = 1

    print("=" * 70)
    bad += dead_total
    _total = len(CHECKS) + 1 - skipped
    print("通过 %d / %d%s"
          % (_total - bad, _total, ("（跳过 %d 项）" % skipped) if skipped else ""))

    md = open(F["md"], encoding="utf-8").read() if os.path.exists(F["md"]) else ""
    n = len(re.findall(r"###? 第十一条之", md))
    print("手册：%d 行，第十一条共 %d 个小节" % (md.count("\n") + 1, n))

    if bad and strict:
        sys.exit(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
