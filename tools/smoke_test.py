"""开发用：功能自检 + 对话框截图（模拟显示器，无需硬件）。"""

from __future__ import annotations

import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication  # noqa: E402

import preview  # noqa: E402
from monitorctl import config, ddc  # noqa: E402
from monitorctl.main_window import MainWindow  # noqa: E402
from monitorctl.ui import theme  # noqa: E402
from monitorctl.ui.dialogs import (  # noqa: E402
    DiagnosticsDialog,
    SettingsDialog,
    VcpBrowserDialog,
)

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name + (("  -> " + detail) if detail and not condition else ""))
    if not condition:
        failures.append(name)


def wait(app, ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    ddc.enumerate_monitors = preview.fake_enumerate
    app = QApplication(sys.argv[:1])
    app.setStyleSheet(theme.QSS)
    window = MainWindow(config.Config(os.path.join(BASE, "tools", "_test_config.json")))
    window.resize(1120, 800)
    window.show()
    wait(app, 1200)

    check("扫描到 2 台显示器", len(window.monitors) == 2, str(len(window.monitors)))
    mon0, mon1 = window.monitors[0], window.monitors[1]
    check("默认选中第一台", window.current is mon0)
    check("能力字符串解析出 36 项 VCP", len(mon0.supported_vcp) == 36, str(len(mon0.supported_vcp)))
    check("亮度滑杆已加载", window.sliders.get(0x10) and window.sliders[0x10].spin.text() == "45",
          window.sliders.get(0x10).spin.text() if 0x10 in window.sliders else "缺失")
    check("对比度滑杆已加载", window.sliders.get(0x12) and window.sliders[0x12].spin.text() == "70")
    check("输入源下拉框已加载", 0x60 in window.enums)

    # 拖动亮度
    slider = window.sliders[0x10]
    slider.set_value(80)
    slider.committed.emit(80)
    wait(app, 500)
    check("亮度写入生效", mon0._state[0x10] == 80, str(mon0._state[0x10]))

    # 切换显示器
    window.monitor_list.setCurrentRow(1)
    wait(app, 600)
    check("切换到第二台", window.current is mon1)
    check("第二台亮度独立", window.sliders[0x10].spin.text() == "45",
          window.sliders[0x10].spin.text())

    # 全部同步
    window.sync_btn.setChecked(True)
    s = window.sliders[0x10]
    s.set_value(60)
    s.committed.emit(60)
    wait(app, 700)
    check("同步后第二台为 60", mon1._state[0x10] == 60, str(mon1._state[0x10]))
    check("同步后第一台也变为 60", mon0._state[0x10] == 60, str(mon0._state[0x10]))
    window.sync_btn.setChecked(False)

    # 输入源切换
    window.monitor_list.setCurrentRow(0)
    wait(app, 400)
    row = window.enums[0x60]
    row.set_current(0x0F)
    row.changed.emit(0x0F)
    wait(app, 300)
    check("输入源切换写入", mon0._state[0x60] == 0x0F, str(mon0._state[0x60]))

    # 场景
    from monitorctl import vcp
    window.apply_scene(vcp.SCENES[4])
    wait(app, 900)
    check("场景（夜间）亮度 15%", mon0._state[0x10] == 15, str(mon0._state[0x10]))
    check("场景色彩预设 5000K", mon0._state[0x14] == 0x04, str(mon0._state[0x14]))

    # 对话框
    dlg = VcpBrowserDialog(window.controller, mon0, window)
    dlg.show()
    wait(app, 900)
    dlg.grab().save(os.path.join(BASE, "docs", "vcp-browser.png"))
    dlg.close()

    dlg2 = DiagnosticsDialog(window.controller, mon0, window)
    dlg2.show()
    wait(app, 900)
    dlg2.grab().save(os.path.join(BASE, "docs", "diagnostics.png"))
    dlg2.close()

    dlg3 = SettingsDialog(window.cfg, window)
    dlg3.show()
    wait(app, 400)
    dlg3.grab().save(os.path.join(BASE, "docs", "settings.png"))
    dlg3.close()

    window._closing = True
    window.controller.shutdown()

    print("\n结果：%d 项失败" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
