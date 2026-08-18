"""Pytest configuration for RET & NS Departures tests."""

from collections.abc import Generator
import threading

import pytest

# pytest-homeassistant-custom-component provides hass, enable_custom_integrations, etc.
pytest_plugins = "pytest_homeassistant_custom_component"  # pylint: disable=invalid-name


@pytest.fixture(scope="session", autouse=True)
def _ignore_safe_shutdown_loop_threads() -> Generator[None]:
    """Ignore leftover asyncio executor-shutdown threads on Python 3.12.

    Creating a config entry shuts down the default executor, which on 3.12
    starts a daemon named ``_run_safe_shutdown_loop``. Older
    pytest-homeassistant-custom-component builds (what pip installs for
    3.12) treat that as a leaked thread and fail teardown. Current Home
    Assistant allows the same thread; filter it so both CI versions pass.
    """
    original_enumerate = threading.enumerate

    def _enumerate() -> list[threading.Thread]:
        return [
            thread
            for thread in original_enumerate()
            if "_run_safe_shutdown_loop" not in thread.name
        ]

    threading.enumerate = _enumerate  # type: ignore[method-assign]
    try:
        yield
    finally:
        threading.enumerate = original_enumerate  # type: ignore[method-assign]
