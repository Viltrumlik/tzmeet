<h1 align="center">tzmeet</h1>

<p align="center">
  <b>Find a meeting time that works in every timezone.</b>
</p>

<p align="center">
  <a href="https://github.com/Viltrumlik/tzmeet/actions/workflows/ci.yml"><img src="https://github.com/Viltrumlik/tzmeet/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/dependencies-0-brightgreen" alt="Zero dependencies">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT"></a>
</p>

Somebody in Tashkent, somebody in Berlin, somebody in New York. The arithmetic is small and goes wrong reliably — usually in the direction of a 6am call for whoever was not in the room when it was scheduled.

```console
$ tzmeet Asia/Tokyo America/Los_Angeles --days 1
Sunday 08 November
  Asia/Tokyo          09:00  America/Los_Angeles 16:00  (different dates)
  Asia/Tokyo          09:30  America/Los_Angeles 16:30  (different dates)
```

Every row is one meeting, shown in each person's own local time. Nobody converts anything.

## When there is no answer, it says so

```console
$ tzmeet Asia/Tashkent Europe/Berlin America/New_York
no overlap: Asia/Tashkent, Europe/Berlin, America/New_York never share 9-18 working hours
try a wider --hours, or a shorter --duration
```

That is not a bug. Tashkent at 09:00–17:00 is 04:00–12:00 UTC; New York at 09:00–17:00 is 14:00–22:00 UTC. They do not touch. Better to learn it in a second than after three reschedules.

Exit code `3` means exactly this — so a script can branch on it.

## Zones

| You write | Meaning |
|---|---|
| `Europe/Berlin` | an IANA name, with daylight saving handled |
| `+5` `+05:00` `UTC+5` | a fixed offset |
| `-03:30` | half-hour offsets too |

## Options

| | |
|---|---|
| `--hours 9-18` | working hours everyone keeps (also `09:30-17:30`) |
| `--duration 60` | meeting length in minutes; the whole meeting must fit |
| `--days 5` | how far ahead to look |
| `--from 2026-11-10` | start from a given date |
| `--limit 12` | how many slots to print |
| `--json` | machine-readable |

Exit codes: `0` found something · `2` usage · `3` no overlap.

## Daylight saving

The comparison runs in UTC and each local time is derived from it, so a clock change inside the range is handled — including on the day it happens. There is a test for the European switch on 2026-10-25.

## Install

```bash
pipx install git+https://github.com/Viltrumlik/tzmeet
```

Or take the file:

```bash
curl -O https://raw.githubusercontent.com/Viltrumlik/tzmeet/main/tzmeet.py
python3 tzmeet.py Europe/Berlin +05:00
```

**Windows:** Python ships no timezone database of its own, so named zones need `pip install tzdata`. Offsets like `+05:00` work everywhere without it.

## Development

```bash
python3 -m unittest discover -s tests -v
```

The core tests use fixed offsets, so they give the same answer on every machine. Named-zone tests skip themselves when no timezone database is present. CI runs on Ubuntu, macOS and Windows with Python 3.9 through 3.13.

## License

[MIT](LICENSE) © Alisher Muhammadaliyev ([@Viltrumlik](https://github.com/Viltrumlik))
