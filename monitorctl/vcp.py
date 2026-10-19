"""VCP 代码表 + DDC/CI 能力字符串解析。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

CAT_BRIGHT = "亮度与对比度"
CAT_COLOR = "色彩"
CAT_IMAGE = "图像"
CAT_AUDIO = "音频"
CAT_INPUT = "输入与电源"
CAT_OTHER = "其他"

CATEGORY_ORDER = [CAT_BRIGHT, CAT_COLOR, CAT_IMAGE, CAT_AUDIO, CAT_INPUT, CAT_OTHER]


@dataclass
class VcpDef:
    code: int
    name: str
    category: str = CAT_OTHER
    kind: str = "range"          # range | enum | action
    values: Dict[int, str] = field(default_factory=dict)
    unit: str = ""
    desc: str = ""


# --------------------------------------------------------------------------- #
# 输入源 0x60
# --------------------------------------------------------------------------- #
INPUT_SOURCES: Dict[int, str] = {
    0x01: "模拟 1 (VGA)",
    0x02: "模拟 2",
    0x03: "数字 1 (DVI)",
    0x04: "数字 2 (HDMI)",
    0x05: "数字 3",
    0x06: "数字 4",
    0x07: "数字 5",
    0x08: "数字 6",
    0x09: "数字 7",
    0x0A: "数字 8",
    0x0B: "数字 9",
    0x0C: "数字 10",
    0x0D: "数字 11",
    0x0E: "数字 12",
    0x0F: "DisplayPort 1",
    0x10: "DisplayPort 2",
    0x11: "HDMI 1",
    0x12: "HDMI 2",
    0x13: "USB-C",
    0x14: "Thunderbolt",
    0x15: "DP Alt Mode",
    0x16: "SDI",
    0x17: "分量视频",
    0x18: "复合视频",
    0x19: "S-Video",
}

COLOR_PRESETS: Dict[int, str] = {
    0x01: "sRGB",
    0x02: "原生色域 (Native)",
    0x03: "4000 K",
    0x04: "5000 K",
    0x05: "6500 K",
    0x06: "7500 K",
    0x07: "8200 K",
    0x08: "9300 K",
    0x09: "10000 K",
    0x0A: "11500 K",
    0x0B: "用户 1",
    0x0C: "用户 2",
    0x0D: "用户 3",
}

POWER_MODES: Dict[int, str] = {
    0x01: "开 (On)",
    0x02: "待机 (Standby)",
    0x03: "挂起 (Suspend)",
    0x04: "关机 (Off)",
    0x05: "关机 (Off)",
}

SCALING: Dict[int, str] = {
    0x01: "无缩放 (1:1)",
    0x02: "全屏",
    0x03: "保持比例",
    0x04: "自定义",
}

AUDIO_MUTE: Dict[int, str] = {0x01: "静音", 0x02: "取消静音"}


# --------------------------------------------------------------------------- #
# 主表
# --------------------------------------------------------------------------- #
VCP_TABLE: Dict[int, VcpDef] = {}


def _add(code, name, category, kind="range", values=None, unit="", desc=""):
    VCP_TABLE[code] = VcpDef(code, name, category, kind, values or {}, unit, desc)


_add(0x10, "亮度", CAT_BRIGHT, unit="", desc="背光亮度 (Brightness)")
_add(0x12, "对比度", CAT_BRIGHT, desc="Contrast")
_add(0x16, "红色增益", CAT_COLOR, desc="R 通道增益")
_add(0x18, "绿色增益", CAT_COLOR, desc="G 通道增益")
_add(0x1A, "蓝色增益", CAT_COLOR, desc="B 通道增益")
_add(0x6C, "黑电平 (红)", CAT_COLOR, desc="R 通道黑电平")
_add(0x6E, "黑电平 (绿)", CAT_COLOR, desc="G 通道黑电平")
_add(0x70, "黑电平 (蓝)", CAT_COLOR, desc="B 通道黑电平")
_add(0x14, "色彩预设", CAT_COLOR, "enum", COLOR_PRESETS, desc="色温 / 色彩模式")
_add(0x0C, "色温 (绝对)", CAT_COLOR, unit="K", desc="直接设定色温数值")
_add(0x8A, "饱和度", CAT_COLOR, desc="Saturation")
_add(0x8B, "色相", CAT_COLOR, desc="Hue")
_add(0x87, "锐度", CAT_IMAGE, desc="Sharpness")
_add(0x86, "显示缩放", CAT_IMAGE, "enum", SCALING)
_add(0x8D, "音频静音", CAT_AUDIO, "enum", AUDIO_MUTE)
_add(0x62, "音量", CAT_AUDIO, desc="扬声器音量")
_add(0x64, "麦克风音量", CAT_AUDIO)
_add(0x60, "输入源", CAT_INPUT, "enum", INPUT_SOURCES)
_add(0xD6, "电源模式", CAT_INPUT, "enum", POWER_MODES)
_add(0x04, "恢复出厂设置", CAT_OTHER, "action", desc="部分显示器会立即生效")
_add(0x05, "恢复亮度/对比度出厂值", CAT_OTHER, "action")
_add(0x08, "恢复色彩出厂值", CAT_OTHER, "action")
_add(0x02, "新控制值", CAT_OTHER, desc="显示器端 OSD 操作计数")

# 几何 / 模拟信号调节（老显示器、投影仪上常见）
_add(0x20, "水平位置", CAT_IMAGE)
_add(0x22, "水平尺寸", CAT_IMAGE)
_add(0x24, "水平枕形", CAT_IMAGE)
_add(0x26, "水平枕形平衡", CAT_IMAGE)
_add(0x30, "垂直位置", CAT_IMAGE)
_add(0x32, "垂直尺寸", CAT_IMAGE)
_add(0x34, "垂直枕形", CAT_IMAGE)
_add(0x36, "垂直枕形平衡", CAT_IMAGE)
_add(0x3E, "时钟相位", CAT_IMAGE)
_add(0x40, "水平同步极性", CAT_IMAGE)
_add(0x46, "平行四边形失真", CAT_IMAGE)
_add(0x48, "梯形失真", CAT_IMAGE)
_add(0x4A, "倾斜", CAT_IMAGE)

# 其它有用信息
_add(0xC0, "使用时长", CAT_OTHER, unit="小时", desc="显示器累计点亮时间")
_add(0xC6, "应用使能密钥", CAT_OTHER)
_add(0xC8, "控制器 ID", CAT_OTHER)
_add(0xC9, "固件版本", CAT_OTHER)
_add(0xCC, "OSD 语言", CAT_OTHER)
_add(0xDF, "VCP 版本", CAT_OTHER)
_add(0xAC, "水平频率", CAT_OTHER, unit="Hz")
_add(0xAE, "垂直频率", CAT_OTHER, unit="Hz")


def vcp_name(code: int) -> str:
    d = VCP_TABLE.get(code)
    return d.name if d else "VCP 0x%02X" % code


def vcp_def(code: int) -> VcpDef:
    return VCP_TABLE.get(code) or VcpDef(code, "VCP 0x%02X" % code)


# --------------------------------------------------------------------------- #
# 能力字符串解析
# --------------------------------------------------------------------------- #
def _tokenize(text: str) -> List[str]:
    tokens: List[str] = []
    buf: List[str] = []
    for ch in text:
        if ch == "(":
            if buf:
                tokens.append("".join(buf))
                buf = []
            tokens.append("(")
        elif ch == ")":
            if buf:
                tokens.append("".join(buf))
                buf = []
            tokens.append(")")
        elif ch.isspace():
            if buf:
                tokens.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def _parse_tree(tokens: List[str], pos: int = 0):
    """把 token 流解析成 [(key, [子节点或原子...]), ...] 的结构。"""
    nodes: list = []
    i = pos
    while i < len(tokens):
        tok = tokens[i]
        if tok == ")":
            return nodes, i + 1
        if tok == "(":
            i += 1
            continue
        if i + 1 < len(tokens) and tokens[i + 1] == "(":
            children, i = _parse_tree(tokens, i + 2)
            nodes.append((tok, children))
        else:
            nodes.append((tok, None))
            i += 1
    return nodes, i


def _int_or_none(text: str) -> Optional[int]:
    try:
        return int(text, 16)
    except (TypeError, ValueError):
        return None


def _atoms(args) -> List[str]:
    """把节点参数里的原子取出来（兼容嵌套 (key) 形式）。"""
    out: List[str] = []
    for item in args or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, tuple) and item[0]:
            out.append(str(item[0]))
    return out


def parse_capabilities(raw: str) -> Dict:
    """解析能力字符串，返回 model / mccs_ver / type / cmds / vcp。"""
    result: Dict = {"model": "", "mccs_ver": "", "type": "", "cmds": [], "vcp": {}}
    if not raw:
        return result

    nodes, _ = _parse_tree(_tokenize(raw))
    for key, args in nodes:
        if not isinstance(key, str):
            continue
        name = key.lower()
        if name == "model":
            result["model"] = "".join(_atoms(args))
        elif name == "mccs_ver":
            result["mccs_ver"] = "".join(_atoms(args))
        elif name == "type":
            result["type"] = "".join(_atoms(args))
        elif name == "cmds":
            result["cmds"] = [c for c in (_int_or_none(a) for a in _atoms(args)) if c is not None]
        elif name == "vcp" and args is not None:
            vcp_map: Dict[int, Optional[List[int]]] = {}
            for item in args:
                if isinstance(item, tuple):
                    code = _int_or_none(str(item[0]))
                    if code is None:
                        continue
                    vals = [v for v in (_int_or_none(a) for a in _atoms(item[1])) if v is not None]
                    vcp_map[code] = vals or None
                elif isinstance(item, str):
                    code = _int_or_none(item)
                    if code is not None:
                        vcp_map.setdefault(code, None)
            result["vcp"] = vcp_map
    return result


def ordered_codes(supported: Dict[int, Optional[List[int]]]) -> List[int]:
    """按类别排序，便于界面稳定显示。"""
    def sort_key(code: int):
        d = vcp_def(code)
        cat = CATEGORY_ORDER.index(d.category) if d.category in CATEGORY_ORDER else 99
        known = 0 if code in VCP_TABLE else 1
        return (cat, known, code)

    return sorted(supported.keys(), key=sort_key)


# --------------------------------------------------------------------------- #
# 场景预设（相对百分比）
# --------------------------------------------------------------------------- #
@dataclass
class ScenePreset:
    name: str
    icon: str
    brightness: int
    contrast: int
    color_preset: Optional[int] = None
    gains: Optional[tuple] = None

    @property
    def description(self) -> str:
        return "亮度 %d%% / 对比度 %d%%" % (self.brightness, self.contrast)


SCENES: List[ScenePreset] = [
    ScenePreset("阅读", "book", 70, 55, 0x05, (100, 97, 92)),
    ScenePreset("办公", "desk", 55, 70, 0x05, (100, 100, 100)),
    ScenePreset("游戏", "game", 75, 75, 0x02, (100, 100, 100)),
    ScenePreset("影院", "film", 35, 85, 0x04, (100, 96, 90)),
    ScenePreset("夜间", "moon", 15, 45, 0x04, (100, 88, 78)),
]
