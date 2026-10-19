"""对话框：VCP 浏览器、显示器诊断、设置。"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .. import config, ddc, vcp
from . import theme


class VcpBrowserDialog(QDialog):
    """直接读写任意 VCP 代码。"""

    def __init__(self, controller, monitor: ddc.Monitor, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.monitor = monitor
        self.values: Dict[int, Optional[tuple]] = {}

        self.setWindowTitle("VCP 浏览器 - %s" % monitor.display_name)
        self.resize(660, 620)
        self.setStyleSheet(theme.QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        head = QLabel("显示器支持的全部 VCP 代码")
        head.setObjectName("H2")
        root.addWidget(head)

        hint = QLabel(
            "VCP (Virtual Control Panel) 是 DDC/CI 的控制项编号，0x10 为亮度、0x12 为对比度。"
            "不同厂商会提供私有代码，名称未知的代码同样可以读写。"
        )
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        root.addWidget(hint)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["代码", "名称", "当前值", "最大值"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 90)
        self.table.setShowGrid(False)
        for col in (2, 3):
            self.table.horizontalHeaderItem(col).setTextAlignment(
                Qt.AlignRight | Qt.AlignVCenter
            )
        self.table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root.addWidget(self.table, 1)

        row = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新全部")
        self.refresh_btn.setObjectName("Primary")
        self.refresh_btn.clicked.connect(self.refresh)
        row.addWidget(self.refresh_btn)

        self.set_btn = QPushButton("设置选中项的值")
        self.set_btn.clicked.connect(self.set_selected)
        row.addWidget(self.set_btn)

        self.custom_btn = QPushButton("读写自定义代码…")
        self.custom_btn.clicked.connect(self.custom_code)
        row.addWidget(self.custom_btn)

        row.addStretch(1)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        root.addLayout(row)

        self.status = QLabel("")
        self.status.setObjectName("Muted")
        root.addWidget(self.status)

        self.populate()
        self.refresh()

    # ------------------------------------------------------------------ #
    def populate(self) -> None:
        codes = vcp.ordered_codes(self.monitor.supported_vcp)
        if not codes:
            codes = list(range(0x10, 0x14))
        self.table.setRowCount(len(codes))
        mono = QFont("Consolas", 9)
        for row, code in enumerate(codes):
            item_code = QTableWidgetItem("0x%02X" % code)
            item_code.setFont(mono)
            self.table.setItem(row, 0, item_code)
            self.table.setItem(row, 1, QTableWidgetItem(vcp.vcp_name(code)))
            self.table.setItem(row, 2, QTableWidgetItem("…"))
            self.table.setItem(row, 3, QTableWidgetItem(""))
            for col in (2, 3):
                self.table.item(row, col).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def _codes(self) -> List[int]:
        return [int(self.table.item(r, 0).text(), 16) for r in range(self.table.rowCount())]

    def refresh(self) -> None:
        codes = self._codes()
        self.refresh_btn.setEnabled(False)
        self.status.setText("正在读取 %d 个控制项…" % len(codes))

        def done(result):
            self.refresh_btn.setEnabled(True)
            ok = 0
            for row, code in enumerate(codes):
                value = result.get(code)
                if value is None:
                    self.table.item(row, 2).setText("不支持")
                    self.table.item(row, 2).setForeground(Qt.gray)
                    self.table.item(row, 3).setText("")
                else:
                    ok += 1
                    cur, mx = value
                    self.table.item(row, 2).setText(str(cur))
                    self.table.item(row, 3).setText(str(mx))
                    self.table.item(row, 2).setForeground(Qt.black)
            self.status.setText("可读取 %d / %d 项" % (ok, len(codes)))

        self.controller.read_many(self.monitor, codes, done)

    def set_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一个控制项。")
            return
        code = int(self.table.item(row, 0).text(), 16)
        maximum_text = self.table.item(row, 3).text()
        maximum = int(maximum_text) if maximum_text.isdigit() else 100
        current = self.table.item(row, 2).text()
        start = int(current) if current.isdigit() else 0
        value, ok = QInputDialog.getInt(
            self,
            "设置 0x%02X" % code,
            "%s 的新值 (0 - %d):" % (vcp.vcp_name(code), maximum),
            start,
            0,
            max(maximum, 1),
            1,
        )
        if not ok:
            return

        def done(result):
            self.table.item(row, 2).setText(str(value))
            self.status.setText("已写入 0x%02X = %d" % (code, value))

        def failed(exc):
            QMessageBox.warning(self, "写入失败", str(exc))

        self.controller.write_now(self.monitor, code, value, lambda r: done(r) if not isinstance(r, Exception) else failed(r))

    def custom_code(self) -> None:
        text, ok = QInputDialog.getText(self, "自定义代码", "VCP 代码（十六进制，如 0xE1）:", text="0x")
        if not ok or not text.strip():
            return
        try:
            code = int(text.strip(), 16)
        except ValueError:
            QMessageBox.warning(self, "格式错误", "请输入十六进制数值，例如 0x10。")
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem("0x%02X" % code))
        self.table.setItem(row, 1, QTableWidgetItem(vcp.vcp_name(code)))
        self.table.setItem(row, 2, QTableWidgetItem("…"))
        self.table.setItem(row, 3, QTableWidgetItem(""))
        self.table.selectRow(row)
        self.refresh()


class DiagnosticsDialog(QDialog):
    """能力字符串 + 逐项读取测试。"""

    def __init__(self, controller, monitor: ddc.Monitor, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.monitor = monitor
        self.setWindowTitle("显示器诊断 - %s" % monitor.display_name)
        self.resize(720, 640)
        self.setStyleSheet(theme.QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        info = QLabel(
            "<b>%s</b><br>输出端口：%s　分辨率：%s<br>EDID 厂商：%s　产品代码：0x%04X　序列号：%s"
            % (
                monitor.display_name,
                monitor.device_name,
                monitor.resolution,
                monitor.edid.manufacturer or "未知",
                monitor.edid.product_code,
                monitor.edid.serial_text or str(monitor.edid.serial_number or "-"),
            )
        )
        info.setWordWrap(True)
        root.addWidget(info)

        state = "正常" if monitor.ddc_ok else "异常"
        color = theme.OK if monitor.ddc_ok else theme.DANGER
        self.state_label = QLabel(
            '<span style="color:%s; font-weight:600;">DDC/CI 状态：%s</span>' % (color, state)
            + ("" if monitor.ddc_ok else "<br><span style='color:#6b7280;'>%s</span>" % (monitor.last_error or ""))
        )
        self.state_label.setWordWrap(True)
        root.addWidget(self.state_label)

        api_title = QLabel("系统 API 调用结果")
        api_title.setObjectName("H2")
        root.addWidget(api_title)

        api_lines = [
            "HMONITOR: 0x%X　　物理显示器句柄: %s"
            % (monitor.hmonitor or 0, ("0x%X" % monitor.handle) if monitor.handle else "空")
        ]
        for step in (monitor.probe or {}).get("steps", []):
            api_lines.append(
                "第 %d 次：数量 %d（ok=%s, err=%d）　获取=%s（ok=%s, err=%s）　句柄=%s"
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
        api_view = QPlainTextEdit()
        api_view.setReadOnly(True)
        api_view.setFont(QFont("Consolas", 9))
        api_view.setPlainText("\n".join(api_lines))
        api_view.setMaximumHeight(76)
        root.addWidget(api_view)

        caps_title = QLabel("能力字符串 (Capabilities String)")
        caps_title.setObjectName("H2")
        root.addWidget(caps_title)

        self.caps_view = QPlainTextEdit()
        self.caps_view.setReadOnly(True)
        self.caps_view.setFont(QFont("Consolas", 9))
        self.caps_view.setPlainText(monitor.capabilities_raw or "（显示器未返回能力字符串）")
        self.caps_view.setMaximumHeight(120)
        root.addWidget(self.caps_view)

        parsed = vcp.parse_capabilities(monitor.capabilities_raw)
        summary = QLabel(
            "MCCS 版本：%s　　类型：%s　　型号：%s　　支持 VCP：%d 项"
            % (
                parsed.get("mccs_ver") or "未知",
                parsed.get("type") or "未知",
                parsed.get("model") or monitor.friendly_name,
                len(monitor.supported_vcp),
            )
        )
        summary.setObjectName("Muted")
        root.addWidget(summary)

        test_title = QLabel("关键控制项读取测试")
        test_title.setObjectName("H2")
        root.addWidget(test_title)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["控制项", "代码", "结果", "范围"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 120)
        self.table.setShowGrid(False)
        for col in (1, 2, 3):
            self.table.horizontalHeaderItem(col).setTextAlignment(
                Qt.AlignHCenter | Qt.AlignVCenter
            )
        self.table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root.addWidget(self.table, 1)

        row = QHBoxLayout()
        self.retest = QPushButton("重新检测")
        self.retest.setObjectName("Primary")
        self.retest.clicked.connect(self.run_test)
        row.addWidget(self.retest)
        row.addStretch(1)
        copy_btn = QPushButton("复制诊断信息")
        copy_btn.clicked.connect(self.copy_report)
        row.addWidget(copy_btn)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        root.addLayout(row)

        self.run_test()

    def run_test(self) -> None:
        codes = [0x10, 0x12, 0x62, 0x60, 0x14, 0xD6, 0x87, 0x16, 0x18, 0x1A]
        self.table.setRowCount(len(codes))
        for r, code in enumerate(codes):
            self.table.setItem(r, 0, QTableWidgetItem(vcp.vcp_name(code)))
            self.table.setItem(r, 1, QTableWidgetItem("0x%02X" % code))
            self.table.setItem(r, 2, QTableWidgetItem("…"))
            self.table.setItem(r, 3, QTableWidgetItem(""))
        self.retest.setEnabled(False)

        def done(result):
            self.retest.setEnabled(True)
            for r, code in enumerate(codes):
                value = result.get(code)
                if value is None:
                    item = QTableWidgetItem("失败")
                    item.setForeground(Qt.red)
                    self.table.setItem(r, 2, item)
                else:
                    cur, mx = value
                    item = QTableWidgetItem("正常")
                    item.setForeground(Qt.darkGreen)
                    self.table.setItem(r, 2, item)
                    self.table.setItem(r, 3, QTableWidgetItem("%d / %d" % (cur, mx)))

        self.controller.read_many(self.monitor, codes, done)

    def copy_report(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(ddc.format_report([self.monitor]))
        QMessageBox.information(self, "已复制", "诊断信息已复制到剪贴板。")


class SettingsDialog(QDialog):
    settingsChanged = Signal()

    def __init__(self, cfg: config.Config, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("设置")
        self.setFixedWidth(460)
        self.setStyleSheet(theme.QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        title = QLabel("常规设置")
        title.setObjectName("H2")
        root.addWidget(title)

        self.cb_hotkeys = QCheckBox("启用全局热键（Ctrl+Alt+↑/↓ 调节亮度，←/→ 调节对比度）")
        self.cb_hotkeys.setChecked(bool(cfg.get("hotkeys")))
        root.addWidget(self.cb_hotkeys)

        self.cb_tray = QCheckBox("关闭窗口时最小化到系统托盘")
        self.cb_tray.setChecked(bool(cfg.get("tray")))
        root.addWidget(self.cb_tray)

        self.cb_autostart = QCheckBox("开机自动启动")
        self.cb_autostart.setChecked(config.Config.is_autostart_enabled())
        root.addWidget(self.cb_autostart)

        self.cb_restore = QCheckBox("启动时恢复上次的亮度 / 对比度")
        self.cb_restore.setChecked(bool(cfg.get("apply_last_on_start")))
        root.addWidget(self.cb_restore)

        self.cb_minimized = QCheckBox("启动后最小化到托盘")
        self.cb_minimized.setChecked(bool(cfg.get("start_minimized")))
        root.addWidget(self.cb_minimized)

        self.cb_poll = QCheckBox("每 5 秒回读一次数值（同步显示器 OSD 上的改动）")
        self.cb_poll.setChecked(bool(cfg.get("poll_interval")))
        root.addWidget(self.cb_poll)

        path = QLabel("配置文件：%s" % config.CONFIG_PATH)
        path.setWordWrap(True)
        path.setObjectName("Muted")
        path.setStyleSheet("font-size:11px;")
        root.addWidget(path)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def save(self) -> None:
        self.cfg.set("hotkeys", self.cb_hotkeys.isChecked())
        self.cfg.set("tray", self.cb_tray.isChecked())
        self.cfg.set("apply_last_on_start", self.cb_restore.isChecked())
        self.cfg.set("start_minimized", self.cb_minimized.isChecked())
        self.cfg.set("poll_interval", 5 if self.cb_poll.isChecked() else 0)
        config.Config.set_autostart(self.cb_autostart.isChecked())
        self.cfg.set("autostart", self.cb_autostart.isChecked())
        self.settingsChanged.emit()
        self.accept()
