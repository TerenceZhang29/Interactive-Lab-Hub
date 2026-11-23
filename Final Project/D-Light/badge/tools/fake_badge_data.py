#!/usr/bin/env python3
"""Fake D-Light badge data: one docking's worth of Pi-side JSON lines.

Writes the same JSON Lines stream the Pi-side receiver will produce after a
real badge docks (see ../data-format.md): one "dock" header line, then one
"sample" line per 60 s sample, plus a "gap" line if --with-gap is given.

Usage:
    python3 fake_badge_data.py --scenario sunny --date 2026-11-16 --seed 1
    python3 fake_badge_data.py --scenario overcast --seed 7 -o overcast.jsonl
    python3 fake_badge_data.py --scenario indoors --start 09:00 --end 18:00
    python3 fake_badge_data.py --scenario sunny --with-gap

Scenarios:
    sunny     clear sky; outdoor walks in the morning, at lunch, after class
    overcast  same day plan under thick cloud
    indoors   the whole day inside (window light at most, no UV)

The same --scenario, --date, --seed, --start, --end, --tz and --with-gap
always give byte-identical output. --date defaults to today, so pass it
explicitly when you need a reproducible file.

The light and UV levels are estimates, not measurements. They will be
corrected after a real day of wearing the badge (Linear SUN-5).

Python 3.9+ standard library only. Needs the system time zone database
(present on macOS and Raspberry Pi OS).
"""

import argparse
import datetime as dt
import json
import math
import random
import sys
from zoneinfo import ZoneInfo

FORMAT = "dlight-badge"
FORMAT_VERSION = 1
INTERVAL_S = 60

# Location used for the sun's position: New York City.
LATITUDE = 40.75
LONGITUDE = -73.95

# LTR390 light mode as the firmware is expected to run it: gain 1, 18-bit,
# 100 ms. One count is 0.6 lux and the reading saturates at 2**18 - 1 counts.
LUX_PER_COUNT = 0.6
LUX_MAX = round((2**18 - 1) * LUX_PER_COUNT, 1)  # 157,285.8 lux

# LTR390 UV mode. PROVISIONAL: the firmware's UV gain and resolution are not
# fixed yet (SUN-3). The datasheet and the Adafruit driver give 2300 counts
# per UV index at gain 18, 20-bit; other settings scale linearly with gain
# and with 2**bits.
UVS_GAIN = 18
UVS_RESOLUTION_BITS = 20
UVS_COUNTS_PER_UVI = 2300 * (UVS_GAIN / 18) * 2 ** (UVS_RESOLUTION_BITS - 20)
UVS_MAX = 2**UVS_RESOLUTION_BITS - 1


# --- sun --------------------------------------------------------------------

def solar_elevation_deg(when_utc):
    """Approximate solar elevation (NOAA low-accuracy formulas, ~0.5 deg)."""
    doy = when_utc.timetuple().tm_yday
    hour = when_utc.hour + when_utc.minute / 60 + when_utc.second / 3600
    g = 2 * math.pi / 365 * (doy - 1 + (hour - 12) / 24)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    true_solar_min = hour * 60 + eqtime + 4 * LONGITUDE
    hour_angle = math.radians(true_solar_min / 4 - 180)
    lat = math.radians(LATITUDE)
    cos_zenith = (math.sin(lat) * math.sin(decl)
                  + math.cos(lat) * math.cos(decl) * math.cos(hour_angle))
    return 90 - math.degrees(math.acos(max(-1.0, min(1.0, cos_zenith))))


def clear_sky_lux(elev):
    """Outdoor illuminance under a clear sky, horizontal, rough model."""
    if elev <= -6:
        return 3.0  # night: street lighting
    if elev <= 0:
        return 3.0 + 400 * (elev + 6) / 6  # civil twilight
    s = math.sin(math.radians(elev))
    return 400 + 120000 * s ** 1.15


def clear_sky_uvi(elev):
    """UV index under a clear sky (UVI ~ 12.5 * cos(zenith)**2.42)."""
    if elev <= 0:
        return 0.0
    return 12.5 * math.sin(math.radians(elev)) ** 2.42


# --- day plan -----------------------------------------------------------------

