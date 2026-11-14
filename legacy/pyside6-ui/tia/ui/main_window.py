"""TIA main window: layout composition only.

All colors and styling come from :mod:`tia.ui.theme`; reusable controls
come from :mod:`tia.ui.widgets`. This module owns the arrangement of the
header, conversation area and footer.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from tia import __app_name__, __version__
from tia.ui.app_icon import create_app_icon
from tia.ui.widgets import MicControl, StatusLevel, StatusPill
from tia.ui.widgets.empty_state import EmptyState


class MainWindow(QMainWindow):
    """The primary TIA desktop window (Phase 1: interface only)."""

    DEFAULT_WIDTH = 980
    DEFAULT_HEIGHT = 660
    MIN_WIDTH = 760
    MIN_HEIGHT = 540

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{__app_name__} — Personal AI Desktop Agent")
        self.setWindowIcon(create_app_icon())
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        self._status_pill = StatusPill(
            StatusLevel.READY,
            "Ready · Local",
            "The interface is running. Voice, the AI brain and automation "
            "are not connected yet.",
        )
        self._command_input = self._build_command_input()
        self._mic_control = MicControl()

        self._build_layout()

    # --- layout assembly ---------------------------------------------------

    def _build_layout(self) -> None:
        central = QWidget()
        central.setObjectName("RootWindow")

        root = QVBoxLayout(central)
        root.setContentsMargins(28, 22, 28, 18)
        root.setSpacing(16)

        root.addLayout(self._build_header())
        root.addWidget(self._build_conversation_card(), stretch=1)
        root.addLayout(self._build_footer())

        self.setCentralWidget(central)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(12)

        orb = QLabel("T")
        orb.setObjectName("BrandOrb")
        orb.setFixedSize(44, 44)
        orb.setAlignment(Qt.AlignmentFlag.AlignCenter)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        name = QLabel(__app_name__)
        name.setObjectName("BrandName")
        tagline = QLabel("Personal AI Desktop Agent")
        tagline.setObjectName("BrandTagline")
        titles.addWidget(name)
        titles.addWidget(tagline)

        header.addWidget(orb)
        header.addLayout(titles)
        header.addStretch(1)
        header.addWidget(self._status_pill)
        return header

    def _build_conversation_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("ConversationArea")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(EmptyState())
        return card

    def _build_command_input(self) -> QLineEdit:
        command_input = QLineEdit()
        command_input.setObjectName("CommandInput")
        command_input.setPlaceholderText(
            "Text chat coming soon — typing isn't connected yet"
        )
        command_input.setEnabled(False)
        command_input.setToolTip(
            "Keyboard input will be enabled together with the AI brain."
        )
        command_input.setAccessibleName("Command input (not implemented yet)")
        command_input.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return command_input

    def _build_footer(self) -> QVBoxLayout:
        footer = QVBoxLayout()
        footer.setSpacing(8)

        controls = QHBoxLayout()
        controls.setSpacing(14)
        controls.addWidget(self._command_input, stretch=1)
        controls.addWidget(self._mic_control)
        footer.addLayout(controls)

        meta = QHBoxLayout()
        note = QLabel(
            "Voice, AI brain and automation are planned for upcoming "
            "phases — nothing is connected yet."
        )
        note.setObjectName("FooterNote")
        version = QLabel(f"{__app_name__} v{__version__} · Local & private")
        version.setObjectName("VersionLabel")
        meta.addWidget(note)
        meta.addStretch(1)
        meta.addWidget(version)
        footer.addLayout(meta)
        return footer

    # --- window behavior ----------------------------------------------------

    def center_on_screen(self) -> None:
        """Center the window inside the available area of its screen."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())
