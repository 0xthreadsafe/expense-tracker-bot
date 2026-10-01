"""Entry point: ``python -m expensebot`` or the ``expensebot`` console script."""

from __future__ import annotations

import logging
import sys

from pydantic import ValidationError

from expensebot.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def run() -> None:
    # Logging is configured twice on purpose: once with defaults so that a
    # configuration error can be reported at all, then again at the level the
    # configuration actually asks for.
    configure_logging()
    try:
        from expensebot.app import run as run_app
        from expensebot.config import get_settings

        configure_logging(get_settings().log_level)
        run_app()
    except ValidationError as exc:
        # A configuration mistake is a user error, not a crash: report it plainly
        # and exit non-zero so a supervisor does not restart-loop on it.
        logger.error("Invalid configuration:\n%s", exc)
        sys.exit(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
