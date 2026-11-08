"""Qat'iy siljishlar bilan -- ular har qanday mashinada bir xil ishlaydi.

Nomlangan mintaqalar Windows'da tizim bazasiga tayanadi, shuning uchun
ular alohida va o'tkazib yuborish mumkin bo'lgan testlarda.
"""

import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "tzmeet.py")

spec = importlib.util.spec_from_file_location("tzmeet", SCRIPT)
tz = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tz)


def have_tzdata():
    if tz.ZoneInfo is None:
        return False
    try:
        tz.ZoneInfo("Europe/Berlin")
        return True
    except Exception:
        return False


needs_tzdata = unittest.skipUnless(have_tzdata(), "no timezone database available")


class ParseZoneTest(unittest.TestCase):
    def test_offsets_in_every_spelling(self):
        for text in ("+5", "+05", "+05:00", "+0500", "UTC+5", "gmt+05:00"):
            zone = tz.parse_zone(text)
            self.assertEqual(zone.tzinfo.utcoffset(None), dt.timedelta(hours=5), text)

    def test_negative_and_half_hour_offsets(self):
        self.assertEqual(tz.parse_zone("-03:30").tzinfo.utcoffset(None),
                         -dt.timedelta(hours=3, minutes=30))

    def test_offsets_get_a_tidy_label(self):
        self.assertEqual(str(tz.parse_zone("+5")), "UTC+05:00")

    def test_impossible_offsets_are_refused(self):
        for bad in ("+15", "+05:99", "", "   "):
            with self.assertRaises(tz.ZoneError, msg=bad):
                tz.parse_zone(bad)

    def test_an_unknown_name_explains_itself(self):
        with self.assertRaises(tz.ZoneError) as e:
            tz.parse_zone("Mars/Olympus_Mons")
        self.assertIn("offset", str(e.exception))

    @needs_tzdata
    def test_named_zones_work(self):
        self.assertEqual(str(tz.parse_zone("Europe/Berlin")), "Europe/Berlin")


class ParseWindowTest(unittest.TestCase):
    def test_plain_hours(self):
        self.assertEqual(tz.parse_window("9-18"), (540, 1080))

    def test_hours_and_minutes(self):
        self.assertEqual(tz.parse_window("09:30-17:30"), (570, 1050))

    def test_nonsense_is_refused(self):
        for bad in ("9", "18-9", "9-25", "nine to five", "9-"):
            with self.assertRaises(tz.ZoneError, msg=bad):
                tz.parse_window(bad)


class SlotTest(unittest.TestCase):
    def find(self, offsets, hours="9-18", duration=60, days=1, day=None):
        zones = [tz.parse_zone(o) for o in offsets]
        return zones, tz.slots(zones, tz.parse_window(hours), duration,
                               day or dt.date(2026, 11, 9), days)

    def test_the_same_zone_twice_overlaps_all_day(self):
        _, found = self.find(["+5", "+5"])
        # 09:00 dan 17:00 gacha, har 30 daqiqada
        self.assertEqual(len(found), 17)
        self.assertEqual(found[0][1][0].strftime("%H:%M"), "09:00")
        self.assertEqual(found[-1][1][0].strftime("%H:%M"), "17:00")

    def test_a_four_hour_gap_still_leaves_room(self):
        zones, found = self.find(["+5", "+1"])
        self.assertTrue(found)
        for _, here_all in found:
            for here in here_all:
                minutes = here.hour * 60 + here.minute
                self.assertGreaterEqual(minutes, 9 * 60)
                self.assertLessEqual(minutes + 60, 18 * 60)

    def test_tashkent_and_new_york_never_overlap(self):
        _, found = self.find(["+5", "-5"])
        self.assertEqual(found, [])

    def test_a_longer_meeting_narrows_the_choice(self):
        _, short = self.find(["+5", "+1"], duration=30)
        _, long = self.find(["+5", "+1"], duration=180)
        self.assertGreater(len(short), len(long))

    def test_wider_working_hours_open_things_up(self):
        _, narrow = self.find(["+5", "-5"], hours="9-18")
        _, wide = self.find(["+5", "-5"], hours="7-22")
        self.assertEqual(narrow, [])
        self.assertTrue(wide)

    def test_more_days_give_more_slots(self):
        _, one = self.find(["+5", "+5"], days=1)
        _, three = self.find(["+5", "+5"], days=3)
        self.assertEqual(len(three), 3 * len(one))

    @needs_tzdata
    def test_a_daylight_saving_change_is_handled(self):
        """EU soati 2026-10-25 da orqaga suriladi.

        Taqqoslash UTC'da ketgani uchun o'sha kunning o'zida ham mahalliy
        vaqt to'g'ri hisoblanishi kerak.
        """
        berlin = tz.parse_zone("Europe/Berlin")
        before = berlin.local(dt.datetime(2026, 10, 24, 8, 0, tzinfo=dt.timezone.utc))
        after = berlin.local(dt.datetime(2026, 10, 26, 8, 0, tzinfo=dt.timezone.utc))
        self.assertEqual(before.hour, 10)   # CEST, UTC+2
        self.assertEqual(after.hour, 9)     # CET,  UTC+1


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args],
                              capture_output=True, text=True)

    def test_an_overlap_prints_local_times_and_exits_zero(self):
        out = self.run_cli("+5", "+5", "--days", "1", "--from", "2026-11-09")
        self.assertEqual(out.returncode, 0)
        self.assertIn("UTC+05:00", out.stdout)
        self.assertIn("09:00", out.stdout)

    def test_no_overlap_exits_three_and_suggests_a_fix(self):
        out = self.run_cli("+5", "-5", "--days", "1", "--from", "2026-11-09")
        self.assertEqual(out.returncode, 3)
        self.assertIn("no overlap", out.stderr)
        self.assertIn("--hours", out.stderr)

    def test_one_zone_is_not_enough(self):
        out = self.run_cli("+5")
        self.assertEqual(out.returncode, 2)
        self.assertIn("usage", out.stdout.lower())

    def test_a_bad_zone_is_a_usage_error(self):
        out = self.run_cli("+5", "Nowhere/Fictional")
        self.assertEqual(out.returncode, 2)
        self.assertIn("error", out.stderr)

    def test_json_carries_utc_and_every_local_time(self):
        out = self.run_cli("+5", "+1", "--days", "1", "--from", "2026-11-09",
                           "--json", "--limit", "1")
        data = json.loads(out.stdout)
        self.assertTrue(data["ok"])
        self.assertEqual(data["zones"], ["UTC+05:00", "UTC+01:00"])
        self.assertIn("UTC+05:00", data["slots"][0]["local"])

    def test_a_negative_duration_is_refused(self):
        self.assertEqual(self.run_cli("+5", "+5", "--duration", "0").returncode, 2)

    def test_dates_crossing_midnight_are_flagged(self):
        out = self.run_cli("+9", "-8", "--days", "1", "--from", "2026-11-09",
                           "--hours", "8-20")
        if out.returncode == 0:
            self.assertIn("different dates", out.stdout)


if __name__ == "__main__":
    unittest.main()
