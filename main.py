"""MonitorCtrl 入口：图形界面 + 命令行模式。

用法:
    python main.py                     启动图形界面
    python main.py --list              列出所有显示器
    python main.py --brightness 60     把主显示器亮度设为 60%
    python main.py --contrast 70 --all 所有显示器对比度设为 70%
    python main.py --get 0x10          读取 VCP 0x10 的当前值/最大值
    python main.py --set 0x60=17       直接写入 VCP（输入源 = HDMI 1）
"""

from __future__ import annotations

import argparse
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 命令行模式使用的参数
CLI_FLAGS = {
    "--list", "-l", "--get", "--set", "--json", "--monitor", "-m", "--all", "-a",
    "--brightness", "-b", "--contrast", "-c", "--volume", "-v", "--input", "--diag",
}


def _wants_cli(argv) -> bool:
    for arg in argv:
        head = arg.split("=", 1)[0]
        if head in CLI_FLAGS:
            return True
    return False


def _ensure_cli_console() -> bool:
    """窗口化打包后没有控制台，CLI 模式自己接一个。

    返回 True 表示复用了父进程的控制台 / 重定向输出；
    返回 False 表示新开了一个控制台窗口（退出前需要停一下让用户看清结果）。
    """
    if sys.stdout is not None and sys.stderr is not None:
        return True
    try:
        import ctypes
        import msvcrt

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetStdHandle.restype = ctypes.c_void_p
        handles = {1: kernel32.GetStdHandle(-11), 2: kernel32.GetStdHandle(-12)}
        if handles[1]:
            for fd, handle in handles.items():
                if not handle:
                    continue
                try:
                    osfd = msvcrt.open_osfhandle(handle, os.O_WRONLY)
                    stream = open(osfd, "w", encoding="utf-8", errors="replace",
                                  buffering=1, closefd=True)
                except OSError:
                    continue
                if fd == 1:
                    sys.stdout = stream
                else:
                    sys.stderr = stream
            if sys.stdout is not None:
                return True

        if not kernel32.AllocConsole():
            return True
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
        try:
            sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
        except OSError:
            pass
        return False
    except Exception:
        return True


# --------------------------------------------------------------------------- #
# 命令行模式
# --------------------------------------------------------------------------- #
def _parse_code(text: str) -> int:
    text = text.strip()
    return int(text, 16) if text.lower().startswith("0x") else int(text, 0)


def _pick_monitors(monitors, index=None, all_monitors=False):
    usable = [m for m in monitors if m.ddc_ok]
    if not usable:
        print("没有检测到支持 DDC/CI 的显示器。", file=sys.stderr)
        return []
    if all_monitors:
        return usable
    if index is not None:
        if 0 <= index < len(monitors):
            return [monitors[index]]
        print("显示器序号超出范围。", file=sys.stderr)
        return []
    primary = next((m for m in usable if m.primary), usable[0])
    return [primary]


def _setup_cli_console() -> None:
    """把控制台代码页切到 UTF-8，避免中文输出乱码。"""
    try:
        import ctypes

        ctypes.WinDLL("kernel32").SetConsoleOutputCP(65001)
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None:
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def run_cli(args) -> int:
    attached = _ensure_cli_console()
    _setup_cli_console()
    try:
        return _run_cli(args)
    finally:
        if not attached and not os.environ.get("MONITORCTRL_NO_PAUSE"):
            _pause_before_exit()


def _pause_before_exit(seconds: int = 20) -> None:
    """双击运行 CLI 时新开的控制台会在进程退出后消失，停一下让用户看清输出。"""
    try:
        print("\n按回车键关闭窗口…", end="", flush=True)
    except Exception:
        return
    try:
        import threading

        done = threading.Event()

        def _wait():
            try:
                if sys.stdin is not None:
                    sys.stdin.readline()
            except Exception:
                pass
            done.set()

        threading.Thread(target=_wait, daemon=True).start()
        done.wait(seconds)
    except Exception:
        pass


