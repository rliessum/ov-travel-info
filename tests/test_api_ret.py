"""Tests for the RET website client (HTML parsing)."""
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientError

from custom_components.ret_ns_departures.api_ret import RETAPIClient

from tests.helpers import attach_get_with_response, mock_aiohttp_response


def _ret_departure_row(
    line_text: str,
    destination: str,
    time_hm: str,
    *,
    minutes: str | None = "30",
) -> str:
    """Minimal HTML matching RETAPIClient._parse_departures selectors."""
    minutes_html = ""
    if minutes is not None:
        minutes_html = (
            f'<span class="favorite__time__amount minutes">{minutes}</span>'
        )
    return f"""<a class="modal__toggle--generated" href="#">
<span class="favorite__info">{line_text}</span>
<div class="favorite__stop">
<span class="favorite__info">Via</span>
<span class="favorite__info">{destination}</span>
</div>
<span class="favorite__time__amount">{time_hm}</span>
{minutes_html}
</a>"""


def _ret_page(*rows: str) -> str:
    return f"<html><body>{''.join(rows)}</body></html>"


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    return MagicMock()


@pytest.fixture
def ret_client(mock_session):
    """Create a RET API client with mocked session."""
    return RETAPIClient(mock_session)


@pytest.mark.asyncio
async def test_get_departures_parses_rows(ret_client, mock_session):
    """Departures are parsed from halt HTML; rows with relative minutes are kept as future."""
    html = _ret_page(
        _ret_departure_row("Tram 8", "Nesselande", "12:00", minutes="25"),
        _ret_departure_row("Bus 33", "Centrum", "12:05", minutes="40"),
    )
    attach_get_with_response(mock_session, mock_aiohttp_response(text=html))

    departures = await ret_client.async_get_departures("beurs", max_results=5)

    assert len(departures) == 2
    lines = {d["line"] for d in departures}
    assert lines == {"8", "33"}
    dests = {d["destination"] for d in departures}
    assert dests == {"Nesselande", "Centrum"}
    assert all(d["operator"] == "RET" for d in departures)
    assert departures[0]["actual_time"] <= departures[1]["actual_time"]


@pytest.mark.asyncio
async def test_get_departures_line_filter(ret_client, mock_session):
    """Line filter excludes non-matching lines."""
    html = _ret_page(
        _ret_departure_row("Tram 2", "A", "10:00", minutes="10"),
        _ret_departure_row("Tram 9", "B", "10:01", minutes="11"),
    )
    attach_get_with_response(mock_session, mock_aiohttp_response(text=html))

    departures = await ret_client.async_get_departures(
        "schiekade", max_results=5, line_filter=["2"]
    )

    assert len(departures) == 1
    assert departures[0]["line"] == "2"
    assert departures[0]["destination"] == "A"


@pytest.mark.asyncio
async def test_get_departures_stop_slug_in_url(ret_client, mock_session):
    """Stop ID is lowercased and spaces become hyphens in the request URL."""
    html = _ret_page(_ret_departure_row("Metro A", "X", "08:00", minutes="5"))
    attach_get_with_response(mock_session, mock_aiohttp_response(text=html))

    await ret_client.async_get_departures("Centraal Station", max_results=3)

    mock_session.get.assert_called_once()
    url = mock_session.get.call_args[0][0]
    assert url.endswith("/centraal-station.html")


@pytest.mark.asyncio
async def test_get_departures_network_error(ret_client, mock_session):
    """ClientError from aiohttp is propagated."""
    mock_session.get.side_effect = ClientError("Network error")

    with pytest.raises(ClientError):
        await ret_client.async_get_departures("beurs")


@pytest.mark.asyncio
async def test_get_departures_empty_html(ret_client, mock_session):
    """No matching rows yields an empty list."""
    attach_get_with_response(
        mock_session, mock_aiohttp_response(text="<html><body></body></html>")
    )

    departures = await ret_client.async_get_departures("beurs")

    assert departures == []


@pytest.mark.asyncio
async def test_validate_stop_success(ret_client, mock_session):
    """Validation succeeds when departures can be fetched."""
    html = _ret_page(_ret_departure_row("Tram 1", "Y", "09:00", minutes="15"))
    attach_get_with_response(mock_session, mock_aiohttp_response(text=html))

    assert await ret_client.async_validate_stop("beurs") is True


@pytest.mark.asyncio
async def test_validate_stop_client_error(ret_client, mock_session):
    """HTTP/client errors make validation False."""
    mock_session.get.side_effect = ClientError("Not found")

    assert await ret_client.async_validate_stop("unknown") is False


@pytest.mark.asyncio
async def test_validate_stop_timeout_still_true(ret_client, mock_session):
    """Non-ClientError exceptions are treated as inconclusive (True)."""
    mock_session.get.side_effect = TimeoutError()

    assert await ret_client.async_validate_stop("beurs") is True
