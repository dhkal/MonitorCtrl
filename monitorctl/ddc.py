"""MonitorCtrl - Windows DDC/CI 底层访问层.

基于 dxva2.dll (高等级显示器 API) + user32.dll 实现：
  * 枚举物理显示器（多显示器 / 每台独立句柄）
  * 读取 / 写入任意 VCP 代码
  * 读取显示器 Capabilities String（能力字符串）并解析出支持的 VCP 列表
  * 从注册表 EDID 解析厂商、型号、序列号、生产周

DDC/CI 是串行、慢速（单次 30~150ms）且经常失败的协议，
因此所有调用都带重试 + 每台显示器独立的线程锁。
"""

from __future__ import annotations

import ctypes
import threading
import time
import winreg
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

user32 = ctypes.WinDLL("user32", use_last_error=True)
dxva2 = ctypes.WinDLL("dxva2", use_last_error=True)


# --------------------------------------------------------------------------- #
# Win32 结构体
# --------------------------------------------------------------------------- #
class PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [
        ("hPhysicalMonitor", wintypes.HANDLE),
        ("szPhysicalMonitorDescription", wintypes.WCHAR * 128),
    ]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


MONITORENUMPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HMONITOR,
    wintypes.HDC,
    ctypes.POINTER(wintypes.RECT),
    wintypes.LPARAM,
)

user32.EnumDisplayMonitors.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(wintypes.RECT),
    MONITORENUMPROC,
    wintypes.LPARAM,
]
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFOEXW)]
user32.EnumDisplayDevicesW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.POINTER(DISPLAY_DEVICEW),
    wintypes.DWORD,
]

dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [
    wintypes.HMONITOR,
    ctypes.POINTER(wintypes.DWORD),
]
dxva2.GetPhysicalMonitorsFromHMONITOR.argtypes = [
    wintypes.HMONITOR,
    wintypes.DWORD,
    ctypes.POINTER(PHYSICAL_MONITOR),
]
dxva2.DestroyPhysicalMonitors.argtypes = [
    wintypes.DWORD,
    ctypes.POINTER(PHYSICAL_MONITOR),
]
dxva2.GetVCPFeatureAndVCPFeatureReply.argtypes = [
    wintypes.HANDLE,
    ctypes.c_ubyte,
    ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
]
dxva2.SetVCPFeature.argtypes = [wintypes.HANDLE, ctypes.c_ubyte, wintypes.DWORD]
dxva2.GetCapabilitiesStringLength.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.DWORD),
]
dxva2.CapabilitiesRequestAndCapabilitiesReply.argtypes = [
    wintypes.HANDLE,
    ctypes.c_char_p,
    wintypes.DWORD,
]

MONITORINFOF_PRIMARY = 0x00000001


# --------------------------------------------------------------------------- #
# 异常
# --------------------------------------------------------------------------- #
class DDCError(Exception):
    """DDC/CI 调用失败。"""

    def __init__(self, message: str, code: int = 0):
        super().__init__(message)
        self.code = code


class DDCTimeout(DDCError):
    pass


_WIN32_HINTS = {
    5: "拒绝访问",
    31: "显示器没有响应（DDC/CI 被关闭，或被转接器 / 扩展坞屏蔽）",
    50: "该控制项不被这台显示器支持",
    87: "参数无效",
    1167: "设备未连接",
    121: "操作超时（显示器没有回应 DDC 请求）",
}


def explain_error(code: int) -> str:
    """把 Win32 错误码翻译成可读原因。"""
    hint = _WIN32_HINTS.get(code)
    return ("%s（错误码 %d）" % (hint, code)) if hint else ("错误码 %d" % code)


# --------------------------------------------------------------------------- #
# 注册表 EDID 解析
# --------------------------------------------------------------------------- #
@dataclass
class EdidInfo:
    manufacturer: str = ""
    product_code: int = 0
    serial_number: int = 0
    week: int = 0
    year: int = 0
    name: str = ""
    serial_text: str = ""

    @property
    def mfg_id(self) -> str:
        return self.manufacturer or "UNK"


