"""TIA entry point.

Launches the PySide6 desktop application. Application bootstrap logic
lives in :mod:`tia.app`; this file stays intentionally thin.
"""

from __future__ import annotations

import logging
import sys

from tia import __app_name__, __version__
from tia.app import run

logger = logging.getLogger(__name__)


def main() -> int:
    """Configure logging, start TIA and return its exit code."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("Launching %s v%s ...", __app_name__, __version__)
    try:
        return run()
    except Exception:  # noqa: BLE001 - top-level guard for the GUI process
        logger.exception("Fatal error while running %s", __app_name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
