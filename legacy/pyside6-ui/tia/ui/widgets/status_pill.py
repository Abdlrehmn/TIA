"""Status indicator widget for TIA's main window."""

from __future__ import annotations

from enum import Enum

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget


class StatusLevel(Enum):
    """Semantic states the status pill can display."""

    OFFLINE = "offline"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"


class StatusPill(QFrame):
    """Compact rounded indicator with a colored dot and a status label.

    The dot color follows :class:`StatusLevel` through the stylesheet in
    :mod:`tia.ui.theme`; the label text describes the state in words.
    """

    def __init__(
        self,
        level: StatusLevel = StatusLevel.OFFLINE,
        text: str = "Offline",
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("StatusPill")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        if tooltip:
            self.setToolTip(tooltip)

        self._level = level

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(8)

        self._dot = QLabel()
        self._dot.setObjectName("StatusDot")
        self._dot.setFixedSize(9, 9)
        self._dot.setProperty("level", level.value)

        self._label = QLabel(text)
        self._label.setObjectName("StatusLabel")

        layout.addWidget(self._dot)
        layout.addWidget(self._label)

    def set_status(self, level: StatusLevel, text: str) -> None:
        """Switch the pill to *level* with the descriptive *text*."""
        if level is self._level and text == self._label.text():
            return
        self._level = level
        self._label.setText(text)
        self._refresh_dot_style()

    def _refresh_dot_style(self) -> None:
        self._dot.setProperty("level", self._level.value)
        style = self._dot.style()
        style.unpolish(self._dot)
        style.polish(self._dot)
