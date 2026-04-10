"""Shared helpers for aiohttp session mocking."""
from unittest.mock import AsyncMock, MagicMock


def mock_aiohttp_response(
    *,
    json_data=None,
    text: str | None = None,
):
    """Build a mock response object for use inside ``async with session.get(...)``."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    if json_data is not None:
        mock_response.json = AsyncMock(return_value=json_data)
    if text is not None:
        mock_response.text = AsyncMock(return_value=text)
    return mock_response


def attach_get_with_response(mock_session, mock_response) -> None:
    """Make ``session.get()`` work as an async context manager returning ``mock_response``."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = cm
