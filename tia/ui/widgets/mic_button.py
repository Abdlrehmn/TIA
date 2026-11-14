"""Microphone control widget.

Voice input is not implemented yet, so the button ships disabled and is
labeled "Coming soon" until the voice pipeline lands.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from tia.ui.theme import Palette

_MIC_TOOLTIP = (
    "Microphone integration is not implemented yet.\n"
    "Planned for an upcoming phase: wake word and push-to-talk voice input."
)

_MIC_SVG_TEMPLATE = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <rect x="9" y="3" width="6" height="10" rx="3" fill="{color}"/>
  <path d="M6 12 A6 6 0 0 0 18 12" fill="none" stroke="{color}"
        stroke-width="1.8" stroke-linecap="round"/>
  <line x1="12" y1="18" x2="12" y2="21" stroke="{color}"
        stroke-width="1.8" stroke-linecap="round"/>
  <line x1="8.5" y1="21" x2="15.5" y2="21" stroke="{color}"
        stroke-width="1.8" stroke-linecap="round"/>
</svg>
"""


def _load_mic_icon(color: str = Palette.ACCENT, size: int = 128) -> QIcon:
    """Render the inline mic SVG into a tinted :class:`QIcon`."""
    renderer = QSvgRenderer(QByteArray(_MIC_SVG_TEMPLATE.replace("{color}", color).encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    return QIcon(pixmap)


class MicButton(QPushButton):
    """Round microphone button; disabled until voice input is implemented."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MicButton")
        self.setFixedSize(56, 56)
        self.setIcon(_load_mic_icon())
        self.setIconSize(QSize(26, 26))
        self.setEnabled(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(_MIC_TOOLTIP)
        self.setAccessibleName("Microphone control (not implemented yet)")


class MicControl(QWidget):
    """Mic button with a "coming soon" caption beneath it."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setToolTip(_MIC_TOOLTIP)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        self.button = MicButton()
        caption = QLabel("Coming soon")
        caption.setObjectName("MicCaption")
        caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(self.button, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(caption)
