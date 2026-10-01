"""Logging configuration.

Kept separate from ``config`` so that logging can be initialised before anything
else runs, including settings parsing failures.
"""

from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

# These libraries log every HTTP request at INFO, which buries our own messages.
_NOISY_LOGGERS = ("httpx", "httpcore", "telegram.vendor", "apscheduler")


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format=_LOG_FORMAT,
        level=getattr(logging, level),
        stream=sys.stdout,
        force=True,
    )
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
