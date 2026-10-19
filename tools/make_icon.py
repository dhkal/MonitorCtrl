"""生成应用图标（多尺寸 .ico + png）。"""

from __future__ import annotations

import io
import os
import struct
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from PySide6.QtCore import QBuffer, QByteArray, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

SIZES = [16, 24, 32, 48, 64, 128, 256]


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    s = float(size)
    # 圆角底板 + 渐变
    grad = QLinearGradient(0, 0, s, s)
    grad.setColorAt(0.0, QColor("#3b82f6"))
    grad.setColorAt(1.0, QColor("#1d4ed8"))
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, s, s), s * 0.22, s * 0.22)
    p.fillPath(path, grad)

    # 屏幕
    screen = QRectF(s * 0.18, s * 0.22, s * 0.64, s * 0.42)
    pen = QPen(QColor(255, 255, 255), max(1.2, s * 0.075))
    pen.setJoinStyle(Qt.RoundJoin)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(screen, s * 0.07, s * 0.07)

    # 屏幕里的太阳（亮度）
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawEllipse(QPointF(s * 0.5, s * 0.43), s * 0.085, s * 0.085)
    p.setPen(QPen(QColor(255, 255, 255, 220), max(1.0, s * 0.045)))
    p.setBrush(Qt.NoBrush)
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        p.drawLine(
            QPointF(s * (0.5 + dx * 0.15), s * (0.43 + dy * 0.15)),
            QPointF(s * (0.5 + dx * 0.21), s * (0.43 + dy * 0.21)),
        )

    # 支架
    p.setPen(QPen(QColor(255, 255, 255), max(1.2, s * 0.075)))
    p.drawLine(QPointF(s * 0.5, s * 0.64), QPointF(s * 0.5, s * 0.74))
    p.drawLine(QPointF(s * 0.34, s * 0.79), QPointF(s * 0.66, s * 0.79))
    p.end()
    return img


def png_bytes(size: int) -> bytes:
    img = render(size)
    store = QByteArray()
    buf = QBuffer(store)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(store)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    assets = os.path.join(BASE, "assets")
    os.makedirs(assets, exist_ok=True)

    blobs = [(size, png_bytes(size)) for size in SIZES]
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries = b""
    data = b""
    for size, blob in blobs:
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0,
            0,
            1,
            32,
            len(blob),
            offset + len(data),
        )
        data += blob
    ico = header + entries + data
    ico_path = os.path.join(assets, "icon.ico")
    with open(ico_path, "wb") as fh:
        fh.write(ico)

    png_path = os.path.join(assets, "icon.png")
    with open(png_path, "wb") as fh:
        fh.write(png_bytes(256))
    print("wrote", ico_path, len(ico), "bytes;", png_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
