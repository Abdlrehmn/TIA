"""Basic console logging configuration for the backend."""

import logging


def configure_logging() -> None:
    """Configure readable application logs on the console."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
