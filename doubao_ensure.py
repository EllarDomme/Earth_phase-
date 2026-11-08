"""doubao_ensure.py —— 确保豆包以 CDP 调试模式在跑（流水线自动调用）

背景：
    豆包只有在**启动参数**里带 `--remote-debugging-port=9225` 时才开调试端口。
    从普通快捷方式打开是没有的。所以自动化每次要先确认/拉起它。

用法：
    python doubao_ensure.py            # 检查，不在就拉起来
    python doubao_ensure.py --check    # 只检查，不启动

返回码：0 = CDP 可用；2 = 不可用（需要人工处理）
"""
import argparse
import os
import socket
import subprocess
import sys
import time

import config                                    # 路径统一由 config.py 管理
APP_EXE = config.DOUBAO_EXE                      # 主程序（不是 launcher）
LAUNCHER = config.DOUBAO_LAUNCHER                # launcher 不转发参数，仅作兜底
PORT = config.DOUBAO_PORT


def cdp_alive(port=PORT, timeout=1.0):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def doubao_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Doubao.exe", "/NH"],
                             capture_output=True, text=True, timeout=10,
                             encoding="mbcs", errors="ignore")
        return "Doubao.exe" in (out.stdout or "")
    except Exception:
        return False


def launch(port=PORT):
    """带上调试端口启动豆包。"""
    exe = APP_EXE if os.path.exists(APP_EXE) else LAUNCHER
    if not os.path.exists(exe):
        raise FileNotFoundError("找不到豆包主程序：" + exe)
    cmd = [exe, f"--remote-debugging-port={port}"]
    kwargs = dict(close_fds=True)
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200   # DETACHED | NEW_GROUP
    subprocess.Popen(cmd, **kwargs)
    return exe


def ensure(port=PORT, wait=90, verbose=True, allow_launch=False):
    """检查 CDP；allow_launch=False 时只报告，不尝试启动（沙箱内起不来）。"""
    if cdp_alive(port):
        if verbose:
            print("[豆包] CDP %d 已就绪" % port)
        return True

    if doubao_running():
        if verbose:
            print("[豆包] 正在运行，但没有调试端口 —— 无法自动接管")
            print("       需要人工：完全退出豆包（托盘右键→退出），再跑一次本脚本")
        return False

    if not allow_launch:
        if verbose:
            print("[豆包] 未运行（或未带调试端口）。需要向用户申请一次提权后启动：")
            print("       Start-Process \"%s\" --ArgumentList \"--remote-debugging-port=9225\"")
        return False

    if verbose:
        print("[豆包] 未运行，正在带调试端口启动……")
    try:
        exe = launch(port)
        if verbose:
            print("       已启动:", exe)
    except Exception as e:
        if verbose:
            print("[豆包] 启动失败:", e)
        return False

    t0 = time.time()
    while time.time() - t0 < wait:
        if cdp_alive(port):
            if verbose:
                print("[豆包] CDP %d 已就绪（用时 %.1fs）" % (port, time.time() - t0))
            return True
        time.sleep(1.5)
    if verbose:
        print("[豆包] %.0fs 内端口未开，启动失败或被已运行实例接管" % wait)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查")
    ap.add_argument("--launch", action="store_true", help="允许尝试启动（需提权环境）")
    a = ap.parse_args()
    ok = cdp_alive() if a.check else ensure(allow_launch=a.launch)
    if a.check:
        print("[豆包] CDP %d: %s" % (PORT, "可用" if ok else "不可用"))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
