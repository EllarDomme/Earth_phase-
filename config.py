"""config.py —— 全项目的路径与外部程序位置，集中在这一个文件。

**换一台电脑，只需要改这里（或设环境变量 / 写 config.json），不用动别的代码。**

三种优先级（从高到低）：
  1. 环境变量   DSH_DOUBAO_EXE / DSH_DOUBAO_PORT / DSH_PYTHON
  2. config.json（放在本文件同目录）
  3. 自动探测常见安装位置

豆包是**硬性前提**：它负责擦掉拼接黑线、清薄雾条带、提清晰度。
没有豆包，本项目的图会有明显拼接瑕疵，所以不允许跳过。
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = HERE

_CFG_PATH = os.path.join(HERE, "config.json")


def _load_cfg():
    if not os.path.exists(_CFG_PATH):
        return {}
    try:
        with open(_CFG_PATH, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


CFG = _load_cfg()


def _pick(env_key, cfg_key, default=None):
    v = os.environ.get(env_key)
    if v:
        return v
    v = CFG.get(cfg_key)
    if v:
        return v
    return default


# ── 豆包（必需）────────────────────────────────────────────────
# 主程序（能接 --remote-debugging-port 的是这个，不是启动器）
DOUBAO_EXE_CANDIDATES = [
    r"E:\豆包\Doubao\app\Doubao.exe",
    r"C:\Program Files\Doubao\Doubao\app\Doubao.exe",
    r"C:\Program Files (x86)\Doubao\Doubao\app\Doubao.exe",
    os.path.expanduser(r"~\AppData\Local\Doubao\app\Doubao.exe"),
    os.path.expanduser(r"~\AppData\Local\Programs\Doubao\app\Doubao.exe"),
]


def _detect_doubao():
    """按常见安装位置找 Doubao.exe（app 子目录下的那个）。"""
    for p in DOUBAO_EXE_CANDIDATES:
        if os.path.exists(p):
            return p
    for pat in (r"C:\Program Files*\Doubao\**\app\Doubao.exe",
                os.path.expanduser(r"~\AppData\**\Doubao\app\Doubao.exe")):
        hit = glob.glob(pat, recursive=True)
        if hit:
            return hit[0]
    return DOUBAO_EXE_CANDIDATES[0]


DOUBAO_EXE = _pick("DSH_DOUBAO_EXE", "doubao_exe") or _detect_doubao()
DOUBAO_LAUNCHER = os.path.join(os.path.dirname(os.path.dirname(DOUBAO_EXE)), "Doubao.exe")
DOUBAO_PORT = int(_pick("DSH_DOUBAO_PORT", "doubao_port", "9225"))

# ── Node（豆包驱动 .mjs 用）───────────────────────────────────
def _detect_node():
    import shutil
    p = shutil.which("node")
    if p:
        return p
    for c in (r"C:\Program Files\nodejs\node.exe",
              r"C:\Program Files (x86)\nodejs\node.exe",
              os.path.expanduser(r"~\AppData\Roaming\npm\node.exe")):
        if os.path.exists(c):
            return c
    return "node"


NODE = _pick("DSH_NODE", "node") or _detect_node()

# ── Python（run.cmd 用）───────────────────────────────────────
PYTHON = _pick("DSH_PYTHON", "python") or sys.executable

# ── 目录 ─────────────────────────────────────────────────────
OUT_DIR = os.path.join(PROJECT_ROOT, "成品")
WORK_DIR = os.path.join(PROJECT_ROOT, "v2")
STATION_DIR = os.path.join(PROJECT_ROOT, "中转站")
ASSET_DIR = os.path.join(PROJECT_ROOT, "素材")


def explain():
    """打印当前生效的配置，出问题时先看这个。"""
    print("项目根目录 : %s" % PROJECT_ROOT)
    print("豆包主程序 : %s  %s" % (DOUBAO_EXE, "✓" if os.path.exists(DOUBAO_EXE) else "✗ 不存在"))
    print("调试端口   : %d" % DOUBAO_PORT)
    print("Node       : %s  %s" % (NODE, "✓" if os.path.exists(NODE) else "✗ 找不到"))
    print("Python     : %s" % PYTHON)
    src = ("环境变量" if os.environ.get("DSH_DOUBAO_EXE")
           else "config.json" if CFG.get("doubao_exe") else "自动探测")
    print("路径来源   : %s" % src)
    print()
    print("启动豆包（复制到 PowerShell 执行）：")
    print('  Start-Process "%s" -ArgumentList "--remote-debugging-port=%d"' % (DOUBAO_EXE, DOUBAO_PORT))


if __name__ == "__main__":
    explain()
