"""Programmatically drawn TIA application icon.

Draws a navy rounded plate with a cyan ring and the TIA letter mark, so
the project needs no binary image assets.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap

from tia.ui.theme import Palette


def create_app_icon(size: int = 256) -> QIcon:
    """Render the TIA icon at *size* pixels and return it as a :class:`QIcon`."""
    return QIcon(_render_logo_pixmap(size))


def _render_logo_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    try:
        _draw_plate(painter, size)
        _draw_ring(painter, size)
        _draw_letter_mark(painter, size)
    finally:
        painter.end()
    return pixmap


def _draw_plate(painter: QPainter, size: int) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(Palette.BG))
    radius = size * 0.22
    painter.drawRoundedRect(QRectF(0.0, 0.0, size, size), radius, radius)


def _draw_ring(painter: QPainter, size: int) -> None:
    pen = QPen(QColor(Palette.ACCENT), size * 0.045)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    inset = size * 0.12
    painter.drawEllipse(QRectF(inset, inset, size - 2 * inset, size - 2 * inset))


def _draw_letter_mark(painter: QPainter, size: int) -> None:
    font = QFont("Segoe UI")
    font.setBold(True)
    font.setPixelSize(int(size * 0.34))
    painter.setFont(font)
    painter.setPen(QColor(Palette.TEXT))
    painter.drawText(QRectF(0.0, 0.0, size, size), Qt.AlignmentFlag.AlignCenter, "T")
