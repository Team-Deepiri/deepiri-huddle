"""Configure logging for the ``huddle`` package (stderr, structured-ish messages)."""

from __future__ import annotations

import logging
import sys
from typing import Final

_HUDDLE_LOGGER_NAME: Final[str] = "huddle"


def configure_logging(*, verbose: bool = False) -> None:
    """
    Attach a stderr handler to the ``huddle`` logger once.

    Respects ``HUDDLE_LOG_LEVEL`` from :class:`huddle.config.Settings` unless
    ``verbose`` is True (then DEBUG). Safe to call multiple times.
    """
    from huddle.config import Settings

    settings = Settings()
    logger = logging.getLogger(_HUDDLE_LOGGER_NAME)
    desired = (
        logging.DEBUG
        if verbose
        else getattr(logging, settings.huddle_log_level.upper(), logging.INFO)
    )

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(levelname)s [%(name)s] %(message)s"),
        )
        logger.addHandler(handler)
        logger.propagate = False
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logger.setLevel(desired)
        return

    if verbose:
        logger.setLevel(logging.DEBUG)
    elif logger.level != logging.DEBUG:
        logger.setLevel(desired)
