"""A simple minimum-interval rate limiter, safe for sequential single-process use."""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """Blocks callers so that at most `max_calls` occur per `period_seconds`.

    Implemented as a fixed minimum interval between calls rather than a token
    bucket: sufficient for a script making sequential requests to one API.
    """

    def __init__(self, max_calls: int = 1, period_seconds: float = 1.0) -> None:
        if max_calls <= 0 or period_seconds <= 0:
            raise ValueError("max_calls and period_seconds must be positive")

        self._min_interval = period_seconds / max_calls
        self._lock = threading.Lock()
        self._last_call: float | None = None

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            if self._last_call is not None:
                wait_time = self._min_interval - (now - self._last_call)
                if wait_time > 0:
                    time.sleep(wait_time)
            self._last_call = time.monotonic()
