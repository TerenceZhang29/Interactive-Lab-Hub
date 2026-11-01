"""
Compare one overnight_diary.py run with the answer key of a test day.
The pipeline never reads ground_truth.json; only this script does.

    python evaluate.py runs/2026-10-27 sample_day/ground_truth.json
    python evaluate.py runs/2026-11-01 real_day/ground_truth.json

A video counts as one file: it is kept if any of its sampled frames is kept.
"""
import itertools
import json
import pathlib
import sys

run, truth = pathlib.Path(sys.argv[1]), json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
frames = json.loads((run / "frames.json").read_text(encoding="utf-8"))
events = json.loads((run / "events.json").read_text(encoding="utf-8"))
draft = json.loads((run / "draft.json").read_text(encoding="utf-8"))
chapters = draft["chapters"]

expect = {i["file"]: i for i in truth["images"]}
file_of = {f["frame"]: f["source"].split("@")[0] for f in frames}
by_file = {}
for f in frames:
    by_file.setdefault(file_of[f["frame"]], []).append(f)


def should_drop(i):
    return i["event_id"] == "quality_filter" or i["test_purpose"].startswith("Near-duplicate")


in_event = {n for e in events for n in e["frames"]}     # the vision model can also refuse a frame (usable: false)
print("1. filtering")
for name in sorted(expect):
    fs, i = by_file.get(name, []), expect[name]
    kept = [f for f in fs if f["frame"] in in_event]
    for f in fs:
        if not f["drop"] and f["frame"] not in in_event:
            f["drop"] = "vision model: unusable"
    either = "may or may not" in i["test_purpose"]
    ok = either or (not kept) == should_drop(i)
    why = "; ".join(sorted({f["drop"] for f in fs if f["drop"]})) or "-"
    print(f"  {'ok ' if ok else 'MISS'} {name}  kept {len(kept)}/{len(fs)} frames  "
          f"brightness {min((f['brightness'] for f in fs), default=0):>5}  "
          f"sharpness {min((f['sharpness'] for f in fs), default=0):>7}  dropped: {why}")

# grouping: for every pair of files with kept frames, same event in the run iff same event in the key
event_of = {}
for e in events:
    for n in e["frames"]:
        event_of.setdefault(file_of[n], e["id"])
kept_files = sorted(event_of)
pairs = list(itertools.combinations(kept_files, 2))
agree = sum((event_of[a] == event_of[b]) == (expect[a]["event_id"] == expect[b]["event_id"]) for a, b in pairs)
print(f"\n2. grouping: {len(events)} events, key has "
      f"{len({i['event_id'] for i in expect.values() if i['event_id'] != 'quality_filter'})}; "
      f"pairwise agreement {agree}/{len(pairs)}")
for e in events:
    files = sorted({file_of[n] for n in e["frames"]})
    print(f"  {e['id']} {e['start'][11:16]}-{e['end'][11:16]}  " +
          ", ".join(f"{n} ({expect[n]['event_id']})" for n in files) +
          (f"  SENSITIVE {e['sensitive']}" if e.get("sensitive") else ""))

print(f"\n3. draft: {len(chapters)} chapters, {sum(1 for c in chapters if c['flags'])} flagged, "
      f"{len(draft.get('check_first', []))} events to check first")
for a in draft.get("check_first", []):
    print(f"  CHECK FIRST [{a['time']}] {a['seen']}")
for c in chapters:
    print(f"  [{c['time']}] {c['title']}: {c['text']}" + (f"  FLAGS {c['flags']}" if c["flags"] else ""))
print("\nThe claims in each chapter still need a human read against the photos; this script only checks structure.")
