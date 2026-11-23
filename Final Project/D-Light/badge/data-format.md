---
linear: SUN-2
---

# D-Light badge data format

What the light badge records, and what the Pi-side receiver hands to the Pi software after the badge docks. Written November 16, 2026, before the logging firmware exists. Format version 1.

The Pi software should build against section 2 (the JSON stream) and the fake-data generator in section 6. Section 3 says how the receiver gets from badge records to that stream; section 4 lists what the firmware must deliver so that it can.

**The light and UV levels in the fake data are estimates.** They will be checked against a real day of wearing (Linear SUN-5) and the generator updated.

## 1. The chain

1. The badge wakes every 60 s, reads the LTR390 once for light and once for UV, appends one record to its on-chip non-volatile memory and goes back to sleep. It has no clock.
2. In the evening it snaps onto the magnetic USB-C cable from the Pi. The receiver on the Pi reads all stored records over USB serial, notes the Pi's own time as the dock time, and rebuilds a timestamp for every record.
3. The receiver writes one JSON Lines stream per docking: a `dock` header line, then one `sample` line per record, with `gap` lines where records are missing. This stream is the interface to the Pi software.

## 2. What the Pi software receives

UTF-8 [JSON Lines](https://jsonlines.org/): one JSON object per line. The first line is always the `dock` header. After it come `sample` lines in increasing `seq` order, with a `gap` line placed just before the first sample after a hole. Ignore unknown fields and unknown `type` values; new optional fields can appear without a version bump. A change that breaks readers bumps `format_version`.

### `dock` header (one per docking)

| Field | Type | Meaning |
| --- | --- | --- |
| `type` | `"dock"` | |
| `format` | `"dlight-badge"` | |
| `format_version` | int | `1` for this document. |
| `source` | `"badge"` or `"fake"` | `"fake"` when made by the generator. |
| `badge_id` | string | Stable id of the badge. Real badges: derived from the chip's unique id (exact form set by the receiver). Fake data: `"fake-0001"`. |
| `dock_time` | ISO 8601 string with UTC offset | Pi time at which the receiver read the badge. All sample times are counted back from it. |
| `interval_s` | number | Seconds between samples used to rebuild the timestamps. Nominally `60`. |
| `interval_source` | `"nominal"` or `"undock-calibrated"` | How `interval_s` was chosen (section 3.3). |
| `sample_count` | int | Number of `sample` lines that follow. |
| `first_seq`, `last_seq` | int | Sequence numbers of the oldest and newest sample slots in this docking. `last_seq − first_seq + 1 − sample_count` samples are missing. |
| `battery_percent` | number or `null` | Battery state of charge from the board's MAX17048 gauge at dock time, 0–100. `null` if it could not be read. |
| `resets` | list of int | `seq` of each sample taken right after a badge reset (anything other than a normal timed wake). Empty if none. See section 3.4. |
| `uvs_counts_per_uvi` | number | The conversion factor used to compute `uvi` from `uvs` in this file (section 5). |
| `fake` | object | Only in generated data: `scenario`, `date`, `seed`. |

### `sample` (one per 60 s record)

| Field | Type | Meaning |
| --- | --- | --- |
| `type` | `"sample"` | |
| `seq` | int | Badge sequence number. Increases by 1 per sampling slot and never repeats within a badge's life (except after a full reflash). |
| `t` | ISO 8601 string with UTC offset | Rebuilt time of the reading, in the Pi's local zone (America/New_York, so `-05:00` in winter). |
| `lux` | number | Illuminance at the badge, lux. |
| `uvs` | int | Raw UV count from the LTR390. |
| `uvi` | number | UV index derived from `uvs`, two decimals. |
| `flags` | list of string | Empty normally. `"lux_saturated"`: the light reading hit the sensor's top count, so the true value was at least `lux`. `"time_approx"`: the time is uncertain because a reset happened later in the day (section 3.4). |

Each sample is a single reading taken at `t`. For dose, treat it as representing the `interval_s` seconds that end at `t`: dose in lux·hours is the sum of `lux × interval_s / 3600`. How bright light becomes advice is up to the Pi software.

### `gap` (zero or more)

| Field | Type | Meaning |
| --- | --- | --- |
| `type` | `"gap"` | |
| `from_seq`, `to_seq` | int | First and last missing sequence numbers. |
| `missing` | int | `to_seq − from_seq + 1`. |
| `start`, `end` | ISO 8601 string | Times the first and last missing samples would have had. |

Do not fill gaps with invented values. Count a gap as "no data", not as darkness.

### Complete example

A clear November day, undocked 07:30, docked 22:00 (14.5 h, 870 samples). Lines cut from the generator's output (`--scenario sunny --date 2026-11-16 --seed 1`, and the gap from the same command with `--with-gap`); `…` marks skipped lines.

```json
{"type":"dock","format":"dlight-badge","format_version":1,"source":"fake","badge_id":"fake-0001","dock_time":"2026-11-16T22:00:00-05:00","interval_s":60,"interval_source":"nominal","sample_count":870,"first_seq":47648,"last_seq":48517,"battery_percent":94.2,"resets":[],"uvs_counts_per_uvi":2300.0,"fake":{"scenario":"sunny","date":"2026-11-16","seed":1}}
{"type":"sample","seq":47648,"t":"2026-11-16T07:30:00-05:00","lux":208.8,"uvs":0,"uvi":0.0,"flags":[]}
…
{"type":"sample","seq":47966,"t":"2026-11-16T12:48:00-05:00","lux":43664.4,"uvs":2845,"uvi":1.24,"flags":[]}
{"type":"sample","seq":47967,"t":"2026-11-16T12:49:00-05:00","lux":280.2,"uvs":0,"uvi":0.0,"flags":[]}
…
{"type":"sample","seq":48207,"t":"2026-11-16T16:49:00-05:00","lux":249.0,"uvs":0,"uvi":0.0,"flags":[]}
{"type":"gap","from_seq":48208,"to_seq":48232,"missing":25,"start":"2026-11-16T16:50:00-05:00","end":"2026-11-16T17:14:00-05:00"}
{"type":"sample","seq":48233,"t":"2026-11-16T17:15:00-05:00","lux":1.2,"uvs":0,"uvi":0.0,"flags":[]}
…
{"type":"sample","seq":48517,"t":"2026-11-16T21:59:00-05:00","lux":19.2,"uvs":0,"uvi":0.0,"flags":[]}
```

With the gap, the header would say `"sample_count":845` and `first_seq`/`last_seq` stay the same.

## 3. How the receiver rebuilds time

### 3.1 Basic rule

The badge has no clock, so every time is counted back from `dock_time`. With samples numbered `i = 0 … n−1` from oldest to newest and no gaps:

```
t_i = dock_time − (n − i) × interval_s
```

The newest sample gets `dock_time − interval_s`. The real newest reading happened somewhere in the last interval before the read, so every timestamp carries up to one interval (60 s) of uncertainty.

The receiver actually counts by sequence number, which gives the same result when nothing is missing and keeps times correct when something is:

```
t(seq) = dock_time − (last_seq + 1 − seq) × interval_s
```

Time arithmetic is done in UTC and converted to local time at the end, so days with a daylight-saving change come out right (on November 1 a 00:30–05:00 wall-clock span is 5.5 h, 330 samples).

### 3.2 Gaps in the sequence numbers

If some `seq` values between `first_seq` and `last_seq` are absent (a failed write, a corrupted record), the badge was still running and time still passed. The receiver keeps every present sample at `t(seq)` from 3.1, writes one `gap` line per run of missing numbers, and lowers `sample_count`. Nothing is interpolated.

If `first_seq` is not the previous docking's `last_seq + 1`, the receiver logs it. A higher number means the oldest records were overwritten (badge memory full) or the badge was undocked without being read; a lower number means the badge was reflashed and its counter restarted. Each docking still stands on its own because it is anchored to its own `dock_time`.

### 3.3 Clock drift and wake overhead

The 60 s interval is timed by the ESP32-S3's sleep timer, which is not crystal-accurate, and each wake takes some time. If the real period is 61 s instead of 60 s, the morning end of a 14.5 h day lands about 15 minutes too late. Two defences:

- The firmware should keep a fixed 60 s cadence (sleep for 60 s minus the time spent awake), not "work, then sleep 60 s".
- The receiver remembers when the badge was last undocked. If the new docking's `seq` range continues from that undock with no reset, it sets `interval_s = (dock_time − undock_time) / (last_seq − first_seq + 1)` and `interval_source = "undock-calibrated"`. Otherwise it uses 60 and `"nominal"`.

### 3.4 After a badge reset

A reset (battery brown-out, watchdog, button) restarts the program. The sequence counter lives in non-volatile memory and continues, but the badge cannot know how long it was down. So:

- Samples after the last reset are anchored to `dock_time` exactly as in 3.1.
- Samples before it are placed as if there had been no downtime. Their times are too late by the unknown downtime, so they get the `"time_approx"` flag. The receiver writes no `gap` line for a downtime because it cannot see one.
- `resets` in the header lists where each reset happened.

This needs the firmware to tell the receiver where resets happened (section 4). If it cannot, `resets` stays empty and the receiver cannot flag anything.

## 4. On-badge record (logical) and what the firmware must meet

The firmware (Linear SUN-3) owns the byte layout and documents it in [`firmware/RECORD_LAYOUT.md`](firmware/RECORD_LAYOUT.md). This document fixes only what a record means.

One record per 60 s sampling slot:

| Field | Meaning |
| --- | --- |
| sequence number | Slot counter, +1 per slot. May be stored per record or implied (a stored base number plus the record's position), as long as the receiver can recover it exactly. |
| lux | Light reading, LTR390 light mode. |
| raw UVS | UV count, LTR390 UV mode. |

The interval is fixed at 60 s and is not stored per record. There is no timestamp.

Constraints the firmware must meet so that sections 2 and 3 hold:

1. **Lux range and resolution.** 0 to at least 150,000 lux without saturating (gain 1, 18-bit gives 0.6 lux per count and tops out at 157,286 lux). Resolution: within 1 lux below 50 lux and within 2 % above it. A compressed (for example logarithmic) code is fine if it meets this. A saturated reading must be recognisable as saturated.
2. **UV range and resolution.** UV index 0 to at least 12 after conversion, resolution 0.05 UVI or finer. The record stores the raw count; the firmware states the gain and resolution it uses so the receiver can set `uvs_counts_per_uvi`.
3. **Fresh readings.** After switching the LTR390 between light and UV mode, wait one full conversion before reading. The bring-up test saw a stale 0 otherwise, and a stale 0 is indistinguishable from darkness here.
4. **Sequence numbers.** Never repeat or wrap within the project (at least 20 bits; 32 recommended). Keep counting across resets.
5. **Capacity and full memory.** Hold at least 24 h of records (1,440). When full, overwrite the oldest records and keep counting (decided by Jason, November 16, 2026). Stopping when full would break the dock-time anchor: the newest records would be missing and every remaining timestamp would be wrong.
6. **Resets.** Keep a small separate list, outside the records, of the first `seq` after each non-timed boot, and send it at docking so the receiver can fill `resets`. The record itself stays three fields (decided by Jason, November 16, 2026).
7. **Cadence.** Hold the 60 s period as closely as practical (section 3.3).
8. **Battery.** Report the MAX17048 state of charge when docked.

## 5. Units, ranges and what 0 means

| Field | Unit | Expected range | What 0 means |
| --- | --- | --- | --- |
| `seq` | count | any non-negative integer | Only the first slot after a fresh flash. |
| `lux` | lux | 0 – 157,286. Indoors so far 130–490 lux; outdoors overcast roughly 1,000–20,000; direct sun around 100,000 (less in winter). | The sensor saw no light it could measure: badge covered, face down, in a dark room or bag, or deep dusk. Not the same as "no data". |
| `uvs` | raw counts | 0 – 2^bits − 1 (2^20 − 1 at the provisional 20-bit setting) | No measurable UV. Normal indoors (window glass blocks most of it), at night and under heavy cover. |
| `uvi` | UV index | 0 – about 12 in principle; New York in winter about 1–2 at midday in sun, 0 indoors; summer up to about 9 | Same as `uvs` = 0. |
| `battery_percent` | % | 0 – 100 | Empty battery. `null` means unknown. |
| `interval_s` | s | about 60 | Never 0. |

**UV conversion (provisional).** `uvi = uvs / uvs_counts_per_uvi`, with

```
uvs_counts_per_uvi = 2300 × (gain / 18) × 2^(resolution_bits − 20)
```

2,300 counts per UVI at gain 18, 20-bit is the figure used by the LTR390 datasheet and the Adafruit driver. The gain and resolution the firmware will use for UV are not fixed yet, so the generator uses 2,300 as a named constant (`UVS_COUNTS_PER_UVI`) and the header carries the factor actually used. The LTR390's UV index is a rough estimate in any case: the sensor sits on a vertical chest badge, not a horizontal plate, and has not been compared with a reference meter.

## 6. Fake-data generator

[`tools/fake_badge_data.py`](tools/fake_badge_data.py) writes one docking in the format of section 2. Python 3.9 or later, standard library only.

```bash
python3 tools/fake_badge_data.py --scenario sunny --date 2026-11-16 --seed 1
python3 tools/fake_badge_data.py --scenario overcast --date 2026-11-16 --seed 1 -o overcast.jsonl
python3 tools/fake_badge_data.py --scenario indoors --date 2026-11-16 --start 09:00 --end 18:00
python3 tools/fake_badge_data.py --scenario sunny --date 2026-11-16 --with-gap
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--scenario` | `sunny` | `sunny`, `overcast` or `indoors` (whole day inside). |
| `--date` | today | Day to simulate. Pass it explicitly for a reproducible file. |
| `--seed` | `0` | Random seed. |
| `--start`, `--end` | `07:30`, `22:00` | Undock and dock time, local. Sample count = whole minutes between them (870 by default). |
| `--tz` | `America/New_York` | Time zone for timestamps. |
| `--with-gap` | off | Drop a run of 5–30 samples mid-day and emit a `gap` line. |
| `-o` | stdout | Output file. |

The same options always give byte-identical output.

**How the day is made.** A fixed plan with edges jittered by up to ±10 minutes per seed: at home until about 08:10, a 30-minute commute, class or office until about 12:05, a 40-minute lunch walk, indoors until about 16:50, a 35-minute commute, then home, with the coat (and badge) hung up from about 18:00. Outdoors, light and UV follow the sun's height over New York for that date, scaled by a random orientation factor per walk (the badge faces toward or away from the sun) and occasional building shade. Overcast passes 6–25 % of clear-sky light and about three times that share of UV. Indoors is 180–450 lux with no UV; at home 120–260 lux; on the coat hook 4–25 lux with occasional 0. In the `indoors` scenario the walks are replaced by more indoor time and a lunch by a window (600–1,800 lux). Lux is rounded to the 0.6-lux step of the real sensor.

What one seed gives on November 16, 2026 (seed 1, defaults):

| Scenario | Samples | Lux min–max | Minutes above 2,000 lux | Max UVI |
| --- | --- | --- | --- | --- |
| sunny | 870 | 0 – 59,603 | 66 | 1.72 |
| overcast | 870 | 0 – 8,297 | 35 | 0.82 |
| indoors | 870 | 0 – 1,418 | 0 | 0 |

These ranges are this generator's guesses. Nothing in them has been measured on a worn badge yet.

## 7. Open points

- Byte layout, memory size and how many hours fit: SUN-3, in `firmware/RECORD_LAYOUT.md`.
- Serial protocol between badge and receiver (how records are requested and cleared after a successful read): not specified here.
- Where the receiver puts the JSON Lines files on the Pi: decided with the receiver.
- Real value ranges: SUN-5 (a day of wearing).
