"""Visual theme for TIA: dark navy palette, cyan accent, shared stylesheet.

Design tokens live here so every widget pulls colors from a single
source of truth. :func:`apply_theme` applies the palette and stylesheet
once to the :class:`~PySide6.QtWidgets.QApplication`.
"""

from __future__ import annotations

from string import Template

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication


class Palette:
    """Design tokens for the TIA dark theme."""

    BG = "#0A1526"
    SURFACE = "#0E1D33"
    SURFACE_2 = "#132643"
    BORDER = "#1D3252"
    TEXT = "#E8F1FB"
    TEXT_MUTED = "#8AA5C6"
    TEXT_FAINT = "#5A7099"
    ACCENT = "#22D3EE"
    ACCENT_SOFT = "rgba(34, 211, 238, 0.14)"
    SUCCESS = "#34D399"
    WARNING = "#FBBF24"
    DANGER = "#F87171"
    OFFLINE = "#64748B"


# Tokens referenced by the stylesheet below via ``$NAME`` substitution.
_TOKENS = {
    name: value
    for name, value in vars(Palette).items()
    if name.isupper() and isinstance(value, str)
}

_STYLESHEET = Template("""\
/* Base ---------------------------------------------------------------- */
QWidget {
    font-family: "Segoe UI";
}

QMainWindow,
QWidget#RootWindow {
    background: $BG;
}

QToolTip {
    background: $SURFACE_2;
    color: $TEXT;
    border: 1px solid $BORDER;
    padding: 6px 8px;
}

/* Header --------------------------------------------------------------- */
QLabel#BrandOrb {
    color: $ACCENT;
    font-size: 16px;
    font-weight: 700;
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                stop: 0 $SURFACE_2, stop: 1 $BG);
    border: 1px solid $ACCENT_SOFT;
    border-radius: 22px;
}

QLabel#BrandName {
    color: $TEXT;
    font-size: 20px;
    font-weight: 700;
}

QLabel#BrandTagline {
    color: $TEXT_MUTED;
    font-size: 12px;
}

/* Status pill ----------------------------------------------------------- */
QFrame#StatusPill {
    background: $SURFACE;
    border: 1px solid $BORDER;
    border-radius: 14px;
}

QLabel#StatusDot {
    background: $OFFLINE;
    border-radius: 4px;
}

QLabel#StatusDot[level="ready"]   { background: $SUCCESS; }
QLabel#StatusDot[level="busy"]    { background: $WARNING; }
QLabel#StatusDot[level="error"]   { background: $DANGER; }
QLabel#StatusDot[level="offline"] { background: $OFFLINE; }

QLabel#StatusLabel {
    color: $TEXT_MUTED;
    font-size: 12px;
    font-weight: 600;
}

/* Conversation area ----------------------------------------------------- */
QFrame#ConversationArea {
    background: $SURFACE;
    border: 1px solid $BORDER;
    border-radius: 16px;
}

QLabel#EmptyStateOrb {
    color: $ACCENT;
    font-size: 26px;
    font-weight: 700;
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                stop: 0 $SURFACE_2, stop: 1 $BG);
    border: 2px solid $ACCENT_SOFT;
    border-radius: 48px;
}

QLabel#Greeting {
    color: $TEXT;
    font-size: 30px;
    font-weight: 700;
}

QLabel#Subtitle {
    color: $TEXT_MUTED;
    font-size: 14px;
}

QLabel#Hint {
    color: $TEXT_FAINT;
    font-size: 12px;
}

QLabel#Chip {
    color: $TEXT_MUTED;
    background: $SURFACE_2;
    border: 1px solid $BORDER;
    border-radius: 13px;
    padding: 5px 13px;
    font-size: 12px;
}

/* Footer ---------------------------------------------------------------- */
QLineEdit#CommandInput {
    background: $SURFACE;
    border: 1px solid $BORDER;
    border-radius: 14px;
    padding: 11px 18px;
    color: $TEXT;
    font-size: 13px;
    selection-background-color: $ACCENT;
    selection-color: #06222A;
}

QLineEdit#CommandInput:disabled {
    background: rgba(14, 29, 51, 0.5);
    border: 1px solid rgba(29, 50, 82, 0.7);
    color: $TEXT_FAINT;
}

QPushButton#MicButton {
    background: $SURFACE_2;
    border: 2px solid $BORDER;
    border-radius: 28px;
}

QPushButton#MicButton:hover {
    background: $SURFACE_2;
    border: 2px solid $ACCENT;
}

QPushButton#MicButton:pressed {
    background: $SURFACE;
}

QPushButton#MicButton:disabled {
    background: rgba(19, 38, 67, 0.55);
    border: 2px solid rgba(29, 50, 82, 0.8);
}

QLabel#MicCaption {
    color: $TEXT_FAINT;
    font-size: 11px;
    font-weight: 600;
}

QLabel#FooterNote {
    color: $TEXT_FAINT;
    font-size: 11px;
}

QLabel#VersionLabel {
    color: $TEXT_FAINT;
    font-size: 11px;
}
""")


def apply_theme(app: QApplication) -> None:
    """Apply TIA's dark theme (palette, base font, stylesheet) to *app*."""
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(Palette.BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(Palette.TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(Palette.SURFACE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(Palette.SURFACE_2))
    palette.setColor(QPalette.ColorRole.Text, QColor(Palette.TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(Palette.SURFACE_2))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(Palette.TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(Palette.ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#06222A"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(Palette.TEXT_FAINT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(Palette.SURFACE_2))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(Palette.TEXT))
    app.setPalette(palette)

    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(_STYLESHEET.substitute(_TOKENS))