def _decode_edid(blob: bytes) -> EdidInfo:
    info = EdidInfo()
    if len(blob) < 128 or blob[:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        return info
    # 厂商 ID: 3 个 5bit 字母
    raw = (blob[8] << 8) | blob[9]
    info.manufacturer = "".join(
        chr(ord("A") + ((raw >> shift) & 0x1F) - 1) for shift in (10, 5, 0)
    )
    info.product_code = blob[10] | (blob[11] << 8)
    info.serial_number = int.from_bytes(blob[12:16], "little")
    info.week = blob[16]
    info.year = 1990 + blob[17]

    for offset in (54, 72, 90, 108):
        d = blob[offset : offset + 18]
        if len(d) < 18:
            break
        if d[0] == 0 and d[1] == 0 and d[2] == 0 and d[3] == 0xFC:
            text = d[5:18].split(b"\x0a")[0].replace(b"\x00", b"")
            info.name = text.decode("ascii", "ignore").strip()
        elif d[0] == 0 and d[1] == 0 and d[2] == 0 and d[3] == 0xFF:
            text = d[5:18].split(b"\x0a")[0].replace(b"\x00", b"")
            info.serial_text = text.decode("ascii", "ignore").strip()
    return info


_EDID_CACHE: Dict[str, EdidInfo] = {}


def edid_from_device_id(device_id: str) -> EdidInfo:
    """通过 EnumDisplayDevices 返回的 DeviceID 在注册表中找到对应 EDID。

    DeviceID 形如 ``MONITOR\\GSM5B7B\\{4d36e96e-...}\\0001``，
    注册表实例键名与之不同，但实例键的 ``Driver`` 值等于后两段。
    """
    if not device_id:
        return EdidInfo()
    if device_id in _EDID_CACHE:
        return _EDID_CACHE[device_id]

    parts = device_id.split("\\")
    if len(parts) < 4:
        return EdidInfo()
    mfg, driver = parts[1], "\\".join(parts[2:4])
    result = EdidInfo()
    base = r"SYSTEM\CurrentControlSet\Enum\DISPLAY\%s" % mfg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as key:
            count = winreg.QueryInfoKey(key)[0]
            for i in range(count):
                try:
                    inst = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, inst) as ikey:
                        try:
                            drv, _ = winreg.QueryValueEx(ikey, "Driver")
                        except OSError:
                            drv = ""
                        if drv and drv.lower() != driver.lower():
                            continue
                        with winreg.OpenKey(
                            ikey, r"Device Parameters"
                        ) as pkey:
                            blob, _ = winreg.QueryValueEx(pkey, "EDID")
                            if isinstance(blob, bytes):
                                result = _decode_edid(blob)
                                if result.manufacturer:
                                    _EDID_CACHE[device_id] = result
                                    return result
                except OSError:
                    continue
    except OSError:
        pass
    _EDID_CACHE[device_id] = result
    return result


