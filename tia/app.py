"""Application bootstrap for TIA's desktop interface.

Owns the QApplication lifecycle, theming and top-level startup logging.
Voice, AI and automation modules will attach here in later phases.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QApplication

from tia import __app_name__, __version__
from tia.ui.app_icon import create_app_icon
from tia.ui.main_window import MainWindow
from tia.ui.theme import apply_theme

logger = logging.getLogger(__name__)


def run() -> int:
    """Create the Qt application, show the main window and run the loop."""
    app = QApplication([])
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("TIA")

    apply_theme(app)
    app.setWindowIcon(create_app_icon())

    window = MainWindow()
    window.center_on_screen()
    window.show()

    logger.info("%s v%s main window shown; entering Qt event loop", __app_name__, __version__)
    exit_code = app.exec()
    logger.info("%s closed with exit code %d", __app_name__, exit_code)
    return exit_code
