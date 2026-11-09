"""final_audit.py —— 逐条核对"说过的规则"是否真的在代码/手册里"""
import os
import re

H = r"E:\DeskTop\地球"
CHECKS = [
    # (文件, 检查项, 正则)
    ("make_earth_full.py", "--moon 开关", r'"--moon"'),
    ("make_earth_full.py", "调用 compose_moon", r"compose_moon\.py"),
    ("make_earth_full.py", "豆包失败中止", r"豆包阶段未成功"),
    ("make_earth_full.py", "中国规则接入", r"china_rule"),
    ("compose_moon.py", "底图为原版 moon_base.png", r'"moon_base\.png"'),
    ("compose_moon.py", "地球默认不旋转", r'earth-rot", type=float, default=0\.0'),
    ("compose_moon.py", "天空目标 1,1,1", r'default="1,1,1"'),
    ("compose_moon.py", "抹星（starless）", r"strip_stars"),
    ("compose_moon.py", "高光只软膝", r"高光软膝"),
    ("compose_moon.py", "无全局缩放", r"不做全局缩放"),
    ("compose_moon.py", "gamma 0.88", r'earth-gamma", type=float, default=0\.88'),
    ("compose_moon.py", "饱和 1.30", r'earth-sat", type=float, default=1\.30'),
    ("compose_moon.py", "暗面不提亮", r'dark-lift", type=float, default=1\.0'),
    ("render_earth.py", "大气弧光 ARC_W", r"ARC_W"),
    ("render_earth.py", "弧光可溢出", r"ARC_OUT"),
    ("render_earth.py", "云顶自阴影 RELIEF", r"RELIEF"),
    ("render_earth.py", "高光余量 knee 0.48", r"knee = 0\.48"),
    ("render_earth.py", "环境光 0.02", r'AMBIENT", 0\.02'),
    ("doubao_polish.py", "交付原生尺寸", r"原生，不做上采样"),
    ("doubao_polish.py", "删对话调用", r"delete_conv\.mjs"),
    ("doubao_polish.py", "删对话日志", r"\[删对话\]"),
]

print("%-22s %-26s %s" % ("文件", "检查项", "结果"))
print("-" * 62)
bad = 0
for f, desc, pat in CHECKS:
    p = os.path.join(H, f)
    ok = os.path.exists(p) and re.search(pat, open(p, encoding="utf-8").read()) is not None
    print("%-22s %-26s %s" % (f, desc, "OK" if ok else "缺失"))
    if not ok:
        bad += 1

md = open(os.path.join(H, "技术手册_地相图.md"), encoding="utf-8").read()
print("\n手册小节（之二十九 ~ 之三十四）：")
for n in ["二十九", "三十", "三十一", "三十二", "三十三", "三十四"]:
    print("   之%-4s %s" % (n, "有" if ("第十一条之" + n) in md else "缺失"))

print("\n结论：%d 项检查，缺失 %d 项" % (len(CHECKS), bad))