def _run_cli(args) -> int:
    from monitorctl import __version__, ddc, vcp

    monitors = ddc.enumerate_monitors(open_handles=True)
    try:
        if args.diag:
            print(ddc.format_report(monitors, __version__))
            return 0
        if args.list:
            payload = []
            for mon in monitors:
                item = {
                    "index": mon.index,
                    "name": mon.display_name,
                    "device": mon.device_name,
                    "resolution": mon.resolution,
                    "primary": mon.primary,
                    "ddc": mon.ddc_ok,
                    "mccs": mon.mccs_version,
                    "manufacturer": mon.edid.manufacturer,
                    "product": "0x%04X" % mon.edid.product_code,
                    "serial": mon.edid.serial_text or str(mon.edid.serial_number or ""),
                    "vcp_count": len(mon.supported_vcp),
                    "error": mon.last_error,
                }
                if mon.ddc_ok:
                    try:
                        cur, mx = mon.get_vcp(0x10)
                        item["brightness"] = cur
                        item["brightness_max"] = mx
                    except ddc.DDCError:
                        pass
                payload.append(item)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                for item in payload:
                    flag = "OK " if item["ddc"] else "ERR"
                    bright = ""
                    if "brightness" in item:
                        bright = "  亮度 %d%%" % round(
                            item["brightness"] / max(1, item["brightness_max"]) * 100
                        )
                    print(
                        "[%d] %s  %s  %s  %s%s"
                        % (
                            item["index"],
                            flag,
                            item["name"],
                            item["resolution"],
                            item["device"],
                            bright,
                        )
                    )
                    if not item["ddc"] and item["error"]:
                        print("      %s" % item["error"])
            return 0

        targets = _pick_monitors(monitors, args.monitor, args.all)
        if not targets:
            return 2

        if args.get is not None:
            code = _parse_code(args.get)
            for mon in targets:
                try:
                    cur, mx = mon.get_vcp(code)
                    if args.json:
                        print(json.dumps(
                            {"monitor": mon.display_name, "code": "0x%02X" % code,
                             "value": cur, "max": mx}, ensure_ascii=False))
                    else:
                        print("%s  0x%02X %s: %d / %d"
                              % (mon.display_name, code, vcp.vcp_name(code), cur, mx))
                except ddc.DDCError as exc:
                    print("%s: %s" % (mon.display_name, exc), file=sys.stderr)
                    return 3
            return 0

        changed = False
        for mon in targets:
            try:
                if args.brightness is not None:
                    _, mx = mon.get_vcp(0x10)
                    mon.set_vcp(0x10, round(args.brightness / 100 * mx))
                    changed = True
                if args.contrast is not None:
                    _, mx = mon.get_vcp(0x12)
                    mon.set_vcp(0x12, round(args.contrast / 100 * mx))
                    changed = True
                if args.volume is not None:
                    _, mx = mon.get_vcp(0x62)
                    mon.set_vcp(0x62, round(args.volume / 100 * mx))
                    changed = True
                if args.input is not None:
                    mon.set_vcp(0x60, args.input)
                    changed = True
                for item in args.set or []:
                    if "=" not in item:
                        print("--set 需要 CODE=VALUE 格式", file=sys.stderr)
                        return 2
                    code_text, value_text = item.split("=", 1)
                    mon.set_vcp(_parse_code(code_text), _parse_code(value_text))
                    changed = True
            except ddc.DDCError as exc:
                print("%s: %s" % (mon.display_name, exc), file=sys.stderr)
                return 3

        if changed and not args.json:
            for mon in targets:
                print("已应用到 %s" % mon.display_name)
        return 0
    finally:
        for mon in monitors:
            mon.close()


# --------------------------------------------------------------------------- #
# 图形界面
# --------------------------------------------------------------------------- #
def run_gui(start_minimized: bool = False, screenshot: str | None = None) -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication

    from monitorctl import config
    from monitorctl.main_window import MainWindow
    from monitorctl.ui import theme, widgets

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("MonitorCtrl")
    app.setOrganizationName("MonitorCtrl")
    app.setWindowIcon(QIcon(widgets.make_pixmap("monitor", 64)))
    app.setStyleSheet(theme.QSS)
    app.setFont(QFont("Microsoft YaHei UI", 9))

    cfg = config.Config()
    window = MainWindow(cfg)
    if screenshot:
        from PySide6.QtCore import QTimer

        window.show()

        def _shot():
            window.grab().save(screenshot)
            window._closing = True
            app.quit()

        QTimer.singleShot(3500, _shot)
    elif start_minimized or cfg.get("start_minimized"):
        window.hide()
        if cfg.get("tray"):
            window.tray.show()
    else:
        window.show()
    return app.exec()


# --------------------------------------------------------------------------- #
def main() -> int:
    # 窗口化程序没有 stdout，--help 也需要先接上控制台
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        _ensure_cli_console()
        _setup_cli_console()

    parser = argparse.ArgumentParser(
        prog="MonitorCtrl",
        description="通过 DDC/CI 控制显示器（亮度 / 对比度 / 输入源 / 色彩等）",
    )
    parser.add_argument("--list", "-l", action="store_true", help="列出所有显示器")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--monitor", "-m", type=int, help="显示器序号（见 --list）")
    parser.add_argument("--all", "-a", action="store_true", help="对所有显示器生效")
    parser.add_argument("--get", metavar="CODE", help="读取 VCP 值，如 0x10")
    parser.add_argument("--set", metavar="CODE=VALUE", action="append",
                        help="写入 VCP，可重复，如 --set 0x10=50")
    parser.add_argument("--brightness", "-b", type=int, metavar="0-100", help="亮度百分比")
    parser.add_argument("--contrast", "-c", type=int, metavar="0-100", help="对比度百分比")
    parser.add_argument("--volume", "-v", type=int, metavar="0-100", help="音量百分比")
    parser.add_argument("--input", type=int, metavar="N", help="输入源编号（1=VGA 3=DVI 4=HDMI 15=DP）")
    parser.add_argument("--minimized", action="store_true", help="启动后最小化到托盘")
    parser.add_argument("--diag", action="store_true", help="输出详细诊断报告（排查 DDC/CI 不可用）")
    parser.add_argument("--screenshot", metavar="PATH", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if _wants_cli(sys.argv[1:]):
        return run_cli(args)
    return run_gui(args.minimized, args.screenshot)


if __name__ == "__main__":
    sys.exit(main())