# --------------------------------------------------------------------------- #
# 显示器对象
# --------------------------------------------------------------------------- #
@dataclass
class Monitor:
    index: int
    hmonitor: int
    device_name: str          # \\.\DISPLAY1
    description: str          # 物理显示器描述（驱动给的名字）
    friendly_name: str
    width: int
    height: int
    x: int
    y: int
    primary: bool
    edid: EdidInfo = field(default_factory=EdidInfo)

    handle: int = 0
    capabilities_raw: str = ""
    supported_vcp: Dict[int, Optional[List[int]]] = field(default_factory=dict)
    mccs_version: str = ""
    cmds: List[int] = field(default_factory=list)
    ddc_ok: bool = False
    last_error: str = ""
    brightness: Optional[Tuple[int, int]] = None
    probe: Dict = field(default_factory=dict)

    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _phys: Optional[PHYSICAL_MONITOR] = field(default=None, repr=False)

    # -- 基本信息 -------------------------------------------------------- #
    @property
    def key(self) -> str:
        """跨会话稳定的标识（用于配置文件）。"""
        e = self.edid
        if e.manufacturer:
            return "%s-%04X-%s" % (e.manufacturer, e.product_code, e.serial_text or e.serial_number)
        return self.device_name

    @property
    def resolution(self) -> str:
        return "%d x %d" % (self.width, self.height)

    @property
    def display_name(self) -> str:
        return self.friendly_name or self.description or self.device_name

    def supports(self, code: int) -> bool:
        if not self.supported_vcp:
            return True
        return code in self.supported_vcp

    # -- VCP 读写 -------------------------------------------------------- #
    def get_vcp(self, code: int, retries: int = 2) -> Tuple[int, int]:
        """返回 (当前值, 最大值)。"""
        if not self.handle:
            raise DDCError("显示器未打开")
        last = None
        for attempt in range(retries + 1):
            vct = ctypes.c_int(0)
            cur = wintypes.DWORD(0)
            mx = wintypes.DWORD(0)
            with self._lock:
                ok = dxva2.GetVCPFeatureAndVCPFeatureReply(
                    self.handle, code, ctypes.byref(vct), ctypes.byref(cur), ctypes.byref(mx)
                )
                err = ctypes.get_last_error()
            if ok:
                return int(cur.value), int(mx.value)
            last = err
            if attempt < retries:
                time.sleep(0.05)
        raise DDCError(
            "读取 VCP 0x%02X 失败：%s" % (code, explain_error(last or 0)), last or 0
        )

    def set_vcp(self, code: int, value: int, retries: int = 2) -> None:
        if not self.handle:
            raise DDCError("显示器未打开")
        last = None
        for attempt in range(retries + 1):
            with self._lock:
                ok = dxva2.SetVCPFeature(self.handle, code, int(value))
                err = ctypes.get_last_error()
            if ok:
                return
            last = err
            if attempt < retries:
                time.sleep(0.05)
        raise DDCError(
            "写入 VCP 0x%02X=%d 失败：%s" % (code, value, explain_error(last or 0)), last or 0
        )

    # -- 能力字符串 ------------------------------------------------------ #
    def read_capabilities(self) -> str:
        if not self.handle:
            return ""
        length = wintypes.DWORD(0)
        with self._lock:
            ok = dxva2.GetCapabilitiesStringLength(self.handle, ctypes.byref(length))
        if not ok or length.value <= 1:
            return ""
        buf = ctypes.create_string_buffer(length.value + 1)
        with self._lock:
            ok = dxva2.CapabilitiesRequestAndCapabilitiesReply(
                self.handle, buf, length.value
            )
        if not ok:
            return ""
        return buf.value.decode("ascii", "ignore").strip("\x00")

    # -- 常用快捷方法 ---------------------------------------------------- #
    def get_brightness(self) -> Tuple[int, int]:
        return self.get_vcp(0x10)

    def set_brightness(self, value: int) -> None:
        self.set_vcp(0x10, value)

    def close(self) -> None:
        if self._phys is not None:
            try:
                arr = (PHYSICAL_MONITOR * 1)(self._phys)
                dxva2.DestroyPhysicalMonitors(1, arr)
            except Exception:
                pass
            self._phys = None
        self.handle = 0


# --------------------------------------------------------------------------- #
# 枚举
# --------------------------------------------------------------------------- #
def _enum_hmonitors() -> List[Tuple[int, MONITORINFOEXW]]:
    found: List[Tuple[int, MONITORINFOEXW]] = []

    def _cb(hmon, hdc, lprc, data):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            found.append((hmon, info))
        return True

    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_cb), 0)
    return found


def _device_strings(device_name: str) -> Tuple[str, str]:
    """返回该显示器的 (DeviceString, DeviceID)。"""
    dd = DISPLAY_DEVICEW()
    dd.cb = ctypes.sizeof(DISPLAY_DEVICEW)
    if user32.EnumDisplayDevicesW(device_name, 0, ctypes.byref(dd), 0):
        return dd.DeviceString, dd.DeviceID
    return "", ""


