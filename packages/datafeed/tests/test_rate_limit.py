from unittest.mock import patch

from equicast_datafeed.rate_limit import RateLimiter


def test_first_call_does_not_sleep() -> None:
    limiter = RateLimiter(max_calls=1, period_seconds=1.0)

    with patch("equicast_datafeed.rate_limit.time.sleep") as mock_sleep:
        limiter.acquire()

    mock_sleep.assert_not_called()


def test_second_call_within_window_sleeps_for_remaining_interval() -> None:
    limiter = RateLimiter(max_calls=1, period_seconds=1.0)

    with patch("equicast_datafeed.rate_limit.time.monotonic", side_effect=[0.0, 0.0, 0.2, 0.2]):
        with patch("equicast_datafeed.rate_limit.time.sleep") as mock_sleep:
            limiter.acquire()
            limiter.acquire()

    mock_sleep.assert_called_once()
    (slept_for,) = mock_sleep.call_args.args
    assert slept_for == 0.8


def test_invalid_arguments_raise() -> None:
    for kwargs in ({"max_calls": 0}, {"period_seconds": 0}, {"max_calls": -1}):
        try:
            RateLimiter(**kwargs)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {kwargs}")
