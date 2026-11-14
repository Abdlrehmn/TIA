"""Central empty-state area for TIA's conversation region."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

_GREETING = "Hello, I'm TIA"
_SUBTITLE = (
    "Your local, private desktop assistant. I'm being built to understand "
    "English and Roman Urdu — voice, chat and automation features arrive "
    "in upcoming phases."
)
_HINT = "Everything will run on this computer. No cloud required."

_CAPABILITY_CHIPS: tuple[str, ...] = (
    "Voice · soon",
    "Chat · soon",
    "Web research · soon",
    "Automation · soon",
)


class EmptyState(QWidget):
    """Greeting shown while the conversation area has no messages yet."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(14)
        layout.addStretch(1)

        self._orb = QLabel("TIA")
        self._orb.setObjectName("EmptyStateOrb")
        self._orb.setFixedSize(96, 96)
        self._orb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._orb, alignment=Qt.AlignmentFlag.AlignHCenter)

        greeting = QLabel(_GREETING)
        greeting.setObjectName("Greeting")
        layout.addWidget(greeting, alignment=Qt.AlignmentFlag.AlignHCenter)

        subtitle = QLabel(_SUBTITLE)
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        subtitle.setMaximumWidth(470)
        subtitle.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(4)
        layout.addLayout(self._build_chip_row())

        hint = QLabel(_HINT)
        hint.setObjectName("Hint")
        layout.addWidget(hint, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)

    @staticmethod
    def _build_chip_row() -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        for text in _CAPABILITY_CHIPS:
            chip = QLabel(text)
            chip.setObjectName("Chip")
            row.addWidget(chip)
        row.addStretch(1)
        return row
