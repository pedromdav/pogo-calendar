#!/usr/bin/env python3
"""Build a subscribable .ics calendar of Pokemon GO events.

Data comes from ScrapedDuck (a community-maintained JSON mirror of Leek Duck).
No third-party dependencies: stdlib only, so it runs anywhere (incl. CI).

Times in the source are *naive local times* (e.g. 14:00 with no timezone),
which is correct for Pokemon GO -- Community Days, Raid Hours, etc. happen at
the same wall-clock time in every player's local timezone. We pin the feed to a
chosen IANA timezone (default below) and embed that zone's DST rules as a
VTIMEZONE, because Google Calendar misreads timezone-less times as UTC.

Set the timezone with `--tz America/New_York` or the POGO_TZ env var (handy when
travelling: switch zones and rebuild). The embedded rules are derived from the
system tz database, so any IANA zone works.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json"
OUTPUT = Path(__file__).parent / "public" / "calendar.ics"

CALENDAR_NAME = "Pokemon GO Events"

# Timezone the feed is pinned to. Override with --tz or the POGO_TZ env var.
DEFAULT_TIMEZONE = "Europe/Zurich"

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


def fmt_offset(td: timedelta) -> str:
    """Format a UTC offset as +HHMM / -HHMM."""
    secs = int(td.total_seconds())
    sign = "+" if secs >= 0 else "-"
    secs = abs(secs)
    return f"{sign}{secs // 3600:02d}{(secs % 3600) // 60:02d}"


def build_vtimezone(tzid: str) -> list[str]:
    """Derive a VTIMEZONE for `tzid` from the system tz database.

    Scans hourly across a window around the current year, recording each DST
    transition as a STANDARD/DAYLIGHT subcomponent. Works for any IANA zone,
    including ones with no DST (single STANDARD subcomponent).
    """
    tz = ZoneInfo(tzid)
    year = datetime.now().year
    cur = datetime(year - 1, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 2, 1, 1, tzinfo=timezone.utc)
    step = timedelta(hours=1)

    def describe(instant: datetime) -> tuple[timedelta, str, bool]:
        loc = instant.astimezone(tz)
        is_dst = bool(loc.dst()) and loc.dst() != timedelta(0)
        return loc.utcoffset(), loc.tzname() or tzid, is_dst

    off, name, is_dst = describe(cur)
    subs: list[dict] = [
        {  # baseline: the offset already in effect at the window start
            "kind": "DAYLIGHT" if is_dst else "STANDARD",
            "from": off,
            "to": off,
            "name": name,
            "dtstart": (cur + off).strftime("%Y%m%dT%H%M%S"),
        }
    ]

    prev_off = off
    while cur <= end:
        off, name, is_dst = describe(cur)
        if off != prev_off:
            subs.append(
                {
                    "kind": "DAYLIGHT" if is_dst else "STANDARD",
                    "from": prev_off,
                    "to": off,
                    "name": name,
                    # onset expressed in the local time *before* the switch
                    "dtstart": (cur + prev_off).strftime("%Y%m%dT%H%M%S"),
                }
            )
            prev_off = off
        cur += step

    lines = ["BEGIN:VTIMEZONE", f"TZID:{tzid}"]
    for s in subs:
        lines += [
            f"BEGIN:{s['kind']}",
            f"TZOFFSETFROM:{fmt_offset(s['from'])}",
            f"TZOFFSETTO:{fmt_offset(s['to'])}",
            f"TZNAME:{s['name']}",
            f"DTSTART:{s['dtstart']}",
            f"END:{s['kind']}",
        ]
    lines.append("END:VTIMEZONE")
    return lines


def build_ics(events: list[dict], tzid: str) -> str:
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//pogo-calendar//Pokemon GO Events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape(CALENDAR_NAME)}",
        f"X-WR-TIMEZONE:{tzid}",
        "X-PUBLISHED-TTL:PT12H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
    ]
    lines += build_vtimezone(tzid)

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
            f"DTSTART;TZID={tzid}:{fmt_dt(start)}",
            f"DTEND;TZID={tzid}:{fmt_dt(end)}",
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
    parser = argparse.ArgumentParser(description="Build the Pokemon GO events .ics feed.")
    parser.add_argument(
        "--tz",
        default=os.environ.get("POGO_TZ") or DEFAULT_TIMEZONE,
        help="IANA timezone to pin the feed to (default: $POGO_TZ or %(default)s).",
    )
    args = parser.parse_args()

    try:
        ZoneInfo(args.tz)
    except Exception:  # noqa: BLE001
        print(f"Unknown timezone: {args.tz!r} (use an IANA name, e.g. America/New_York)", file=sys.stderr)
        return 2

    try:
        events = fetch_events()
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to fetch events: {exc}", file=sys.stderr)
        return 1

    ics = build_ics(events, args.tz)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(ics, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({args.tz})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
