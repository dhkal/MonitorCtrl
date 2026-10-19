"""打包脚本：生成单文件 MonitorCtrl.exe。

    python build.py            # 单文件（推荐分发）
    python build.py --onedir   # 目录模式（启动更快）
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(BASE, "dist")
BUILD = os.path.join(BASE, "build")

EXCLUDES = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQml",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtBluetooth",
    "PySide6.QtPositioning",
    "PySide6.QtSerialPort",
    "PySide6.QtSensors",
    "PySide6.QtWebSockets",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSvgWidgets",
    "tkinter",
    "unittest",
    "pydoc",
]


def main() -> int:
    onedir = "--onedir" in sys.argv
    icon = os.path.join(BASE, "assets", "icon.ico")
    version = os.path.join(BUILD, "version_info.txt")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir" if onedir else "--onefile",
        "--windowed",
        "--name", "MonitorCtrl",
        "--distpath", DIST,
        "--workpath", os.path.join(BUILD, "work"),
        "--specpath", BUILD,
    ]
    if os.path.exists(icon):
        cmd += ["--icon", icon]
    if os.path.exists(version):
        cmd += ["--version-file", version]
    for module in EXCLUDES:
        cmd += ["--exclude-module", module]
    cmd.append(os.path.join(BASE, "main.py"))

    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=BASE)
    if result.returncode != 0:
        print("打包失败")
        return result.returncode

    exe = os.path.join(DIST, "MonitorCtrl.exe")
    if os.path.exists(exe):
        size = os.path.getsize(exe) / (1024 * 1024)
        print("\n完成：%s (%.1f MB)" % (exe, size))
    else:
        print("\n完成：%s" % os.path.join(DIST, "MonitorCtrl"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
