import logging

import pytest
from equicast_datafeed.disclaimers import reset_warned, warn_once


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_warned()
    yield
    reset_warned()


def test_warn_once_logs_the_first_time(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("test.warn_once")
    with caplog.at_level(logging.WARNING):
        warn_once(logger, "hello")

    assert caplog.messages == ["hello"]


def test_warn_once_does_not_repeat_the_same_message(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("test.warn_once")
    with caplog.at_level(logging.WARNING):
        warn_once(logger, "hello")
        warn_once(logger, "hello")

    assert caplog.messages == ["hello"]


def test_warn_once_logs_a_different_message_independently(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("test.warn_once")
    with caplog.at_level(logging.WARNING):
        warn_once(logger, "hello")
        warn_once(logger, "goodbye")

    assert caplog.messages == ["hello", "goodbye"]