# (start, end, place). Places: home, home_off (coat off, badge on the coat
# hook), commute, indoor, window, lunch_walk. Times are jittered per seed.
PLAN_OUT = [
    ("00:00", "08:10", "home"),
    ("08:10", "08:40", "commute"),
    ("08:40", "12:05", "indoor"),
    ("12:05", "12:45", "lunch_walk"),
    ("12:45", "16:50", "indoor"),
    ("16:50", "17:25", "commute"),
    ("17:25", "18:00", "home"),
    ("18:00", "24:00", "home_off"),
]
PLAN_IN = [
    ("00:00", "08:10", "home"),
    ("08:10", "08:40", "indoor"),  # e.g. tunnel or car park, no daylight
    ("08:40", "12:05", "indoor"),
    ("12:05", "12:45", "window"),
    ("12:45", "16:50", "indoor"),
    ("16:50", "17:25", "indoor"),
    ("17:25", "18:00", "home"),
    ("18:00", "24:00", "home_off"),
]


def _minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def build_plan(scenario, rng):
    """Return [(start_min, end_min, place)] covering the whole day."""
    base = PLAN_IN if scenario == "indoors" else PLAN_OUT
    edges = [_minutes(s) for s, _, _ in base] + [24 * 60]
    # Jitter inner edges by up to +-10 min, keeping order.
    for k in range(1, len(edges) - 1):
        edges[k] += rng.randint(-10, 10)
    return [(edges[k], edges[k + 1], base[k][2]) for k in range(len(base))]


def place_at(plan, minute_of_day):
    for start, end, place in plan:
        if start <= minute_of_day < end:
            return place
    return plan[-1][2]


# --- light model --------------------------------------------------------------

class Model:
    def __init__(self, scenario, rng):
        self.scenario = scenario
        self.rng = rng
        self.cloud = 0.15  # transmission of visible light under overcast
        self.facing = 1.0  # badge orientation factor while outdoors
        self.last_place = None
        self.indoor_level = 300.0

    def step(self, place, elev):
        rng = self.rng
        if place != self.last_place:
            # New activity: new orientation and new indoor lighting level.
            self.facing = rng.uniform(0.35, 1.15)
            self.indoor_level = {
                "home": rng.uniform(120, 260),
                "home_off": rng.uniform(4, 25),
                "indoor": rng.uniform(180, 450),
                "window": rng.uniform(600, 1800),
            }.get(place, 300.0)
            self.last_place = place
        # Overcast transmission drifts slowly between 0.06 and 0.25.
        self.cloud = min(0.25, max(0.06, self.cloud + rng.gauss(0, 0.01)))

        if place in ("commute", "lunch_walk"):
            sky = clear_sky_lux(elev)
            uvi = clear_sky_uvi(elev)
            if self.scenario == "overcast":
                sky *= self.cloud
                uvi *= min(1.0, self.cloud * 3.0)  # clouds pass UV more readily
            # Walking turns the badge to and from the sun; buildings shade it.
            turn = self.facing * rng.uniform(0.75, 1.1)
            if rng.random() < 0.12:
                turn *= rng.uniform(0.1, 0.4)  # building shadow
            lux = sky * turn
            uvi = uvi * min(1.0, 0.55 * turn + 0.15)  # chest is vertical
        else:
            # Indoors: glass blocks the UV the LTR390 measures.
            lux = self.indoor_level * rng.uniform(0.85, 1.15)
            uvi = 0.0
            if place == "home_off" and rng.random() < 0.15:
                lux = 0.0  # badge facing the wall or covered by another coat
        return lux, uvi


def quantize_lux(lux):
    counts = min(2**18 - 1, max(0, round(lux / LUX_PER_COUNT)))
    return round(counts * LUX_PER_COUNT, 1), counts == 2**18 - 1


def uvs_from_uvi(uvi, rng):
    if uvi <= 0:
        return 0
    counts = round(uvi * UVS_COUNTS_PER_UVI * rng.uniform(0.95, 1.05))
    return min(UVS_MAX, max(0, counts))


# --- output -------------------------------------------------------------------

