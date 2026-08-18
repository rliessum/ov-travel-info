"""Parse RET omleidingen / dienstregeling notices for a halt."""
from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from .const import RET_DIENSTREGELING_BASE_URL, RET_DIVERSIONS_URL

_LINE_LIST_RE = re.compile(
    r"(?:nachtbus|tram|bus|metro)(?:lijnen?)?\s+"
    r"([0-9A-Za-z]+(?:\s*[,/]\s*[0-9A-Za-z]+|\s+en\s+[0-9A-Za-z]+)*)",
    re.IGNORECASE,
)
_VAN_TOT_RE = re.compile(
    r"Van:\s*(.+?)\s*Tot:\s*(.+?)(?:\s*$)",
    re.IGNORECASE | re.DOTALL,
)
_CANCELLED_HEADER_RE = re.compile(
    r"^Vervallen haltes(?:\s+(?:nachtbus|tram|bus|metro)\s+([0-9A-Za-z]+))?",
    re.IGNORECASE,
)
_REPLACEMENT_HEADER_RE = re.compile(
    r"^Vervangende haltes(?:\s+(?:nachtbus|tram|bus|metro)\s+([0-9A-Za-z]+))?",
    re.IGNORECASE,
)
_STOP_ITEM_RE = re.compile(r"^[-•]\s+(.+)")
_WORKS_RE = re.compile(r"werkzaamheden\s+(\S+)", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def parse_diversion_articles(html: str) -> list[dict[str, Any]]:
    """Turn RET omleidingen articles into structured notices."""
    soup = BeautifulSoup(html, "html.parser")
    notices: list[dict[str, Any]] = []
    for index, article in enumerate(soup.select("article.article--modal")):
        notice = _parse_article(article, index)
        if notice:
            notices.append(notice)
    return notices


def match_stop_notice(
    notices: list[dict[str, Any]],
    *,
    stop_name: str,
    stop_slug: str,
    lines: list[str] | None = None,
    line_urls: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Pick the diversion that explains an empty or cancelled halt."""
    wanted_lines = {str(line).strip() for line in (lines or []) if str(line).strip()}
    cancelled_hits: list[dict[str, Any]] = []
    line_hits: list[dict[str, Any]] = []

    for notice in notices:
        if _halt_is_cancelled(notice, stop_name, stop_slug):
            cancelled_hits.append(notice)
        elif wanted_lines and wanted_lines.intersection(notice.get("lines") or []):
            line_hits.append(notice)

    if cancelled_hits and wanted_lines:
        lined = [
            notice
            for notice in cancelled_hits
            if wanted_lines.intersection(notice.get("lines") or [])
        ]
        if lined:
            cancelled_hits = lined

    chosen = cancelled_hits or line_hits
    if not chosen:
        return None
    return format_stop_notice(
        chosen[0],
        stop_name=stop_name,
        stop_slug=stop_slug,
        lines=sorted(wanted_lines),
        line_urls=line_urls,
    )


def format_stop_notice(
    notice: dict[str, Any],
    *,
    stop_name: str,
    stop_slug: str,
    lines: list[str],
    line_urls: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a disruption-shaped dict for Home Assistant more-info."""
    halt_label = (stop_name or stop_slug.replace("-", " ")).strip()
    replacements = _replacements_for_halt(notice, halt_label, stop_slug, lines)
    cancelled = _halt_is_cancelled(notice, stop_name, stop_slug)
    period = str(notice.get("period") or "").strip()
    until = str(notice.get("end_text") or "").strip()

    if cancelled:
        situation = f"{halt_label} is vervallen"
        if until:
            situation = f"{situation} tot {until}"
        if replacements:
            situation = f"{situation}. Vervangende halte: {', '.join(replacements)}"
    elif lines:
        situation = f"Lijn {', '.join(lines)} rijdt een gewijzigde route"
        if until:
            situation = f"{situation} tot {until}"
    else:
        situation = str(notice.get("summary") or "").strip()

    matched_lines = lines or list(notice.get("lines") or [])
    return {
        "id": notice.get("id") or f"ret-{halt_label}",
        "title": notice.get("title") or "Gewijzigde dienstregeling",
        "type": "MAINTENANCE",
        "cause": notice.get("cause") or notice.get("title"),
        "situation": situation,
        "period": period,
        "expected_duration": f"Tot {until}" if until else period,
        "stations": [halt_label] if halt_label else [],
        "replacement_stops": replacements,
        "lines": matched_lines,
        "url": _source_url(matched_lines, line_urls),
        "cancelled_stop": cancelled,
    }


def extract_halt_lines(html: str) -> list[str]:
    """Line numbers linked from the halt page line overview."""
    soup = BeautifulSoup(html, "html.parser")
    lines: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select('a.line-number[href*="/dienstregeling/"]'):
        line = anchor.get_text(strip=True)
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    return lines


def extract_halt_name(html: str) -> str:
    """Visible halt title from the page header."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1.text--white") or soup.find("h1")
    return heading.get_text(strip=True) if heading else ""


def extract_dienstregeling_urls(html: str) -> dict[str, str]:
    """Map line number to its dienstregeling path on the halt page."""
    soup = BeautifulSoup(html, "html.parser")
    urls: dict[str, str] = {}
    for anchor in soup.select('a.line-number[href*="/dienstregeling/"]'):
        line = anchor.get_text(strip=True)
        href = str(anchor.get("href") or "")
        if line and href and line not in urls:
            urls[line] = href
    return urls


def _parse_article(article: Any, index: int) -> dict[str, Any] | None:
    heading = article.select_one("h2")
    title_full = heading.get_text(" ", strip=True) if heading else ""
    if not title_full:
        return None

    date_block = article.find("div", class_="-mgb--xsm")
    date_text = date_block.get_text(" ", strip=True) if date_block else ""
    start_text = ""
    end_text = ""
    match = _VAN_TOT_RE.search(date_text)
    if match:
        start_text = re.sub(r"\s+", " ", match.group(1)).strip()
        end_text = re.sub(r"\s+", " ", match.group(2)).strip()

    paragraphs = [
        para.get_text(" ", strip=True)
        for para in article.find_all("p")
        if para.get_text(strip=True)
    ]
    summary = paragraphs[0] if paragraphs else title_full
    lines = _lines_from_text(" ".join([title_full, *paragraphs[:3]]))
    cancelled_by_line, replacements_by_line = _parse_stop_lists(
        article.get_text("\n", strip=True)
    )
    for line in (*cancelled_by_line, *replacements_by_line):
        if line and line not in lines:
            lines.append(line)

    works = _WORKS_RE.search(title_full)
    cause = f"Werkzaamheden {works.group(1).strip()}" if works else title_full
    title = cause if works else title_full.split(".")[0].strip()

    period = ""
    if start_text and end_text:
        period = f"{start_text} – {end_text}"

    return {
        "id": f"ret-diversion-{index}",
        "title": title,
        "cause": cause,
        "summary": summary,
        "period": period,
        "start_text": start_text,
        "end_text": end_text,
        "lines": lines,
        "cancelled_by_line": cancelled_by_line,
        "replacements_by_line": replacements_by_line,
    }


def _parse_stop_lists(text: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    cancelled: dict[str, list[str]] = {}
    replacements: dict[str, list[str]] = {}
    section: str | None = None
    current_line = ""
    target: dict[str, list[str]] = cancelled

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        cancelled_header = _CANCELLED_HEADER_RE.match(line)
        if cancelled_header:
            section = "cancelled"
            current_line = (cancelled_header.group(1) or "").strip()
            target = cancelled
            target.setdefault(current_line, [])
            continue
        replacement_header = _REPLACEMENT_HEADER_RE.match(line)
        if replacement_header:
            section = "replacement"
            current_line = (replacement_header.group(1) or "").strip()
            target = replacements
            target.setdefault(current_line, [])
            continue
        if section is None:
            continue
        item = _STOP_ITEM_RE.match(line)
        if item:
            stop = item.group(1).strip()
            if stop and stop.lower() not in {"geen"}:
                target.setdefault(current_line, []).append(stop)
    return cancelled, replacements


def _lines_from_text(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _LINE_LIST_RE.finditer(text):
        blob = match.group(1).replace(" en ", ",")
        for part in re.split(r"[,/]", blob):
            line = part.strip()
            if line and line not in seen:
                seen.add(line)
                found.append(line)
    return found


def _halt_is_cancelled(notice: dict[str, Any], stop_name: str, stop_slug: str) -> bool:
    for stops in (notice.get("cancelled_by_line") or {}).values():
        if any(_names_match(stop_name, stop_slug, stop) for stop in stops):
            return True
    return False


def _replacements_for_halt(
    notice: dict[str, Any],
    stop_name: str,
    stop_slug: str,
    lines: list[str],
) -> list[str]:
    replacements_by_line: dict[str, list[str]] = (
        notice.get("replacements_by_line") or {}
    )
    cancelled_by_line: dict[str, list[str]] = notice.get("cancelled_by_line") or {}
    picked: list[str] = []
    seen: set[str] = set()

    relevant_lines = [
        line
        for line, stops in cancelled_by_line.items()
        if any(_names_match(stop_name, stop_slug, stop) for stop in stops)
    ]
    if not relevant_lines:
        relevant_lines = list(lines)

    for line in (*relevant_lines, ""):
        for stop in replacements_by_line.get(line, []):
            key = _norm(stop)
            if key and key not in seen:
                seen.add(key)
                picked.append(stop)
    return picked


def _names_match(stop_name: str, stop_slug: str, candidate: str) -> bool:
    cand = _norm(candidate)
    if not cand:
        return False
    for raw in (stop_name, stop_slug.replace("-", " ")):
        name = _norm(raw)
        if name and (name == cand or name in cand or cand in name):
            return True
    return False


def _norm(value: str) -> str:
    return " ".join(_TOKEN_RE.findall(value.casefold()))


def _source_url(lines: list[str], line_urls: dict[str, str] | None) -> str:
    for line in lines:
        href = (line_urls or {}).get(line)
        if not href:
            continue
        if href.startswith("http"):
            return href
        return f"https://www.ret.nl{href}"
    if len(lines) == 1 and lines[0].isalpha():
        return f"{RET_DIENSTREGELING_BASE_URL}/metro-{lines[0].lower()}.html"
    return RET_DIVERSIONS_URL
