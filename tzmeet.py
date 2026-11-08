#!/usr/bin/env python3
"""tzmeet - find a meeting time that works in every timezone.

Somebody in Tashkent, somebody in Berlin, somebody in New York. Working
out which hours overlap is a small amount of arithmetic that goes wrong
reliably, usually in the direction of a 6am call for one person.

    tzmeet Asia/Tashkent Europe/Berlin America/New_York

Prints the slots that land inside everybody's working hours, with the
local time for each person, so nobody has to convert anything.

Exit codes: 0 found something, 2 usage, 3 no overlap at all.

Zero dependencies on macOS and Linux. On Windows, Python ships no timezone
database of its own, so `tzdata` is needed for named zones -- plain UTC
offsets work everywhere.
"""

import argparse
import datetime as dt
import json
import re
import sys

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:                                  # pragma: no cover
    ZoneInfo = None

    class ZoneInfoNotFoundError(Exception):
        pass

VERSION = "0.1.0"
EXIT_OK, EXIT_USAGE, EXIT_NONE = 0, 2, 3

OFFSET = re.compile(r"^(?:UTC|GMT)?(?P<sign>[+-])(?P<h>\d{1,2})(?::?(?P<m>\d{2}))?$", re.I)
WINDOW = re.compile(r"^(?P<a>\d{1,2})(?::(?P<am>\d{2}))?-(?P<b>\d{1,2})(?::(?P<bm>\d{2}))?$")


class ZoneError(ValueError):
    pass


class Zone:
    """A named zone, or a fixed offset."""

    def __init__(self, label, tzinfo):
        self.label, self.tzinfo = label, tzinfo

    def local(self, moment_utc):
        return moment_utc.astimezone(self.tzinfo)

    def __str__(self):
        return self.label


def parse_zone(text):
    text = text.strip()
    if not text:
        raise ZoneError("empty zone")
    m = OFFSET.match(text)
    if m:
        hours, minutes = int(m.group("h")), int(m.group("m") or 0)
        if hours > 14 or minutes > 59:
            raise ZoneError("offset out of range: %s" % text)
        delta = dt.timedelta(hours=hours, minutes=minutes)
        if m.group("sign") == "-":
            delta = -delta
        label = "UTC%s%02d:%02d" % (m.group("sign"), hours, minutes)
        return Zone(label, dt.timezone(delta))
    if ZoneInfo is None:
        raise ZoneError("named zones need Python 3.9+ with zoneinfo")
    try:
        return Zone(text, ZoneInfo(text))
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise ZoneError(
            "unknown timezone: %s (try a name like Europe/Berlin, or an "
            "offset like +05:00)" % text)


def parse_window(text):
    m = WINDOW.match(text.strip())
    if not m:
        raise ZoneError("working hours should look like 9-18 or 09:30-17:30")
    start = int(m.group("a")) * 60 + int(m.group("am") or 0)
    end = int(m.group("b")) * 60 + int(m.group("bm") or 0)
    if not 0 <= start < end <= 24 * 60:
        raise ZoneError("working hours out of range: %s" % text)
    return start, end


def slots(zones, window, duration, start_day, days, step=30):
    """Start times that land inside everyone's working hours.

    The comparison runs in UTC and each zone's local time is computed from
    it, so a daylight-saving change is handled correctly even when it
    happens in the middle of the range.
    """
    low, high = window
    found = []
    begin = dt.datetime.combine(start_day, dt.time(0, 0), tzinfo=dt.timezone.utc)
    total = days * 24 * 60
    for minutes in range(0, total, step):
        moment = begin + dt.timedelta(minutes=minutes)
        here_all = []
        for zone in zones:
            here = zone.local(moment)
            start_min = here.hour * 60 + here.minute
            if not (low <= start_min and start_min + duration <= high):
                here_all = None
                break
            here_all.append(here)
        if here_all:
            found.append((moment, here_all))
    return found


def render(zones, found, limit):
    width = max(len(str(z)) for z in zones)
    shown, last_day = 0, None
    for moment, here_all in found:
        if shown >= limit:
            break
        day = here_all[0].date()
        if day != last_day:
            if last_day is not None:
                print()
            print(here_all[0].strftime("%A %d %B"))
            last_day = day
        times = "  ".join("%s %s" % (str(z).ljust(width), here.strftime("%H:%M"))
                          for z, here in zip(zones, here_all))
        note = "  (different dates)" if len({h.date() for h in here_all}) > 1 else ""
        print("  " + times + note)
        shown += 1


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="tzmeet",
        description="Find a meeting time that works in every timezone.",
        epilog="example: tzmeet Asia/Tashkent Europe/Berlin America/New_York")
    p.add_argument("zones", nargs="*", metavar="ZONE",
                   help="a name like Europe/Berlin, or an offset like +05:00")
    p.add_argument("--hours", default="9-18", metavar="A-B",
                   help="working hours everyone keeps (default 9-18)")
    p.add_argument("--duration", type=int, default=60, metavar="MINUTES",
                   help="how long the meeting runs (default 60)")
    p.add_argument("--days", type=int, default=5, metavar="N",
                   help="how many days ahead to look (default 5)")
    p.add_argument("--from", dest="start", metavar="YYYY-MM-DD",
                   help="start looking from this date (default today)")
    p.add_argument("--limit", type=int, default=12, metavar="N",
                   help="how many slots to print (default 12)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--version", action="version", version="tzmeet " + VERSION)
    args = p.parse_args(argv)

    if len(args.zones) < 2:
        p.print_help()
        return EXIT_USAGE
    try:
        zones = [parse_zone(z) for z in args.zones]
        window = parse_window(args.hours)
        if args.duration <= 0 or args.days <= 0:
            raise ZoneError("duration and days must be positive")
        start_day = (dt.date.fromisoformat(args.start) if args.start
                     else dt.datetime.now(dt.timezone.utc).date())
    except (ZoneError, ValueError) as e:
        print("error: %s" % e, file=sys.stderr)
        return EXIT_USAGE

    found = slots(zones, window, args.duration, start_day, args.days)

    if args.json:
        print(json.dumps({
            "ok": bool(found),
            "zones": [str(z) for z in zones],
            "slots": [{"utc": moment.isoformat(),
                       "local": {str(z): here.isoformat()
                                 for z, here in zip(zones, here_all)}}
                      for moment, here_all in found[:args.limit]],
        }, indent=2, sort_keys=True))
    elif not found:
        print("no overlap: %s never share %s working hours"
              % (", ".join(str(z) for z in zones), args.hours), file=sys.stderr)
        print("try a wider --hours, or a shorter --duration", file=sys.stderr)
    else:
        render(zones, found, args.limit)
        if len(found) > args.limit:
            print("\n%d more slots (--limit to see them)" % (len(found) - args.limit))
    return EXIT_OK if found else EXIT_NONE


if __name__ == "__main__":
    sys.exit(main())
