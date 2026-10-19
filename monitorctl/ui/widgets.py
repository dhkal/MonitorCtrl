"""自定义控件：图标、显示器卡片、VCP 滑杆、分组卡片。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QIcon,
    QIntValidator,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from . import theme


# --------------------------------------------------------------------------- #
# 矢量图标（不依赖任何图片资源）
# --------------------------------------------------------------------------- #
def _icon_path(name: str, s: float) -> QPainterPath:
    """在 s x s 的坐标系里画图标轮廓。"""
    p = QPainterPath()
    if name == "monitor":
        p.addRoundedRect(QRectF(s * 0.10, s * 0.16, s * 0.80, s * 0.56), s * 0.08, s * 0.08)
        p.moveTo(s * 0.36, s * 0.82)
        p.lineTo(s * 0.64, s * 0.82)
        p.moveTo(s * 0.50, s * 0.72)
        p.lineTo(s * 0.50, s * 0.82)
    elif name == "sun":
        p.addEllipse(QPointF(s * 0.5, s * 0.5), s * 0.19, s * 0.19)
        for i in range(8):
            import math

            a = math.radians(i * 45)
            x1 = s * 0.5 + math.cos(a) * s * 0.30
            y1 = s * 0.5 + math.sin(a) * s * 0.30
            x2 = s * 0.5 + math.cos(a) * s * 0.40
            y2 = s * 0.5 + math.sin(a) * s * 0.40
            p.moveTo(x1, y1)
            p.lineTo(x2, y2)
    elif name == "moon":
        outer = QPainterPath()
        outer.addEllipse(QRectF(s * 0.14, s * 0.10, s * 0.72, s * 0.72))
        inner = QPainterPath()
        inner.addEllipse(QRectF(s * 0.34, s * 0.02, s * 0.66, s * 0.66))
        p = outer.subtracted(inner)
    elif name == "refresh":
        rect = QRectF(s * 0.16, s * 0.16, s * 0.68, s * 0.68)
        p.arcMoveTo(rect, 40)
        p.arcTo(rect, 40, 290)
        p.moveTo(s * 0.86, s * 0.10)
        p.lineTo(s * 0.86, s * 0.34)
        p.lineTo(s * 0.62, s * 0.34)
    elif name == "save":
        p.addRoundedRect(QRectF(s * 0.14, s * 0.14, s * 0.72, s * 0.72), s * 0.09, s * 0.09)
        p.addRect(QRectF(s * 0.30, s * 0.14, s * 0.40, s * 0.24))
        p.addRect(QRectF(s * 0.30, s * 0.54, s * 0.40, s * 0.32))
    elif name == "gear":
        p.addEllipse(QPointF(s * 0.5, s * 0.5), s * 0.15, s * 0.15)
        p.addEllipse(QPointF(s * 0.5, s * 0.5), s * 0.31, s * 0.31)
    elif name == "star":
        import math

        for i in range(10):
            a = math.radians(-90 + i * 36)
            r = s * (0.42 if i % 2 == 0 else 0.18)
            x, y = s * 0.5 + math.cos(a) * r, s * 0.5 + math.sin(a) * r
            if i == 0:
                p.moveTo(x, y)
            else:
                p.lineTo(x, y)
        p.closeSubpath()
    elif name == "warning":
        p.moveTo(s * 0.5, s * 0.12)
        p.lineTo(s * 0.94, s * 0.86)
        p.lineTo(s * 0.06, s * 0.86)
        p.closeSubpath()
        p.moveTo(s * 0.5, s * 0.36)
        p.lineTo(s * 0.5, s * 0.60)
        p.moveTo(s * 0.5, s * 0.70)
        p.lineTo(s * 0.5, s * 0.72)
    elif name == "power":
        p.arcMoveTo(QRectF(s * 0.18, s * 0.20, s * 0.64, s * 0.64), 70)
        p.arcTo(QRectF(s * 0.18, s * 0.20, s * 0.64, s * 0.64), 70, 320)
        p.moveTo(s * 0.5, s * 0.10)
        p.lineTo(s * 0.5, s * 0.48)
    elif name == "check":
        p.moveTo(s * 0.16, s * 0.52)
        p.lineTo(s * 0.40, s * 0.76)
        p.lineTo(s * 0.86, s * 0.24)
    elif name == "keyboard":
        p.addRoundedRect(QRectF(s * 0.06, s * 0.28, s * 0.88, s * 0.44), s * 0.08, s * 0.08)
        p.moveTo(s * 0.30, s * 0.62)
        p.lineTo(s * 0.70, s * 0.62)
    elif name == "palette":
        p.addEllipse(QPointF(s * 0.5, s * 0.5), s * 0.40, s * 0.40)
        for dx, dy in ((-0.14, -0.10), (0.10, -0.14), (0.16, 0.10), (-0.06, 0.20)):
            p.addEllipse(QPointF(s * (0.5 + dx), s * (0.5 + dy)), s * 0.055, s * 0.055)
    elif name == "plus":
        p.moveTo(s * 0.5, s * 0.2)
        p.lineTo(s * 0.5, s * 0.8)
        p.moveTo(s * 0.2, s * 0.5)
        p.lineTo(s * 0.8, s * 0.5)
    elif name == "chevron":
        p.moveTo(s * 0.38, s * 0.22)
        p.lineTo(s * 0.64, s * 0.5)
        p.lineTo(s * 0.38, s * 0.78)
    else:
        p.addEllipse(QPointF(s * 0.5, s * 0.5), s * 0.34, s * 0.34)
    return p


def make_icon(name: str, size: int = 18, color: str = theme.TEXT) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    path = _icon_path(name, float(size))
    pen = QPen(QColor(color), max(1.4, size * 0.085))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)
    painter.end()
    return QIcon(pm)


def make_pixmap(name: str, size: int = 64, color: str = theme.ACCENT) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), max(2.0, size * 0.07))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.drawPath(_icon_path(name, float(size)))
    painter.end()
    return pm


# --------------------------------------------------------------------------- #
# 小部件
# --------------------------------------------------------------------------- #
class ElidedLabel(QLabel):
    """按实际宽度自动省略的标签。"""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        super().setText(text)
        self.setToolTip(text)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._apply()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._apply()

    def _apply(self) -> None:
        # 用控件自身的 fontMetrics：样式表用 px 设字号时 font() 的 pointSize 是 -1，
        # 直接构造 QFontMetrics 会触发 "Point size <= 0" 警告
        metrics = self.fontMetrics()
        super().setText(metrics.elidedText(self._full, Qt.ElideRight, max(10, self.width())))


def _forward_wheel(widget: QWidget, event) -> bool:
    """把滚轮事件转给外层滚动区域，让页面正常滚动。"""
    from PySide6.QtWidgets import QAbstractScrollArea

    parent = widget.parentWidget()
    while parent is not None and not isinstance(parent, QAbstractScrollArea):
        parent = parent.parentWidget()
    if parent is None:
        return False
    QApplication.sendEvent(parent.viewport(), QWheelEvent(event))
    return True


class NoWheelSlider(QSlider):
    """滚轮默认不改变数值，避免滚动页面时误改；按住 Ctrl 才用滚轮微调。"""

    def wheelEvent(self, event):  # noqa: N802
        if event.modifiers() & Qt.ControlModifier:
            step = max(1, round((self.maximum() - self.minimum()) / 100))
            delta = 1 if event.angleDelta().y() > 0 else -1
            self.setValue(self.value() + delta * step)
            event.accept()
            return
        if _forward_wheel(self, event):
            event.accept()
        else:
            event.ignore()


class NoWheelComboBox(QComboBox):
    """滚轮不切换选项（下拉框抢滚轮是 Qt 的老毛病）。"""

    def wheelEvent(self, event):  # noqa: N802
        if _forward_wheel(self, event):
            event.accept()
        else:
            event.ignore()


class MiniBar(QWidget):
    """细长的百分比条。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ratio = 0.0
        self._color = QColor(theme.ACCENT)
        self.setFixedHeight(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_ratio(self, ratio: float, color: Optional[str] = None) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        if color:
            self._color = QColor(color)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#eef1f6"))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 2, 2)
        if self._ratio > 0:
            p.setBrush(self._color)
            p.drawRoundedRect(
                QRectF(0, 0, max(2.0, self.width() * self._ratio), self.height()), 2, 2
            )
        p.end()


class Badge(QLabel):
    def __init__(self, text: str, kind: str = "accent", parent=None):
        super().__init__(text, parent)
        self.setObjectName("Badge" if kind == "accent" else "BadgeGray")
        self.setAlignment(Qt.AlignCenter)


class MonitorCard(QWidget):
    """左侧显示器列表中的卡片。"""

    def __init__(self, index: int, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.monitor_index = index
        self._title = title
        self._subtitle = subtitle
        self._brightness = 0.0
        self._ok = True

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedHeight(78)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.title_label = ElidedLabel(title)
        self.title_label.setStyleSheet("font-weight:600; font-size:13px;")
        self.title_label.setTextInteractionFlags(Qt.NoTextInteraction)
        top.addWidget(self.title_label, 1)
        self.badge = Badge("主")
        self.badge.setVisible(False)
        top.addWidget(self.badge, 0)
        self.warn = QLabel("!")
        self.warn.setStyleSheet(
            "color:#d97706; font-weight:800; border:1px solid #f3d19e;"
            "border-radius:8px; padding:0px 5px; font-size:11px;"
        )
        self.warn.setVisible(False)
        top.addWidget(self.warn, 0)
        lay.addLayout(top)

        self.sub_label = QLabel(subtitle)
        self.sub_label.setObjectName("Muted")
        self.sub_label.setStyleSheet("font-size:11px; color:#8a93a3;")
        lay.addWidget(self.sub_label)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.bar = MiniBar()
        row.addWidget(self.bar, 1)
        self.val = QLabel("--")
        self.val.setStyleSheet("font-size:11px; color:#8a93a3; font-family:Consolas;")
        row.addWidget(self.val, 0)
        lay.addLayout(row)

        self.title_label.set_full_text(title)

    def set_brightness(self, current: int, maximum: int) -> None:
        if maximum <= 0:
            self.bar.set_ratio(0)
            self.val.setText("--")
            return
        ratio = current / maximum
        self.bar.set_ratio(ratio, theme.ACCENT if self._ok else "#c9d2de")
        self.val.setText("%d%%" % round(ratio * 100))

    def set_primary(self, primary: bool) -> None:
        self.badge.setVisible(primary)

    def set_ok(self, ok: bool) -> None:
        self._ok = ok
        self.warn.setVisible(not ok)
        self.title_label.setStyleSheet(
            "font-weight:600; font-size:13px;" + ("" if ok else "color:#8a93a3;")
        )

    def update_text(self, title: str, subtitle: str) -> None:
        self._title = title
        self._subtitle = subtitle
        self.title_label.set_full_text(title)
        self.sub_label.setText(subtitle)


class VcpSlider(QWidget):
    """带数值框与步进按钮的滑杆行。"""

    valueChanged = Signal(int)   # 拖动过程中
    committed = Signal(int)      # 最终值

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._updating = False
        self._minimum = 0
        self._maximum = 100

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.name_label = QLabel(label)
        self.name_label.setFixedWidth(80)
        self.name_label.setStyleSheet("font-size:12px; color:#4b5563;")
        lay.addWidget(self.name_label)

        self.slider = NoWheelSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(10)
        lay.addWidget(self.slider, 1)

        self.spin = QLineEdit("0")
        self.spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spin.setFixedWidth(52)
        self.spin.setValidator(QIntValidator(0, 100, self))
        self.spin.setStyleSheet("font-family:Consolas; font-size:12px; padding:3px 5px;")
        lay.addWidget(self.spin)

        self.minus = QPushButton("\u2212")
        self.minus.setObjectName("Step")
        self.minus.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.minus)

        self.plus = QPushButton("+")
        self.plus.setObjectName("Step")
        self.plus.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.plus)

        self.slider.valueChanged.connect(self._on_slider)
        self.slider.sliderReleased.connect(self._on_release)
        self.spin.editingFinished.connect(self._commit_spin)
        self.spin.returnPressed.connect(self._commit_spin)
        self.minus.clicked.connect(lambda: self._step(-1))
        self.plus.clicked.connect(lambda: self._step(1))

    # -- 对外 ------------------------------------------------------------ #
    def set_range(self, minimum: int, maximum: int) -> None:
        self._minimum, self._maximum = minimum, maximum
        self.slider.setRange(minimum, maximum)
        self.spin.setValidator(QIntValidator(minimum, maximum, self))

    def set_value(self, value: int) -> None:
        self._updating = True
        self.slider.setValue(int(value))
        self.spin.setText(str(int(value)))
        self._updating = False

    def value(self) -> int:
        return self.slider.value()

    def set_enabled_state(self, enabled: bool) -> None:
        for w in (self.slider, self.spin, self.minus, self.plus):
            w.setEnabled(enabled)

    def set_hint(self, text: str) -> None:
        self.setToolTip(text)

    def set_unavailable(self, hint: str = "") -> None:
        """显示器不响应这个控制项时显示 --。"""
        self.set_enabled_state(False)
        self._updating = True
        self.slider.setValue(self._minimum)
        self.spin.setText("--")
        self._updating = False
        if hint:
            self.setToolTip(hint)

    # -- 内部 ------------------------------------------------------------ #
    def _on_slider(self, value: int) -> None:
        if self._updating:
            return
        self._updating = True
        self.spin.setText(str(value))
        self._updating = False
        self.valueChanged.emit(value)

    def _on_release(self) -> None:
        if not self._updating:
            self.committed.emit(self.slider.value())

    def _commit_spin(self) -> None:
        if self._updating:
            return
        text = self.spin.text().strip()
        try:
            value = int(text)
        except ValueError:
            self.set_value(self.slider.value())
            return
        value = max(self._minimum, min(self._maximum, value))
        if value == self.slider.value():
            self.set_value(value)
            return
        self.set_value(value)
        self.committed.emit(value)

    def _step(self, direction: int) -> None:
        step = max(1, round((self._maximum - self._minimum) / 100))
        value = max(self._minimum, min(self._maximum, self.slider.value() + direction * step))
        self.set_value(value)
        self.committed.emit(value)