def generate(scenario, date, seed, start, end, tz_name, with_gap):
    rng = random.Random(f"{scenario}|{date.isoformat()}|{seed}")
    tz = ZoneInfo(tz_name)

    undock = dt.datetime.combine(date, start, tzinfo=tz)
    dock = dt.datetime.combine(date, end, tzinfo=tz)
    if dock <= undock:
        raise SystemExit("--end must be later than --start")
    span_s = (dock.astimezone(dt.timezone.utc) - undock.astimezone(dt.timezone.utc)).total_seconds()
    n = int(span_s // INTERVAL_S)
    if n < 1:
        raise SystemExit("day is shorter than one interval")

    plan = build_plan(scenario, rng)
    model = Model(scenario, rng)
    first_seq = rng.randrange(1000, 50000)
    last_seq = first_seq + n - 1

    gap = None
    if with_gap and n > 120:
        g_start = first_seq + rng.randrange(n // 3, 2 * n // 3)
        gap = (g_start, g_start + rng.randint(5, 30) - 1)

    dock_utc = dock.astimezone(dt.timezone.utc)
    samples = []
    for i in range(n):
        seq = first_seq + i
        t_utc = dock_utc - dt.timedelta(seconds=(last_seq + 1 - seq) * INTERVAL_S)
        t_local = t_utc.astimezone(tz)
        lux_raw, uvi_true = model.step(place_at(plan, t_local.hour * 60 + t_local.minute),
                                       solar_elevation_deg(t_utc))
        if gap and gap[0] <= seq <= gap[1]:
            continue  # model still advances so later samples do not shift
        lux, saturated = quantize_lux(lux_raw)
        uvs = uvs_from_uvi(uvi_true, rng)
        samples.append({
            "type": "sample",
            "seq": seq,
            "t": t_local.isoformat(),
            "lux": lux,
            "uvs": uvs,
            "uvi": round(uvs / UVS_COUNTS_PER_UVI, 2),
            "flags": ["lux_saturated"] if saturated else [],
        })

    hours = span_s / 3600
    header = {
        "type": "dock",
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "source": "fake",
        "badge_id": "fake-0001",
        "dock_time": dock.isoformat(),
        "interval_s": INTERVAL_S,
        "interval_source": "nominal",
        "sample_count": len(samples),
        "first_seq": first_seq,
        "last_seq": last_seq,
        "battery_percent": round(100 - 0.35 * hours - rng.uniform(0, 1), 1),
        "resets": [],
        "uvs_counts_per_uvi": UVS_COUNTS_PER_UVI,
        "fake": {"scenario": scenario, "date": date.isoformat(), "seed": seed},
    }

    lines = [header]
    for s in samples:
        if gap and s["seq"] == gap[1] + 1:
            lines.append({
                "type": "gap",
                "from_seq": gap[0],
                "to_seq": gap[1],
                "missing": gap[1] - gap[0] + 1,
                "start": (dock_utc - dt.timedelta(seconds=(last_seq + 1 - gap[0]) * INTERVAL_S)).astimezone(tz).isoformat(),
                "end": (dock_utc - dt.timedelta(seconds=(last_seq + 1 - gap[1]) * INTERVAL_S)).astimezone(tz).isoformat(),
            })
        lines.append(s)
    return lines


def _hhmm(text):
    try:
        return dt.datetime.strptime(text, "%H:%M").time()
    except ValueError:
        raise argparse.ArgumentTypeError("use HH:MM, e.g. 07:30")


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate one fake day of D-Light badge data as JSON Lines.")
    p.add_argument("--scenario", choices=["sunny", "overcast", "indoors"], default="sunny")
    p.add_argument("--date", type=dt.date.fromisoformat, default=dt.date.today(),
                   help="day to simulate, YYYY-MM-DD (default: today)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--start", type=_hhmm, default=_hhmm("07:30"),
                   help="undock time, HH:MM local (default 07:30)")
    p.add_argument("--end", type=_hhmm, default=_hhmm("22:00"),
                   help="dock time, HH:MM local (default 22:00)")
    p.add_argument("--tz", default="America/New_York", help="IANA time zone (default America/New_York)")
    p.add_argument("--with-gap", action="store_true",
                   help="drop a 5-30 sample run mid-day and emit a gap line")
    p.add_argument("-o", "--output", help="write to this file instead of stdout")
    args = p.parse_args(argv)

    lines = generate(args.scenario, args.date, args.seed, args.start, args.end, args.tz, args.with_gap)
    text = "".join(json.dumps(obj, separators=(",", ":")) + "\n" for obj in lines)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
