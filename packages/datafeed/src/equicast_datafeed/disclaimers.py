"""Shared once-per-process console disclaimers for equicast's market-data packages."""

from __future__ import annotations

import logging
import threading

#: Shown by DatafeedClient and FXClient alike (identical text, so constructing
#: many of either in one process only logs it once, not once per instance).
YFINANCE_DATA_DISCLAIMER = (
    "equicast: data via yfinance (Yahoo Finance), for educational purposes only "
    "- not financial advice."
)

_shown: set[str] = set()
_lock = threading.Lock()


def warn_once(logger: logging.Logger, message: str) -> None:
    """Log `message` at WARNING level the first time it's seen in this process.

    Tracked by message text (not caller), so the same disclaimer shown by
    multiple classes only logs once, while a differently-worded one still
    logs independently. If nothing has configured a logging handler, this
    still reaches the console via Python's own "handler of last resort".
    """
    with _lock:
        if message in _shown:
            return
        _shown.add(message)
    logger.warning(message)


def reset_warned() -> None:
    """Clear the "already shown" state. Test-only; not part of the public API."""
    with _lock:
        _shown.clear()
