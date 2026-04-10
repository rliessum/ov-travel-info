"""Pytest configuration for RET & NS Departures tests."""
import pytest


# pytest-homeassistant-custom-component provides many fixtures
# Import them here for easy access in test files
pytest_plugins = "pytest_homeassistant_custom_component"  # pylint: disable=invalid-name


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):  # pylint: disable=unused-argument
    """Enable custom integrations for all tests."""
    yield
