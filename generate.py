#!/usr/bin/env python3
"""Build a subscribable .ics calendar of Pokemon GO events.

Data comes from ScrapedDuck (a community-maintained JSON mirror of Leek Duck).
No third-party dependencies: stdlib only, so it runs anywhere (incl. CI).

Times in the source are *naive local times* (e.g. 14:00 with no timezone),
which is correct for Pokemon GO -- Community Days, Raid Hours, etc. happen at
the same wall-clock time in every player's local timezone. We therefore emit
"floating" calendar events (no TZID), so they land at the right local time for
whoever subscribes, wherever they are.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json"
OUTPUT = Path(__file__).parent / "public" / "calendar.ics"

CALENDAR_NAME = "Pokemon GO Events"

# Which Leek Duck eventTypes to include, mapped to a friendly emoji prefix that
# shows up in the calendar event title. Edit this dict to change what you track.
#   - Community Days & big events
#   - Raids (incl. raid hours)
INCLUDE = {
    "community-day": "🌟",
    "raid-battles": "⚔️",
    "raid-hour": "⚔️",
    "raid-day": "⚔️",
    "max-mondays": "⚔️",
    "pokemon-go-fest": "🎉",
    "event": "📅",
}

# Default duration when an event has no end time.
DEFAULT_DURATION = timedelta(hours=1)


def fetch_events(url: str = SOURCE_URL) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "pogo-calendar"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def parse_dt(value: str | None) -> datetime | None:
    """Parse '2026-06-20T14:00:00.000' (naive) robustly across Python versions."""
    if not value:
        return None
    text = value.strip().rstrip("Z")
    text = text.split(".")[0]  # drop fractional seconds
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(text, "%Y-%m-%dT%H:%M")
        except ValueError:
            return None


def escape(text: str) -> str:
    """Escape per RFC 5545 (commas, semicolons, backslashes, newlines)."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold(line: str) -> str:
    """Fold lines longer than 75 octets per RFC 5545 (continuation = space)."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    out = bytearray()
    start = 0
    first = True
    while start < len(raw):
        limit = 75 if first else 74  # leading space on continuation lines
        # don't split a multi-byte char: back off to a UTF-8 boundary
        end = min(start + limit, len(raw))
        while end < len(raw) and (raw[end] & 0xC0) == 0x80:
            end -= 1
        chunk = raw[start:end]
        if not first:
            out += b" "
        out += chunk + b"\r\n"
        start = end
        first = False
    return out.decode("utf-8").rstrip("\r\n")


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def build_ics(events: list[dict]) -> str:
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//pogo-calendar//Pokemon GO Events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape(CALENDAR_NAME)}",
        "X-PUBLISHED-TTL:PT12H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
    ]

    kept = 0
    for ev in events:
        etype = ev.get("eventType")
        if etype not in INCLUDE:
            continue
        start = parse_dt(ev.get("start"))
        if start is None:
            continue
        end = parse_dt(ev.get("end")) or (start + DEFAULT_DURATION)
        if end <= start:
            end = start + DEFAULT_DURATION

        emoji = INCLUDE[etype]
        name = ev.get("name", "Pokemon GO Event")
        title = f"{emoji} {name}"

        uid = ev.get("eventID") or f"{name}-{fmt_dt(start)}"
        link = ev.get("link", "")
        heading = ev.get("heading", "")
        desc_parts = [p for p in (heading, link) if p]
        description = "\\n".join(escape(p) for p in desc_parts)

        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}@pogo-calendar",
            f"DTSTAMP:{now_stamp}",
            fold(f"SUMMARY:{escape(title)}"),
            f"DTSTART:{fmt_dt(start)}",
            f"DTEND:{fmt_dt(end)}",
        ]
        if description:
            lines.append(fold(f"DESCRIPTION:{description}"))
        if link:
            lines.append(fold(f"URL:{escape(link)}"))
        lines.append("END:VEVENT")
        kept += 1

    lines.append("END:VCALENDAR")
    print(f"Included {kept} of {len(events)} events.", file=sys.stderr)
    return "\r\n".join(lines) + "\r\n"


def main() -> int:
    try:
        events = fetch_events()
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to fetch events: {exc}", file=sys.stderr)
        return 1
    ics = build_ics(events)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(ics, encoding="utf-8")
    print(f"Wrote {OUTPUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