# 能力字符串缺失时，主动试读这些标准控制项（覆盖亮度/对比度/色彩/音频/输入/电源）
DEFAULT_PROBE_CODES = [
    0x10, 0x12, 0x14, 0x16, 0x18, 0x1A, 0x0C, 0x6C, 0x6E, 0x70,
    0x87, 0x8A, 0x8B, 0x86, 0x62, 0x8D, 0x60, 0xD6,
]


def probe_vcp(mon: "Monitor", codes: Optional[List[int]] = None) -> Dict[int, Optional[List[int]]]:
    """逐个试读 VCP，返回真正有响应的代码集合。

    不少杂牌显示器不实现能力字符串（Capabilities String），
    但控制项其实可用，这里靠试读把界面补全。
    """
    found: Dict[int, Optional[List[int]]] = {}
    for code in codes or DEFAULT_PROBE_CODES:
        try:
            _cur, mx = mon.get_vcp(code, retries=0)
        except DDCError:
            continue
        if mx > 0:
            found[code] = None
    return found


def _acquire_physical(hmon, attempts: int = 3):
    """带重试地拿到物理显示器数组。

    某些显卡驱动（尤其接了 KVM / 扩展坞 / 杂牌屏）第一次调用会返回空句柄，
    隔一百多毫秒再枚举一次往往就正常了，所以这里重试三次。
    """
    probe: Dict = {"hmonitor": int(hmon or 0), "steps": [], "count": 0}
    for attempt in range(attempts):
        count = wintypes.DWORD(0)
        ok = dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(count))
        err = ctypes.get_last_error()
        step = {
            "attempt": attempt + 1,
            "num_ok": bool(ok),
            "num_err": err,
            "count": int(count.value),
        }
        if ok and count.value > 0:
            arr = (PHYSICAL_MONITOR * count.value)()
            ok2 = dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, count.value, arr)
            err2 = ctypes.get_last_error()
            step["get_ok"] = bool(ok2)
            step["get_err"] = err2
            step["handles"] = [int(m.hPhysicalMonitor or 0) for m in arr]
            probe["steps"].append(step)
            if ok2 and any(step["handles"]):
                probe["count"] = int(count.value)
                return arr, int(count.value), probe
        else:
            probe["steps"].append(step)
        time.sleep(0.12)
    return None, 0, probe


def _acquire_error(probe: Dict) -> str:
    steps = probe.get("steps") or []
    if not steps:
        return "未能获取物理显示器"
    last = steps[-1]
    if not last.get("num_ok", False):
        return "GetNumberOfPhysicalMonitorsFromHMONITOR 失败（错误码 %d）" % last.get("num_err", 0)
    if last.get("count", 0) == 0:
        return "该显示输出没有物理显示器（虚拟机 / 远程桌面 / 虚拟显示驱动）"
    if not last.get("get_ok", False):
        return "GetPhysicalMonitorsFromHMONITOR 失败（错误码 %d）" % last.get("get_err", 0)
    return "系统返回的显示器句柄为空（显卡驱动没有提供 DDC 通道，或显示器 EDID 异常）"


