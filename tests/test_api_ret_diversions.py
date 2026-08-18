"""Tests for RET omleidingen parsing and halt matching."""

from custom_components.ret_ns_departures.api_ret_diversions import (
    extract_dienstregeling_urls,
    extract_halt_lines,
    extract_halt_name,
    match_stop_notice,
    parse_diversion_articles,
)

HOFPLEIN_HTML = """
<html><body>
<article class="article article--modal">
  <h2 class="banner__tophead">
    <p>Door werkzaamheden Hofplein rijden de tramlijnen 1, 3, 4, 6, 7, 8, 11, 12, 14 en 18 een gewijzigde route en hebben vervallen haltes.</p>
  </h2>
  <h3 class="banner__head">Richting: De Esch, Holy</h3>
  <div class="-mgb--xsm">
    Van: 18 juli 2026 05:00<br/>
    Tot: 23 november 2026 01:00<br/>
  </div>
  <p>Door werkzaamheden Hofplein rijden de tramlijnen 1, 3, 4, 6, 7, 8, 11, 12, 14 en 18 van 18 jul t/m 22 nov een gewijzigde route en hebben vervallen haltes.</p>
  <p>Vervallen haltes tram 8 beide richtingen:</p>
  <p>- Schiekade</p>
  <p>- Weena</p>
  <p>- Rotterdam Centraal</p>
  <p>Vervangende haltes tram 8 beide richtingen:</p>
  <p>- Provenierssingel</p>
  <p>- Achterzijde Rotterdam Centraal</p>
</article>
</body></html>
"""

HALT_HTML = """
<html><body>
<h1 class="text--white">Schiekade</h1>
<a aria-label="Lijn tram 8" class="line-number line-number--tram-8"
   href="/home/reizen/dienstregeling/tram-8.html">8</a>
</body></html>
"""


def test_parse_hofplein_article_extracts_cancelled_tram_8_stops():
    notices = parse_diversion_articles(HOFPLEIN_HTML)
    assert len(notices) == 1
    notice = notices[0]
    assert notice["title"] == "Werkzaamheden Hofplein"
    assert "8" in notice["lines"]
    assert "Schiekade" in notice["cancelled_by_line"]["8"]
    assert "Provenierssingel" in notice["replacements_by_line"]["8"]
    assert "23 november 2026" in notice["end_text"]


def test_match_schiekade_explains_empty_board():
    notices = parse_diversion_articles(HOFPLEIN_HTML)
    matched = match_stop_notice(
        notices,
        stop_name="Schiekade",
        stop_slug="schiekade",
        lines=["8"],
        line_urls={"8": "/home/reizen/dienstregeling/tram-8.html"},
    )
    assert matched is not None
    assert matched["cancelled_stop"] is True
    assert matched["situation"].startswith("Schiekade is vervallen tot")
    assert matched["replacement_stops"] == [
        "Provenierssingel",
        "Achterzijde Rotterdam Centraal",
    ]
    assert matched["url"] == (
        "https://www.ret.nl/home/reizen/dienstregeling/tram-8.html"
    )
    assert "23 november 2026" in matched["situation"]


def test_unrelated_halt_without_matching_line_is_ignored():
    notices = parse_diversion_articles(HOFPLEIN_HTML)
    assert (
        match_stop_notice(
            notices,
            stop_name="Zuidplein",
            stop_slug="zuidplein",
            lines=["70"],
        )
        is None
    )


def test_extract_halt_metadata():
    assert extract_halt_name(HALT_HTML) == "Schiekade"
    assert extract_halt_lines(HALT_HTML) == ["8"]
    assert extract_dienstregeling_urls(HALT_HTML)["8"].endswith("tram-8.html")
