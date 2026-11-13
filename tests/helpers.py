"""Shared helpers for aiohttp session mocking."""
from unittest.mock import AsyncMock, MagicMock


def mock_aiohttp_response(
    *,
    json_data=None,
    text: str | None = None,
    status: int = 200,
):
    """Build a mock response object for use inside ``async with session.get(...)``."""
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value=json_data if json_data is not None else {})
    if text is not None:
        mock_response.text = AsyncMock(return_value=text)
    return mock_response


def attach_get_with_response(mock_session, mock_response) -> None:
    """Make ``session.get()`` work as an async context manager returning ``mock_response``."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = cm


def attach_get_router(mock_session, routes: list[tuple[str, object]]) -> None:
    """Route ``session.get(url)`` to a mock response by URL substring."""

    def _get(url, *_args, **_kwargs):
        for needle, response in routes:
            if needle in url:
                cm = MagicMock()
                cm.__aenter__ = AsyncMock(return_value=response)
                cm.__aexit__ = AsyncMock(return_value=False)
                return cm
        raise AssertionError(f"Unexpected GET {url}")

    mock_session.get.side_effect = _get


def set_body(mock_response, body: bytes, chunk_size: int | None = None) -> None:
    """Make ``response.content.iter_chunked()`` stream ``body``."""

    def _iter_chunked(_size):
        async def _chunks():
            step = chunk_size or max(len(body), 1)
            for start in range(0, len(body), step):
                yield body[start : start + step]

        return _chunks()

    mock_response.content.iter_chunked = _iter_chunked