def enumerate_monitors(open_handles: bool = True) -> List[Monitor]:
    """枚举所有物理显示器（带重试与详细探针信息）。"""
    monitors: List[Monitor] = []
    for _idx, (hmon, info) in enumerate(_enum_hmonitors()):
        device = info.szDevice
        dev_string, dev_id = _device_strings(device)
        edid = edid_from_device_id(dev_id)
        common = dict(
            index=len(monitors),
            hmonitor=hmon,
            device_name=device,
            width=info.rcMonitor.right - info.rcMonitor.left,
            height=info.rcMonitor.bottom - info.rcMonitor.top,
            x=info.rcMonitor.left,
            y=info.rcMonitor.top,
            primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
            edid=edid,
        )

        arr, count, probe = _acquire_physical(hmon)
        if arr is None:
            monitors.append(
                Monitor(
                    description=dev_string or "未知显示器",
                    friendly_name=edid.name or dev_string or device,
                    last_error=_acquire_error(probe),
                    probe=probe,
                    **common,
                )
            )
            continue

        for sub in range(count):
            phys = arr[sub]
            desc = phys.szPhysicalMonitorDescription or dev_string
            name = edid.name or desc or device
            if count > 1:
                name = "%s (%d)" % (name, sub + 1)
            mon = Monitor(
                description=desc,
                friendly_name=name,
                handle=int(phys.hPhysicalMonitor or 0),
                _phys=phys,
                probe=probe,
                **common,
            )
            mon.index = len(monitors)
            if open_handles:
                if not mon.handle:
                    mon.last_error = _acquire_error(probe)
                    monitors.append(mon)
                    continue
                try:
                    mon.capabilities_raw = mon.read_capabilities()
                except Exception as exc:  # pragma: no cover
                    mon.last_error = str(exc)
                try:
                    cur, mx = mon.get_vcp(0x10, retries=1)
                    mon.brightness = (cur, mx)
                    mon.ddc_ok = mx > 0
                    if not mon.ddc_ok:
                        mon.last_error = "显示器返回最大值为 0，可能未启用 DDC/CI"
                except DDCError as exc:
                    mon.ddc_ok = False
                    mon.last_error = str(exc)
                if mon.ddc_ok and not mon.supported_vcp:
                    # 没有能力字符串：试读标准控制项，尽量把界面补全
                    mon.supported_vcp = probe_vcp(mon)
            monitors.append(mon)
    return monitors


def format_report(monitors: List[Monitor], app_version: str = "") -> str:
    """生成可复制的纯文本诊断报告。"""
    import platform

    lines: List[str] = []
    lines.append("MonitorCtrl 诊断报告" + ("  v" + app_version if app_version else ""))
    lines.append("时间: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append(
        "系统: %s %s (build %s)  Python %s"
        % (platform.system(), platform.release(), platform.version(), platform.python_version())
    )
    if not monitors:
        lines.append("未枚举到任何显示器")
        return "\n".join(lines)

    for mon in monitors:
        lines.append("")
        lines.append("[%d] %s" % (mon.index, mon.display_name))
        lines.append(
            "    输出: %s   分辨率: %s   %s"
            % (mon.device_name, mon.resolution, "主显示器" if mon.primary else "")
        )
        lines.append("    HMONITOR: 0x%X" % (mon.hmonitor or 0))
        lines.append("    物理显示器句柄: %s" % (("0x%X" % mon.handle) if mon.handle else "空"))
        for step in (mon.probe or {}).get("steps", []):
            lines.append(
                "    尝试%d: 数量=%d (ok=%s,err=%d)  获取=%s (ok=%s,err=%s)  句柄=%s"
                % (
                    step.get("attempt", 0),
                    step.get("count", 0),
                    step.get("num_ok"),
                    step.get("num_err", 0),
                    "成功" if step.get("get_ok") else ("失败" if "get_ok" in step else "未调用"),
                    step.get("get_ok"),
                    step.get("get_err", "-"),
                    [hex(h) for h in step.get("handles", [])] or "-",
                )
            )
        lines.append("    DDC/CI: %s" % ("可用" if mon.ddc_ok else "不可用"))
        if mon.last_error:
            lines.append("    原因: %s" % mon.last_error)
        e = mon.edid
        lines.append(
            "    EDID: 厂商=%s  产品=0x%04X  序列号=%s  生产=%s"
            % (
                e.manufacturer or "未读到",
                e.product_code,
                e.serial_text or (e.serial_number or "无"),
                ("%d年第%d周" % (e.year, e.week)) if e.year else "未知",
            )
        )
        lines.append("    MCCS 版本: %s   支持 VCP: %d 项" % (mon.mccs_version or "未知", len(mon.supported_vcp)))
        lines.append("    Capabilities: %s" % (mon.capabilities_raw or "(显示器未返回)"))
    return "\n".join(lines)


def restore_factory_defaults(mon: Monitor) -> None:
    """VCP 0x04：恢复出厂设置（部分显示器不支持）。"""
    mon.set_vcp(0x04, 0x01)


