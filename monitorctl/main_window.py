"""主窗口。"""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QAbstractNativeEventFilter, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from . import config, ddc, vcp
from .controller import Controller
from .ui import theme, widgets
from .ui.dialogs import DiagnosticsDialog, SettingsDialog, VcpBrowserDialog

APP_VERSION = "1.0.3"

user32 = ctypes.WinDLL("user32", use_last_error=True)
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
WM_HOTKEY = 0x0312
VK_UP, VK_DOWN, VK_LEFT, VK_RIGHT = 0x26, 0x28, 0x25, 0x27


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, handler):
        super().__init__()
        self.handler = handler

    def nativeEventFilter(self, eventType, message):  # noqa: N802
        try:
            if eventType in (b"windows_generic_MSG", "windows_generic_MSG"):
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY:
                    self.handler(int(msg.wParam))
                    return True, 0
        except Exception:
            pass
        return False, 0


class MainWindow(QMainWindow):
    def __init__(self, cfg: config.Config):
        super().__init__()
        self.cfg = cfg
        self.controller = Controller(self)
        self.monitors: List[ddc.Monitor] = []
        self.current: Optional[ddc.Monitor] = None
        self.cards: Dict[str, widgets.MonitorCard] = {}

        self.sliders: Dict[int, widgets.VcpSlider] = {}
        self.enums: Dict[int, widgets.EnumRow] = {}
        self.shown_codes: set = set()
        self.cache: Dict[Tuple[str, int], Tuple[int, int]] = {}
        self.pending: Dict[Tuple[str, int], int] = {}
        self._closing = False
        self._scanning = False
        self._hotkey_ids: List[int] = []

        self.setWindowTitle("显示器控制 · DDC/CI")
        self.setWindowIcon(QIcon(widgets.make_pixmap("monitor", 64)))
        self.resize(1100, 780)
        self.setMinimumSize(940, 640)

        self._build_ui()
        self._build_tray()

        self.write_timer = QTimer(self)
        self.write_timer.setSingleShot(True)
        self.write_timer.setInterval(70)
        self.write_timer.timeout.connect(self._flush_writes)

        self._last_write = 0.0
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(5000)
        self.poll_timer.timeout.connect(self._poll_values)

        self._apply_settings()

        self.controller.monitorScanned.connect(self._on_scanned)
        self.controller.scanFailed.connect(self._on_scan_failed)

        self.hotkey_filter = HotkeyFilter(self._on_hotkey)
        QApplication.instance().installNativeEventFilter(self.hotkey_filter)

        QTimer.singleShot(80, self.rescan)

    # ================================================================== #
    # 界面搭建
    # ================================================================== #
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_sidebar())

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(22, 18, 22, 14)
        main_layout.setSpacing(12)
        main_layout.addLayout(self._build_header())

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("Content")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 6, 0)
        self.content_layout.setSpacing(12)
        self.content_layout.addStretch(1)
        self.scroll.setWidget(self.content)
        main_layout.addWidget(self.scroll, 1)

        outer.addWidget(main, 1)

        self.toast = widgets.Toast(root)

        bar = self.statusBar()
        bar.setSizeGripEnabled(False)
        bar.setStyleSheet("QStatusBar { padding-left: 12px; }")
        spacer = QWidget()
        spacer.setFixedWidth(12)
        bar.addWidget(spacer)
        self.status_label = QLabel("正在检测显示器…")
        bar.addWidget(self.status_label, 1)
        self.hint_label = QLabel("Ctrl+Alt+↑/↓ 亮度　Ctrl+Alt+←/→ 对比度")
        self.hint_label.setStyleSheet("color:#9aa3b2; font-size:11px;")
        bar.addPermanentWidget(self.hint_label)

    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(268)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(16, 20, 16, 16)
        lay.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(widgets.make_pixmap("monitor", 30, theme.ACCENT))
        head.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        t1 = QLabel("显示器控制")
        t1.setObjectName("H1")
        t1.setStyleSheet("font-size:17px;")
        titles.addWidget(t1)
        t2 = QLabel("DDC/CI 硬件级调节")
        t2.setStyleSheet("color:#9aa3b2; font-size:11px;")
        titles.addWidget(t2)
        head.addLayout(titles)
        head.addStretch(1)
        lay.addLayout(head)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background:#eef1f6;")
        lay.addWidget(line)

        self.list_label = QLabel("显示器")
        self.list_label.setObjectName("SectionTitle")
        lay.addWidget(self.list_label)

        self.monitor_list = QListWidget()
        self.monitor_list.setSelectionMode(QListWidget.SingleSelection)
        self.monitor_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.monitor_list.currentRowChanged.connect(self._on_row_changed)
        lay.addWidget(self.monitor_list, 1)

        self.refresh_btn = QPushButton("重新检测显示器")
        self.refresh_btn.setObjectName("Primary")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.rescan)
        lay.addWidget(self.refresh_btn)

        bottom = QHBoxLayout()
        self.settings_btn = QPushButton("  设置")
        self.settings_btn.setIcon(widgets.make_icon("gear", 16, theme.MUTED))
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_settings)
        bottom.addWidget(self.settings_btn, 1)
        lay.addLayout(bottom)

        ver = QLabel("v%s" % APP_VERSION)
        ver.setStyleSheet("color:#b6bdc9; font-size:10px;")
        ver.setAlignment(Qt.AlignCenter)
        lay.addWidget(ver)
        return side

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        left = QVBoxLayout()
        left.setSpacing(2)
        self.title_label = QLabel("未检测到显示器")
        self.title_label.setObjectName("H1")
        left.addWidget(self.title_label)
        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet("color:#8a93a3; font-size:11px;")
        left.addWidget(self.subtitle_label)
        row.addLayout(left)
        row.addStretch(1)

        self.sync_btn = QPushButton("  全部同步")
        self.sync_btn.setObjectName("Chip")
        self.sync_btn.setCheckable(True)
        self.sync_btn.setIcon(widgets.make_icon("check", 14, theme.MUTED))
        self.sync_btn.setToolTip("开启后，亮度与对比度的调整会按比例同步到所有显示器")
        self.sync_btn.setCursor(Qt.PointingHandCursor)
        self.sync_btn.toggled.connect(self._on_sync_toggled)
        row.addWidget(self.sync_btn)

        self.scene_btn = QPushButton("  场景")
        self.scene_btn.setObjectName("Chip")
        self.scene_btn.setIcon(widgets.make_icon("sun", 14, theme.MUTED))
        self.scene_btn.setCursor(Qt.PointingHandCursor)
        self.scene_btn.setMenu(self._build_scene_menu())
        row.addWidget(self.scene_btn)

        self.profile_btn = QPushButton("  配置文件")
        self.profile_btn.setObjectName("Chip")
        self.profile_btn.setIcon(widgets.make_icon("save", 14, theme.MUTED))
        self.profile_btn.setCursor(Qt.PointingHandCursor)
        self.profile_menu = QMenu(self)
        self.profile_menu.aboutToShow.connect(self._rebuild_profile_menu)
        self.profile_btn.setMenu(self.profile_menu)
        row.addWidget(self.profile_btn)

        self.more_btn = QPushButton()
        self.more_btn.setObjectName("Chip")
        self.more_btn.setIcon(widgets.make_icon("gear", 14, theme.MUTED))
        self.more_btn.setCursor(Qt.PointingHandCursor)
        self.more_btn.setFixedWidth(38)
        self.more_btn.setMenu(self._build_more_menu())
        row.addWidget(self.more_btn)
        return row

    def _build_scene_menu(self) -> QMenu:
        menu = QMenu(self)
        for scene in vcp.SCENES:
            act = QAction(scene.name, menu)
            act.setToolTip(scene.description)
            act.triggered.connect(lambda _=False, s=scene: self.apply_scene(s))
            menu.addAction(act)
        menu.addSeparator()
        info = QAction("应用到：当前显示器 / 全部（取决于“全部同步”）", menu)
        info.setEnabled(False)
        menu.addAction(info)
        return menu

    def _build_more_menu(self) -> QMenu:
        menu = QMenu(self)
        act_vcp = QAction("VCP 浏览器…", menu)
        act_vcp.triggered.connect(self.open_vcp_browser)
        menu.addAction(act_vcp)
        act_diag = QAction("显示器诊断…", menu)
        act_diag.triggered.connect(self.open_diagnostics)
        menu.addAction(act_diag)
        menu.addSeparator()
        act_dir = QAction("打开配置目录", menu)
        act_dir.triggered.connect(self._open_config_dir)
        menu.addAction(act_dir)
        act_set = QAction("设置…", menu)
        act_set.triggered.connect(self.open_settings)
        menu.addAction(act_set)
        menu.addSeparator()
        act_about = QAction("关于 MonitorCtrl", menu)
        act_about.triggered.connect(self._about)
        menu.addAction(act_about)
        menu.addSeparator()
        act_quit = QAction("退出 MonitorCtrl", menu)
        act_quit.triggered.connect(self.quit_app)
        menu.addAction(act_quit)
        return menu

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(QIcon(widgets.make_pixmap("monitor", 64)), self)
        self.tray.setToolTip("显示器控制")
        menu = QMenu(self)
        act_show = QAction("显示主界面", menu)
        act_show.triggered.connect(self._show_window)
        menu.addAction(act_show)
        menu.addSeparator()
        act_up = QAction("亮度 +5%", menu)
        act_up.triggered.connect(lambda: self._nudge(0x10, +1))
        menu.addAction(act_up)
        act_down = QAction("亮度 -5%", menu)
        act_down.triggered.connect(lambda: self._nudge(0x10, -1))
        menu.addAction(act_down)
        menu.addSeparator()
        scenes = menu.addMenu("场景")
        for scene in vcp.SCENES:
            a = QAction(scene.name, scenes)
            a.triggered.connect(lambda _=False, s=scene: self.apply_scene(s))
            scenes.addAction(a)
        menu.addSeparator()
        act_quit = QAction("退出", menu)
        act_quit.triggered.connect(self.quit_app)
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)

    def _apply_settings(self) -> None:
        if self.cfg.get("tray"):
            self.tray.show()
        self._register_hotkeys()
        if self.cfg.get("poll_interval"):
            self.poll_timer.start()
        else:
            self.poll_timer.stop()

    # ================================================================== #
    # 显示器扫描
    # ================================================================== #
    def rescan(self) -> None:
        if self._scanning:
            return
        self._scanning = True
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("正在检测…")
        self.status_label.setText("正在枚举显示器并读取 DDC/CI 能力…")
        self.controller.scan()

    def _on_scan_failed(self, message: str) -> None:
        self._scanning = False
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("重新检测显示器")
        self.status_label.setText("检测失败：%s" % message)

    def _on_scanned(self, monitors: List[ddc.Monitor]) -> None:
        previous_key = self.current.key if self.current else None
        self._scanning = False
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("重新检测显示器")
        self.monitors = monitors
        self.cards = {}
        self.monitor_list.blockSignals(True)
        self.monitor_list.clear()
        for mon in monitors:
            item = QListWidgetItem()
            item.setSizeHint(QSize(236, 84))
            card = widgets.MonitorCard(mon.index, mon.display_name, self._card_subtitle(mon))
            card.set_primary(mon.primary)
            card.set_ok(mon.ddc_ok)
            if mon.ddc_ok and mon.brightness:
                card.set_brightness(*mon.brightness)
                self.cache[(mon.key, 0x10)] = mon.brightness
            self.monitor_list.addItem(item)
            self.monitor_list.setItemWidget(item, card)
            self.cards[mon.key] = card
        self.monitor_list.blockSignals(False)

        self.list_label.setText("显示器 · %d 台" % len(monitors))

        if not monitors:
            self.current = None
            self.title_label.setText("未检测到显示器")
            self.subtitle_label.setText("请检查显示器连接，或在 OSD 菜单中启用 DDC/CI")
            self._clear_content()
            self._add_empty_state()
            self.status_label.setText("未检测到显示器")
            return

        target = 0
        if previous_key:
            for i, mon in enumerate(monitors):
                if mon.key == previous_key:
                    target = i
                    break
        self.monitor_list.setCurrentRow(target)
        if self.current is not monitors[target]:
            self._on_row_changed(target)

        ok_count = sum(1 for m in monitors if m.ddc_ok)
        self.status_label.setText(
            "已连接 %d 台显示器，其中 %d 台 DDC/CI 可用" % (len(monitors), ok_count)
        )

        if self.cfg.get("apply_last_on_start") and previous_key is None:
            self._restore_last_state()

    def _card_subtitle(self, mon: ddc.Monitor) -> str:
        parts = [mon.resolution, mon.device_name.replace("\\\\.\\", "")]
        if mon.mccs_version:
            parts.append("MCCS " + mon.mccs_version)
        return " · ".join(parts)

    def _on_row_changed(self, row: int) -> None:
        if row < 0 or row >= len(self.monitors):
            return
        mon = self.monitors[row]
        self.current = mon
        self.title_label.setText(mon.display_name)
        bits = [mon.resolution, mon.device_name]
        if mon.primary:
            bits.append("主显示器")
        if mon.edid.serial_text:
            bits.append("SN " + mon.edid.serial_text)
        self.subtitle_label.setText("　·　".join(bits))
        self._build_content(mon)

    # ================================================================== #
    # 内容区
    # ================================================================== #
    def _clear_content(self) -> None:
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.sliders.clear()
        self.enums.clear()
        self.shown_codes.clear()

    def _add_card(self, card: QWidget) -> QWidget:
        self.content_layout.insertWidget(self.content_layout.count() - 1, card)
        return card

    def _add_empty_state(self) -> None:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 30, 24, 30)
        lay.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(widgets.make_pixmap("warning", 48, "#c7cedb"))
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)
        t = QLabel("没有可控制的显示器")
        t.setObjectName("H2")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        d = QLabel(
            "如果是笔记本内置屏幕或虚拟机，通常不支持 DDC/CI。\n"
            "外接显示器需要在 OSD 菜单里开启 “DDC/CI”，并尽量使用 HDMI / DP 直连。"
        )
        d.setObjectName("Muted")
        d.setAlignment(Qt.AlignCenter)
        d.setWordWrap(True)
        lay.addWidget(d)
        self._add_card(card)

    def _build_content(self, mon: ddc.Monitor) -> None:
        self._clear_content()

        if not mon.ddc_ok:
            self._add_card(self._build_warning_card(mon))
            self._add_card(self._build_help_card())
            return

        supported = mon.supported_vcp
        codes = set(supported) if supported else set()

        # ---- 快速调节 -------------------------------------------------- #
        quick = widgets.SectionCard("快速调节")
        rows = 0
        for code in (0x10, 0x12):
            if not codes or code in codes:
                quick.add_widget(self._make_slider(code))
                rows += 1
        if 0x62 in codes:
            quick.add_widget(self._make_slider(0x62, "音量"))
            rows += 1
        if 0x8D in codes:
            row = self._make_enum(0x8D, "静音")
            quick.add_widget(row)
            rows += 1
        if rows == 0:
            quick.add_widget(self._muted_label("该显示器没有报告任何常用控制项"))
        self._add_card(quick)

        # ---- 图像 ------------------------------------------------------ #
        image_codes = [0x87, 0x8A, 0x8B, 0x86, 0x20, 0x30, 0x3E, 0x4A]
        image_codes = [c for c in image_codes if c in codes and c not in self.shown_codes]
        if image_codes:
            card = widgets.SectionCard("图像")
            for code in image_codes:
                if vcp.vcp_def(code).kind == "enum":
                    card.add_widget(self._make_enum(code))
                else:
                    card.add_widget(self._make_slider(code))
            self._add_card(card)

        # ---- 色彩 ------------------------------------------------------ #
        color_codes = [0x14, 0x0C, 0x16, 0x18, 0x1A, 0x6C, 0x6E, 0x70]
        color_codes = [c for c in color_codes if c in codes and c not in self.shown_codes]
        if color_codes:
            card = widgets.SectionCard("色彩")
            for code in color_codes:
                if vcp.vcp_def(code).kind == "enum":
                    card.add_widget(self._make_enum(code))
                else:
                    card.add_widget(self._make_slider(code))
            self._add_card(card)

        # ---- 输入与电源 ------------------------------------------------ #
        io_codes = [0x60, 0xD6]
        io_codes = [c for c in io_codes if c in codes and c not in self.shown_codes]
        card = widgets.SectionCard("输入与电源")
        for code in io_codes:
            card.add_widget(self._make_enum(code))
        if not io_codes:
            card.add_widget(self._muted_label("该显示器未提供输入源 / 电源模式控制"))
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        restore = QPushButton("恢复出厂设置")
        restore.setCursor(Qt.PointingHandCursor)
        restore.clicked.connect(self._restore_defaults)
        action_row.addWidget(restore)
        card.add_layout(action_row)
        self._add_card(card)

        # ---- 其它 VCP -------------------------------------------------- #
        rest = [c for c in vcp.ordered_codes(supported) if c not in self.shown_codes]
        if rest:
            card = widgets.SectionCard("其它控制项")
            for code in rest[:16]:
                d = vcp.vcp_def(code)
                if d.kind == "action":
                    continue
                if d.kind == "enum":
                    card.add_widget(self._make_enum(code))
                else:
                    card.add_widget(self._make_slider(code))
            if len(rest) > 16:
                more = QPushButton("还有 %d 项，打开 VCP 浏览器查看" % (len(rest) - 16))
                more.setObjectName("Ghost")
                more.setCursor(Qt.PointingHandCursor)
                more.clicked.connect(self.open_vcp_browser)
                card.add_widget(more)
            self._add_card(card)

        self._load_values(mon)

    def _build_warning_card(self, mon: ddc.Monitor) -> QWidget:
        card = QFrame()
        card.setObjectName("WarnCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 13, 16, 14)
        lay.setSpacing(6)
        head = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(widgets.make_pixmap("warning", 18, theme.WARN))
        head.addWidget(icon)
        t = QLabel("DDC/CI 不可用")
        t.setStyleSheet("font-weight:600; color:#92400e;")
        head.addWidget(t)
        head.addStretch(1)
        lay.addLayout(head)
        msg = QLabel(
            (mon.last_error or "显示器没有响应 DDC/CI 请求。")
            + "\n请确认：显示器 OSD 菜单中已开启 DDC/CI；使用 HDMI / DP 直连（部分扩展坞、转接器会屏蔽 DDC 通道）。"
        )
        msg.setWordWrap(True)
        msg.setStyleSheet("color:#92400e; font-size:12px;")
        lay.addWidget(msg)

        row = QHBoxLayout()
        row.addStretch(1)
        copy_btn = QPushButton("复制诊断报告")
        copy_btn.clicked.connect(self.copy_diagnostic_report)
        row.addWidget(copy_btn)
        diag_btn = QPushButton("运行深度诊断")
        diag_btn.setObjectName("Primary")
        diag_btn.clicked.connect(self.open_diagnostics)
        row.addWidget(diag_btn)
        lay.addLayout(row)
        return card

    def _build_help_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 13, 16, 14)
        lay.setSpacing(6)
        title = QLabel("排查步骤")
        title.setObjectName("SectionTitle")
        lay.addWidget(title)
        steps = QLabel(
            "1. 在显示器 OSD 菜单中打开「DDC/CI」<br>"
            "2. 改用 HDMI / DisplayPort 直连，绕开扩展坞、KVM、转接器<br>"
            "3. 关闭显示器的「节能模式 / DisplayPort 深度休眠」<br>"
            "4. 在显卡控制面板中确认输出未经过虚拟显示驱动<br>"
            "5. 处理完后点击左下角「重新检测显示器」"
        )
        steps.setWordWrap(True)
        steps.setStyleSheet("color:#4b5563; font-size:12px; line-height:150%;")
        lay.addWidget(steps)
        return card

    def _muted_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Muted")
        label.setWordWrap(True)
        return label

    def _make_slider(self, code: int, label: Optional[str] = None) -> widgets.VcpSlider:
        d = vcp.vcp_def(code)
        widget = widgets.VcpSlider(label or d.name)
        widget.set_range(0, 100)
        widget.set_enabled_state(False)
        widget.setToolTip(
            "VCP 0x%02X%s" % (code, ("　" + d.desc) if d.desc else "")
        )
        widget.valueChanged.connect(lambda value, c=code: self._on_slider_live(c, value))
        widget.committed.connect(lambda value, c=code: self._on_slider_commit(c, value))
        self.sliders[code] = widget
        self.shown_codes.add(code)
        return widget

    def _make_enum(self, code: int, label: Optional[str] = None) -> widgets.EnumRow:
        d = vcp.vcp_def(code)
        widget = widgets.EnumRow(label or d.name)
        widget.set_enabled_state(False)
        widget.setToolTip("VCP 0x%02X%s" % (code, ("　" + d.desc) if d.desc else ""))
        widget.changed.connect(lambda value, c=code: self._on_enum_changed(c, value))
        self.enums[code] = widget
        self.shown_codes.add(code)
        return widget

    # ================================================================== #
    # 数值加载与写入
    # ================================================================== #
    def _load_values(self, mon: ddc.Monitor) -> None:
        codes = list(self.sliders.keys()) + list(self.enums.keys())
        if not codes:
            return

        def done(result):
            if self.current is not mon:
                return
            for code, value in result.items():
                if value is None:
                    self._mark_unsupported(code)
                else:
                    self._apply_value(code, value[0], value[1])

        self.controller.read_many(mon, codes, done)

    def _mark_unsupported(self, code: int) -> None:
        if code in self.sliders:
            self.sliders[code].set_unavailable("显示器未响应 VCP 0x%02X" % code)
        if code in self.enums:
            self.enums[code].set_enabled_state(False)

    def _apply_value(self, code: int, current: int, maximum: int) -> None:
        if not self.current:
            return
        self.cache[(self.current.key, code)] = (current, maximum)
        if code in self.sliders:
            slider = self.sliders[code]
            if maximum > 0:
                slider.set_range(0, maximum)
                slider.set_value(current)
                slider.set_enabled_state(True)
            else:
                slider.set_enabled_state(False)
        if code in self.enums:
            row = self.enums[code]
            d = vcp.vcp_def(code)
            values = []
            allowed = self.current.supported_vcp.get(code)
            source = d.values or {}
            if allowed:
                for v in allowed:
                    values.append((v, source.get(v, "选项 %d" % v)))
                if current not in allowed:
                    values.insert(0, (current, source.get(current, "当前值 %d" % current)))
            else:
                values = sorted(source.items())
            if not values:
                values = [(current, "当前值 %d" % current)]
            row.set_items(values, current)
            row.set_enabled_state(True)
        self._update_card_bar()

    def _update_card_bar(self) -> None:
        if not self.current:
            return
        key = (self.current.key, 0x10)
        card = self.cards.get(self.current.key)
        if key in self.cache and card is not None:
            cur, mx = self.cache[key]
            card.set_brightness(cur, mx)

    def _on_slider_live(self, code: int, value: int) -> None:
        if not self.current:
            return
        key = (self.current.key, code)
        old = self.cache.get(key)
        self.cache[key] = (value, old[1] if old else 100)
        self.pending[key] = value
        self.write_timer.start()

    def _on_slider_commit(self, code: int, value: int) -> None:
        if not self.current:
            return
        key = (self.current.key, code)
        old = self.cache.get(key)
        self.cache[key] = (value, old[1] if old else 100)
        self.pending[key] = value
        self.write_timer.stop()
        self._flush_writes()

    def _on_enum_changed(self, code: int, value: int) -> None:
        if not self.current:
            return
        self.controller.write(self.current, code, value, self._on_write_result)
        if code == 0x60:
            self.toast.show_message("已切换输入源，若画面未变化请稍候几秒")

    def _flush_writes(self) -> None:
        pending, self.pending = self.pending, {}
        if pending:
            self._last_write = time.time()
        for (key, code), value in pending.items():
            mon = next((m for m in self.monitors if m.key == key), None)
            if not mon:
                continue
            self.controller.write(mon, code, value, self._on_write_result)
            if self.sync_btn.isChecked() and code in (0x10, 0x12):
                cached = self.cache.get((key, code))
                maximum = cached[1] if cached else 100
                if maximum > 0:
                    self._sync_to_others(mon, code, value / maximum)
        self._update_card_bar()

    def _poll_values(self) -> None:
        """定期回读，保持界面与显示器 OSD 的实际状态一致。"""
        mon = self.current
        if not mon or not mon.ddc_ok or not self.isVisible():
            return
        if time.time() - self._last_write < 2.0:
            return
        codes = [c for c in (0x10, 0x12, 0x62) if c in self.sliders]

        def done(result):
            if self.current is not mon or not isinstance(result, dict):
                return
            for code, value in result.items():
                if not value:
                    continue
                cur, mx = value
                slider = self.sliders.get(code)
                if slider and mx > 0 and abs(slider.value() - cur) > 1:
                    slider.set_range(0, mx)
                    slider.set_value(cur)
                self.cache[(mon.key, code)] = (cur, mx)
            self._update_card_bar()

        self.controller.read_many(mon, codes, done)

    def _on_write_result(self, result) -> None:
        self._last_write = time.time()
        if isinstance(result, Exception):
            self.status_label.setText("写入失败：%s" % result)
            self.toast.show_message("写入失败：%s" % result, 3000)

    def _sync_to_others(self, source: ddc.Monitor, code: int, ratio: float) -> None:
        targets = [m for m in self.monitors if m is not source and m.ddc_ok]

        def task():
            for mon in targets:
                try:
                    cached = self.cache.get((mon.key, code))
                    if cached and cached[1] > 0:
                        maximum = cached[1]
                    else:
                        _, maximum = mon.get_vcp(code)
                    if maximum > 0:
                        mon.set_vcp(code, max(0, min(maximum, round(ratio * maximum))))
                except ddc.DDCError:
                    continue
            return True

        self.controller.call(task)

    # ================================================================== #
    # 场景 / 配置文件
    # ================================================================== #
    def _targets(self) -> List[ddc.Monitor]:
        if self.sync_btn.isChecked():
            return [m for m in self.monitors if m.ddc_ok]
        return [self.current] if self.current and self.current.ddc_ok else []

    def apply_scene(self, scene: vcp.ScenePreset) -> None:
        targets = self._targets()
        if not targets:
            self.toast.show_message("没有可用的显示器")
            return
        self.status_label.setText("正在应用场景：%s…" % scene.name)

        def task():
            errors = []
            for mon in targets:
                try:
                    _, mx = mon.get_vcp(0x10)
                    if mx > 0:
                        mon.set_vcp(0x10, round(scene.brightness / 100 * mx))
                    _, mxc = mon.get_vcp(0x12)
                    if mxc > 0:
                        mon.set_vcp(0x12, round(scene.contrast / 100 * mxc))
                    if scene.color_preset and mon.supports(0x14):
                        mon.set_vcp(0x14, scene.color_preset)
                    if scene.gains and mon.supports(0x16):
                        for code, percent in zip((0x16, 0x18, 0x1A), scene.gains):
                            if mon.supports(code):
                                _, gmax = mon.get_vcp(code)
                                if gmax > 0:
                                    mon.set_vcp(code, round(percent / 100 * gmax))
                except ddc.DDCError as exc:
                    errors.append(str(exc))
            return errors

        def done(errors):
            if self.current:
                self._load_values(self.current)
            self.status_label.setText("已应用场景：%s" % scene.name)
            if errors:
                self.toast.show_message("部分控制项不支持，已跳过")
            else:
                self.toast.show_message("场景「%s」已应用" % scene.name)

        self.controller.call(task, done)

    def _rebuild_profile_menu(self) -> None:
        menu = self.profile_menu
        menu.clear()
        act_save = QAction("保存当前设置为配置文件…", menu)
        act_save.triggered.connect(self.save_profile)
        menu.addAction(act_save)
        menu.addSeparator()
        if not self.cfg.profiles:
            empty = QAction("（还没有配置文件）", menu)
            empty.setEnabled(False)
            menu.addAction(empty)
            return
        for name in sorted(self.cfg.profiles):
            act = QAction(name, menu)
            act.triggered.connect(lambda _=False, n=name: self.apply_profile(n))
            menu.addAction(act)
        menu.addSeparator()
        act_del = QAction("删除配置文件…", menu)
        act_del.triggered.connect(self.delete_profile)
        menu.addAction(act_del)

    def save_profile(self) -> None:
        name, ok = QInputDialog.getText(
            self, "保存配置文件", "名称（例如：夜间办公 / 双屏游戏）:",
            text="我的配置",
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        codes = (0x10, 0x12, 0x14, 0x16, 0x18, 0x1A, 0x62, 0x60, 0x87)
        targets = [m for m in self.monitors if m.ddc_ok]
        if not targets:
            QMessageBox.information(self, "提示", "没有可用的显示器。")
            return
        self.status_label.setText("正在读取当前设置…")

        def task():
            data: Dict[str, Dict[str, int]] = {}
            labels: Dict[str, str] = {}
            for mon in targets:
                values = {}
                for code in codes:
                    if not mon.supports(code):
                        continue
                    try:
                        cur, mx = mon.get_vcp(code)
                    except ddc.DDCError:
                        continue
                    if mx > 0:
                        values[str(code)] = cur
                if values:
                    data[mon.key] = values
                    labels[mon.key] = mon.display_name
            return data, labels

        def done(result):
            if isinstance(result, Exception):
                self.status_label.setText("保存失败：%s" % result)
                return
            data, labels = result
            if not data:
                QMessageBox.information(self, "提示", "没有读取到可保存的数值。")
                return
            self.cfg.save_profile(name, data, labels)
            self.status_label.setText("已保存配置文件「%s」" % name)
            self.toast.show_message("已保存配置文件「%s」" % name)

        self.controller.call(task, done)

    def apply_profile(self, name: str) -> None:
        profile = self.cfg.profiles.get(name)
        if not profile:
            return
        steps = []
        for mon in self.monitors:
            if not mon.ddc_ok:
                continue
            values = profile.get("monitors", {}).get(mon.key)
            if not values:
                continue
            for code_text, raw in values.items():
                code = int(code_text)
                if not mon.supports(code):
                    continue
                steps.append((mon, code, int(raw)))
        if not steps:
            QMessageBox.information(
                self, "无法应用",
                "该配置文件里没有与当前显示器匹配的设置。\n（配置文件按显示器型号 + 序列号匹配）",
            )
            return
        self.status_label.setText("正在应用配置文件：%s…" % name)

        def done(results):
            if self.current:
                self._load_values(self.current)
            self.status_label.setText("已应用配置文件：%s" % name)
            self.toast.show_message("已应用「%s」" % name)

        self.controller.run_sequence(steps, done)

    def delete_profile(self) -> None:
        if not self.cfg.profiles:
            return
        name, ok = QInputDialog.getItem(
            self, "删除配置文件", "选择要删除的配置文件:", sorted(self.cfg.profiles), 0, False
        )
        if ok and name:
            self.cfg.delete_profile(name)
            self.toast.show_message("已删除「%s」" % name)

    # ================================================================== #
    # 其它操作
    # ================================================================== #
    def _restore_last_state(self) -> None:
        steps = []
        for mon in self.monitors:
            values = self.cfg.last_state.get(mon.key)
            if not values:
                continue
            for code_text, raw in values.items():
                code = int(code_text)
                if code in (0x10, 0x12) and mon.supports(code):
                    steps.append((mon, code, int(raw)))
        if steps:
            self.controller.run_sequence(steps, lambda _r: self._load_values(self.current) if self.current else None)

    def _restore_defaults(self) -> None:
        if not self.current:
            return
        answer = QMessageBox.question(
            self,
            "恢复出厂设置",
            "将向显示器发送 VCP 0x04（恢复出厂默认值）。\n"
            "这会把亮度、对比度、色彩等全部恢复为出厂状态，且无法撤销。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        mon = self.current

        def done(result):
            self.toast.show_message("已发送恢复出厂指令")
            QTimer.singleShot(800, lambda: self._load_values(mon))

        self.controller.write_now(mon, 0x04, 0x01, lambda r: done(r) if not isinstance(r, Exception) else self._on_write_result(r))

    def _nudge(self, code: int, direction: int) -> None:
        mon = self.current or next((m for m in self.monitors if m.ddc_ok), None)
        if not mon:
            return
        key = (mon.key, code)
        cached = self.cache.get(key)
        if not cached or cached[1] <= 0:
            def first(result):
                if isinstance(result, Exception):
                    return
                cur, mx = result
                self.cache[key] = (cur, mx)
                self._nudge(code, direction)

            self.controller.read(mon, code, first)
            return
        cur, mx = cached
        step = max(1, round(mx * 0.05))
        new = max(0, min(mx, cur + direction * step))
        self.cache[key] = (new, mx)
        if self.current is mon and code in self.sliders:
            self.sliders[code].set_value(new)
        self.controller.write(mon, code, new, self._on_write_result)
        if self.sync_btn.isChecked() and code in (0x10, 0x12):
            self._sync_to_others(mon, code, new / mx)
        self._update_card_bar()
        self.toast.show_message("%s %d%%" % (vcp.vcp_name(code), round(new / mx * 100)), 1200)

    def _on_sync_toggled(self, checked: bool) -> None:
        self.toast.show_message(
            "已开启全部同步：亮度/对比度将按比例同步" if checked else "已关闭全部同步"
        )

    def open_vcp_browser(self) -> None:
        if not self.current:
            return
        dlg = VcpBrowserDialog(self.controller, self.current, self)
        dlg.exec()
        self._load_values(self.current)

    def copy_diagnostic_report(self) -> None:
        from PySide6.QtWidgets import QApplication

        report = ddc.format_report(self.monitors, APP_VERSION)
        QApplication.clipboard().setText(report)
        self.toast.show_message("诊断报告已复制到剪贴板")

    def open_diagnostics(self) -> None:
        if not self.current:
            return
        dlg = DiagnosticsDialog(self.controller, self.current, self)
        dlg.exec()

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.cfg, self)
        dlg.settingsChanged.connect(self._apply_settings)
        dlg.exec()

    def _open_config_dir(self) -> None:
        config.ensure_dir()
        os.startfile(config.APP_DIR)  # noqa: S606

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "关于 MonitorCtrl",
            "<b>MonitorCtrl %s</b><br><br>"
            "通过 DDC/CI 协议直接控制显示器硬件：亮度、对比度、音量、输入源、"
            "色彩增益等，不依赖显卡驱动或厂商工具。<br><br>"
            "所有设置保存在：<br><code>%s</code>" % (APP_VERSION, config.CONFIG_PATH),
        )

    # ================================================================== #
    # 托盘 / 热键 / 关闭
    # ================================================================== #
    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    def _show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _register_hotkeys(self) -> None:
        hwnd = int(self.winId())
        for kid in self._hotkey_ids:
            user32.UnregisterHotKey(hwnd, kid)
        self._hotkey_ids = []
        if not self.cfg.get("hotkeys"):
            self.hint_label.setText("")
            return
        self.hint_label.setText("Ctrl+Alt+↑/↓ 亮度　Ctrl+Alt+←/→ 对比度")
        bindings = [(1, VK_UP), (2, VK_DOWN), (3, VK_LEFT), (4, VK_RIGHT)]
        for kid, vk in bindings:
            if user32.RegisterHotKey(hwnd, kid, MOD_CONTROL | MOD_ALT, vk):
                self._hotkey_ids.append(kid)
        if len(self._hotkey_ids) < 4:
            self.hint_label.setText("部分全局热键被其它程序占用")

    def _on_hotkey(self, kid: int) -> None:
        if kid == 1:
            self._nudge(0x10, +1)
        elif kid == 2:
            self._nudge(0x10, -1)
        elif kid == 3:
            self._nudge(0x12, -1)
        elif kid == 4:
            self._nudge(0x12, +1)

    def quit_app(self) -> None:
        self._closing = True
        self._save_last_state()
        hwnd = int(self.winId())
        for kid in self._hotkey_ids:
            user32.UnregisterHotKey(hwnd, kid)
        self._hotkey_ids = []
        self.tray.hide()
        self.controller.shutdown()
        QApplication.instance().quit()

    def _save_last_state(self) -> None:
        for mon in self.monitors:
            values = {}
            for code in (0x10, 0x12):
                cached = self.cache.get((mon.key, code))
                if cached:
                    values[code] = cached[0]
            if values:
                self.cfg.remember_state(mon.key, values)
        self.cfg.save()

    def closeEvent(self, event):  # noqa: N802
        if self._closing:
            event.accept()
            return
        if self.cfg.get("tray") and self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "MonitorCtrl", "程序已最小化到托盘，双击图标可重新打开。",
                QSystemTrayIcon.Information, 2000,
            )
            return
        self._closing = True
        self._save_last_state()
        self.controller.shutdown()
        event.accept()
