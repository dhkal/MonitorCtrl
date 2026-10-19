"""开发用：用模拟显示器预览界面（无需真实 DDC/CI 硬件）。

    python tools/preview.py [输出图片路径]
"""

from __future__ import annotations

import os
import sys
import types

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from monitorctl import config, ddc, vcp  # noqa: E402
from monitorctl.main_window import MainWindow  # noqa: E402
from monitorctl.ui import theme  # noqa: E402

CAPS_DELL = (
    "(prot(monitor)type(lcd)model(U2419H)cmds(01 02 03 07 0C E3 F3)"
    "vcp(02 04 05 08 10 12 14(01 04 05 08 0B) 16 18 1A 1E 20 30 3E 52 "
    "60(01 03 0F 11) 62 6C 6E 70 86 87 8A 8D 8E B6 C0 C6 C8 C9 CC "
    "D6(01 04 05) DF E0 E1 E2)mswhql(1)mccs_ver(2.1))"
)
CAPS_LG = (
    "(prot(monitor)type(lcd)model(27GL850)cmds(01 02 03 0C E3 F3)"
    "vcp(02 04 10 12 14(01 02 05 08 0B) 16 18 1A 60(01 11 0F 12) 62 "
    "6C 6E 70 87 8A 8D D6(01 04) DF)mccs_ver(2.2))"
)

DEFAULT_VALUES = {
    0x10: 45, 0x12: 70, 0x62: 30, 0x87: 50, 0x8A: 50, 0x8B: 50,
    0x16: 100, 0x18: 100, 0x1A: 100, 0x6C: 50, 0x6E: 50, 0x70: 50,
    0x14: 0x05, 0x60: 0x11, 0xD6: 0x01, 0x86: 0x01, 0x8D: 0x02,
    0x1E: 50, 0x20: 50, 0x30: 50, 0x3E: 50, 0x52: 50,
    0xC0: 1268, 0xDF: 0x0102, 0xCC: 0x02, 0xB6: 0x03,
}


def make_fake(index: int, name: str, caps: str, device: str, primary: bool,
              width: int, height: int, x: int) -> ddc.Monitor:
    parsed = vcp.parse_capabilities(caps)
    mon = ddc.Monitor(
        index=index,
        hmonitor=0,
        device_name=device,
        description=name,
        friendly_name=parsed.get("model") or name,
        width=width,
        height=height,
        x=x,
        y=0,
        primary=primary,
        edid=ddc.EdidInfo(
            manufacturer="DEL" if "DELL" in name else "GSM",
            product_code=0xA0B1 if "DELL" in name else 0x5B7B,
            serial_text="CN0K3F7N7441" if "DELL" in name else "209NTYK9Q123",
        ),
        handle=1000 + index,
        capabilities_raw=caps,
        supported_vcp=parsed.get("vcp") or {},
        mccs_version=parsed.get("mccs_ver", ""),
        ddc_ok=True,
    )
    state = dict(DEFAULT_VALUES)
    maxes = {
        0x10: 100, 0x12: 100, 0x62: 100, 0x87: 100, 0x8A: 100, 0x8B: 100,
        0x16: 100, 0x18: 100, 0x1A: 100, 0x6C: 100, 0x6E: 100, 0x70: 100,
        0x14: 0x0D, 0x60: 0x12, 0xD6: 0x05, 0x86: 0x04, 0x8D: 0x02,
        0x1E: 100, 0x20: 100, 0x30: 100, 0x3E: 100, 0x52: 100,
        0xC0: 65535, 0xDF: 0xFFFF, 0xCC: 0x20, 0xB6: 0x05,
    }

    def get_vcp(self, code, retries=2):
        if code not in self.supported_vcp:
            raise ddc.DDCError("不支持")
        return state.get(code, 0), maxes.get(code, 100)

    def set_vcp(self, code, value, retries=2):
        if code not in self.supported_vcp:
            raise ddc.DDCError("不支持")
        state[code] = int(value)

    mon._state = state
    mon.brightness = (state[0x10], maxes[0x10])
    mon.get_vcp = types.MethodType(get_vcp, mon)
    mon.set_vcp = types.MethodType(set_vcp, mon)
    mon.close = types.MethodType(lambda self: None, mon)
    return mon


def fake_enumerate(open_handles=True):
    return [
        make_fake(0, "DELL U2419H", CAPS_DELL, "\\\\.\\DISPLAY1", True, 2560, 1440, 0),
        make_fake(1, "LG 27GL850", CAPS_LG, "\\\\.\\DISPLAY2", False, 1920, 1080, 2560),
    ]


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "preview.png")
    ddc.enumerate_monitors = fake_enumerate

    app = QApplication(sys.argv[:1])
    app.setStyleSheet(theme.QSS)
    window = MainWindow(config.Config(os.path.join(BASE, "tools", "_preview_config.json")))
    window.resize(1120, 800)
    window.show()

    def shot():
        window.grab().save(out)
        app.quit()

    QTimer.singleShot(2200, shot)
    app.exec()
    print("saved", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