class EnumRow(QWidget):
    """标签 + 下拉框。"""

    changed = Signal(int)

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._updating = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.name_label = QLabel(label)
        self.name_label.setFixedWidth(80)
        self.name_label.setStyleSheet("font-size:12px; color:#4b5563;")
        lay.addWidget(self.name_label)
        self.combo = NoWheelComboBox()
        self.combo.setMinimumWidth(160)
        lay.addWidget(self.combo, 1)
        self.combo.currentIndexChanged.connect(self._on_change)

    def set_items(self, items, current: Optional[int] = None) -> None:
        self._updating = True
        self.combo.clear()
        for value, text in items:
            self.combo.addItem(text, value)
        if current is not None:
            idx = self.combo.findData(current)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
        self._updating = False

    def set_current(self, value: int) -> None:
        self._updating = True
        idx = self.combo.findData(value)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        self._updating = False

    def set_enabled_state(self, enabled: bool) -> None:
        self.combo.setEnabled(enabled)

    def _on_change(self, _index: int) -> None:
        if self._updating:
            return
        data = self.combo.currentData()
        if data is not None:
            self.changed.emit(int(data))


class SectionCard(QFrame):
    """带标题的分组卡片。"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 13, 16, 14)
        self.body.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(6)
        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("SectionTitle")
        head.addWidget(self.title_label)
        head.addStretch(1)
        self.head = head
        self.body.addLayout(head)

    def add_widget(self, widget: QWidget) -> None:
        self.body.addWidget(widget)

    def add_layout(self, layout) -> None:
        self.body.addLayout(layout)


class Toast(QLabel):
    """浮在窗口底部的轻量提示。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "background:#111827; color:white; border-radius:8px; padding:7px 14px;"
            "font-size:12px;"
        )
        self.setVisible(False)
        self._timer = None

    def show_message(self, text: str, msec: int = 2200) -> None:
        from PySide6.QtCore import QTimer

        self.setText(text)
        self.adjustSize()
        parent = self.parentWidget()
        if parent:
            self.move(
                (parent.width() - self.width()) // 2,
                parent.height() - self.height() - 34,
            )
        self.setVisible(True)
        self.raise_()
        if self._timer:
            self._timer.stop()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._timer.start(msec)
