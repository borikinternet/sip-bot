"""Logging setup for the application runtime."""

import logging
import sys

from .config import RuntimeConfig


def configure_logging(config: RuntimeConfig) -> logging.Logger:
    """Configure the application logger from an explicit runtime config.

    Configuration is idempotent and does not add a second handler when tests or
    an embedding process call it more than once.
    """

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(config.log_format, config.log_date_format))
        root.addHandler(handler)
    root.setLevel(config.log_level)
    return logging.getLogger(config.application_name)
