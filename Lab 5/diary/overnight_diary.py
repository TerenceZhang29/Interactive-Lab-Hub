"""
Part H for Yesterday Together: turn one day of selected photos and clips into a
draft audio-diary for a caregiver to review in the morning.

    python overnight_diary.py sample_day                        # notes from sample_day/caregiver_notes.json
    python overnight_diary.py sample_day --notes notes.json --out runs/2026-10-27
    python overnight_diary.py sample_day --model google/gemini-3.5-flash-lite:batch

Stages, each saved to the run folder so an interrupted night resumes where it stopped:
  1. load     order photos (and frames sampled from clips) by the time in the filename
  2. filter   drop frames that are too dark or blurry, and near-duplicates
  3. describe ask a vision model what is visible, and nothing more (cached per frame)
  4. group    frames close in time become one candidate event; attach caregiver notes
  5. draft    write one short chapter per event, each citing its source frames
status.json says Processing, Ready for Review or Needs Attention, and review.html is the
caregiver's morning page (morning_page.py). Nothing here plays
audio: the draft waits for the caregiver.
"""
import argparse
import base64
import datetime
import json
import os
import pathlib
import re
import time

import cv2
import numpy as np
import requests
from dotenv import load_dotenv

import morning_page                                # Part I: writes review.html for the caregiver

PHOTO = {".jpg", ".jpeg", ".png"}
VIDEO = {".mp4", ".mov", ".m4v"}
STAMP = re.compile(r"(\d{8})[-_](\d{6})")          # 20261027-163000

# Words that claim more than a photo can show. A hit does not block the draft, it
# marks the chapter so the caregiver looks at it first.
RISKY = re.compile(r"\b(took|taken|taking) (her|his|your|the)? ?(medication|medicine|pills?)\b"
                   r"|\b(enjoy\w*|happy|happily|sad|lonely|love[sd]?|felt|feel\w*|remember\w*|said|told|talked)\b",
                   re.I)
# Things a caregiver should see before anything is narrated: the event is flagged,
# and the draft is told to leave them out of the listener's story.
SENSITIVE = re.compile(r"\b(knife|knives|blade|scissors|weapon|gun|fire|flame|smoke|blood|injur\w*|wound|"
                       r"fall(en|ing)?|lying on the floor|ambulance)\b", re.I)

parser = argparse.ArgumentParser()
parser.add_argument("records", type=pathlib.Path, help="folder of the day's selected photos and clips")
parser.add_argument("--notes", type=pathlib.Path, help="caregiver notes JSON (default: records/caregiver_notes.json)")
parser.add_argument("--out", type=pathlib.Path, help="run folder (default: runs/<date>)")
parser.add_argument("--model", help="OpenRouter model (default: OPENROUTER_MODEL in .env)")
parser.add_argument("--clip-every", type=float, default=5, help="seconds between frames sampled from a clip")
parser.add_argument("--dark", type=float, default=45, help="mean brightness (0-255) below this is too dark")
parser.add_argument("--blur", type=float, default=40, help="Laplacian variance below this is too blurry")
parser.add_argument("--dup-bits", type=int, default=6, help="hash difference at or below this is a duplicate")
parser.add_argument("--dup-minutes", type=float, default=10, help="only compare frames this close in time")
parser.add_argument("--gap", type=float, default=30, help="minutes between frames that start a new event")
args = parser.parse_args()

load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")     # Lab 5/.env, never committed
MODEL = args.model or os.environ.get("OPENROUTER_MODEL", "google/gemini-3.5-flash-lite")
KEY = os.environ.get("OPENROUTER_API_KEY", "")
notes_path = args.notes or args.records / "caregiver_notes.json"
notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path.exists() else {"notes": []}


def stamp_of(path):
    m = STAMP.search(path.stem)
    if m:
        return datetime.datetime.strptime("".join(m.groups()), "%Y%m%d%H%M%S")
    return datetime.datetime.fromtimestamp(path.stat().st_mtime)    # no time in the name: file time


day = notes.get("date") or min((stamp_of(p) for p in args.records.iterdir() if p.suffix.lower() in PHOTO | VIDEO),
                               default=datetime.datetime.now()).date().isoformat()
out = args.out or pathlib.Path(__file__).resolve().parent / "runs" / day
(out / "frames").mkdir(parents=True, exist_ok=True)


def save(name, data):
    (out / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load(name):
    p = out / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def status(state, detail):
    save("status.json", {"state": state, "detail": detail, "model": MODEL,
                         "updated": datetime.datetime.now().isoformat(timespec="seconds")})
    print(f"[{state}] {detail}", flush=True)


def openrouter(content, retries=3):
    for attempt in range(retries):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", timeout=180,
                              headers={"Authorization": f"Bearer {KEY}"},
                              json={"model": MODEL, "response_format": {"type": "json_object"},
                                    "temperature": 0.2, "messages": [{"role": "user", "content": content}]})
            r.raise_for_status()
            d = r.json()
            return json.loads(d["choices"][0]["message"]["content"]), d.get("usage", {}).get("cost", 0)
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"  model call failed ({e}), retry {attempt + 1}/{retries}", flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("model call failed after retries")


# 1. load ----------------------------------------------------------------------------
def load_frames():
    frames = []
    for p in sorted(args.records.iterdir()):
        ext = p.suffix.lower()
        if ext in PHOTO:
            frames.append({"frame": p.name, "source": p.name, "t": stamp_of(p).isoformat()})
        elif ext in VIDEO:
            cap, start = cv2.VideoCapture(str(p)), stamp_of(p)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            step, i = max(1, round(fps * args.clip_every)), 0
            while True:
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ok, img = cap.read()
                if not ok:
                    break
                sec = i / fps
                name = f"{p.stem}_{int(sec):04d}s.jpg"
                cv2.imwrite(str(out / "frames" / name), img)
                frames.append({"frame": name, "source": f"{p.name}@{sec:.0f}s",
                               "t": (start + datetime.timedelta(seconds=sec)).isoformat()})
                i += step
            cap.release()
    return sorted(frames, key=lambda f: f["t"])


def image_path(f):
    p = out / "frames" / f["frame"]
    return p if p.exists() else args.records / f["frame"]


# 2. filter --------------------------------------------------------------------------
def dhash(gray):
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    return int("".join("1" if b else "0" for b in (small[:, 1:] > small[:, :-1]).flatten()), 2)


def filter_frames(frames):
    kept = []
    for f in frames:
        img = cv2.imread(str(image_path(f)))
        gray = cv2.cvtColor(cv2.resize(img, (640, round(640 * img.shape[0] / img.shape[1]))), cv2.COLOR_BGR2GRAY)
        f["brightness"] = round(float(gray.mean()), 1)
        f["sharpness"] = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1)
        f["hash"] = dhash(gray)
        f["drop"] = None
        if f["brightness"] < args.dark:
            f["drop"] = "too dark"
        elif f["sharpness"] < args.blur:
            f["drop"] = "too blurry"
        else:
            t = datetime.datetime.fromisoformat(f["t"])
            for k in reversed(kept):
                if (t - datetime.datetime.fromisoformat(k["t"])).total_seconds() > args.dup_minutes * 60:
                    break
                if bin(f["hash"] ^ k["hash"]).count("1") <= args.dup_bits:
                    f["drop"] = f"near-duplicate of {k['frame']}"
                    break
        if f["drop"] is None:
            kept.append(f)
    for f in frames:
        f["hash"] = f"{f['hash']:016x}"
    return frames


# 3. describe ------------------------------------------------------------------------
DESCRIBE = """You help prepare a daily photo diary for an older adult. Describe only what is visible.
Do not guess names, relationships, emotions, thoughts, conversations, or whether medication was taken.
Refer to people by visible appearance only (for example "an older woman", "a younger man").
Answer JSON: {"people": int, "who": [str], "setting": str, "objects": [str],
"activity": str (only if clearly visible, else ""), "description": str (one or two plain sentences),
"usable": bool (false if the photo is too unclear to describe reliably)}"""


def describe(frames, cache):
    spent = 0.0
    for f in frames:
        if f["drop"] or f["frame"] in cache:
            continue
        # Re-encode before upload: drops EXIF (phones store GPS there) and caps the size.
        img = cv2.imread(str(image_path(f)))
        scale = min(1.0, 1280 / max(img.shape[:2]))
        if scale < 1:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        b64 = base64.b64encode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()).decode()
        d, cost = openrouter([{"type": "text", "text": DESCRIBE},
                              {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}])
        cache[f["frame"]] = d
        spent += cost or 0
        save("descriptions.json", cache)            # after every frame: a crash loses one call at most
        print(f"  {f['frame']}: {d.get('description', '')[:90]}", flush=True)
    return spent


# 4. group ---------------------------------------------------------------------------
def group(frames, cache):
    usable = [f for f in frames if not f["drop"] and cache.get(f["frame"], {}).get("usable", True)]
    events = []
    for f in usable:
        t = datetime.datetime.fromisoformat(f["t"])
        if events and (t - datetime.datetime.fromisoformat(events[-1]["end"])).total_seconds() <= args.gap * 60:
            events[-1]["frames"].append(f["frame"])
            events[-1]["end"] = f["t"]
        else:
            events.append({"id": f"e{len(events) + 1}", "start": f["t"], "end": f["t"], "frames": [f["frame"]]})
    for e in events:
        e["sources"] = [next(f["source"] for f in frames if f["frame"] == n) for n in e["frames"]]
        e["observations"] = [cache[n] for n in e["frames"]]
        lo = datetime.datetime.fromisoformat(e["start"]) - datetime.timedelta(minutes=15)
        hi = datetime.datetime.fromisoformat(e["end"]) + datetime.timedelta(minutes=15)
        e["notes"] = [n["fact"] for n in notes.get("notes", [])
                      if lo.time() <= datetime.time.fromisoformat(n["time"]) <= hi.time()]
        seen = json.dumps(e["observations"])
        e["sensitive"] = sorted({m.group(0).lower() for m in SENSITIVE.finditer(seen)})
    return events


# 5. draft ---------------------------------------------------------------------------
DRAFT = """You write a short morning audio diary for an older adult with memory loss, from the evidence below.
Each event lists what a vision model saw in its photos and any facts a caregiver confirmed.

Rules:
- One chapter per event, in time order, one to three short, warm, direct sentences, addressed to "you".
- Use only the observations and caregiver facts of that event. Leave out anything they do not state.
- Names and relationships come only from caregiver facts. Never invent emotions, conversations or thoughts.
- If an event only shows objects (for example a pill organizer), describe the object or omit the chapter;
  never say medication was taken.
- Never ask the listener whether they remember.
- If an event lists "sensitive" items (for example a knife), do not mention them; the caregiver decides.
- People in the photos may look younger than the listener; write "you" and never mention age.
- When an event shows only one person, that person is the listener: "you", never "a person" or "someone".

Answer JSON: {"chapters": [{"event": "<event id>", "title": str, "text": str}]}

Events:
"""


def draft(events):
    brief = [{"id": e["id"], "time": f"{e['start'][11:16]}-{e['end'][11:16]}",
              "observations": [{k: o.get(k) for k in ("who", "setting", "objects", "activity", "description")}
                               for o in e["observations"]],
              "caregiver_facts": e["notes"], "sensitive": e["sensitive"]} for e in events]
    d, cost = openrouter([{"type": "text", "text": DRAFT + json.dumps(brief, indent=1)}])
    written = {c.get("event") for c in d.get("chapters", [])}
    # Only object-only events may be left out; the model sometimes drops others silently.
    missing = [b for b, e in zip(brief, events)
               if e["id"] not in written and any(o.get("people") for o in e["observations"])]
    if missing:
        print(f"  draft skipped {[b['id'] for b in missing]}, asking again for those", flush=True)
        more, c2 = openrouter([{"type": "text", "text": DRAFT + json.dumps(missing, indent=1)
                                + "\n\nWrite exactly one chapter for every event above."}])
        d["chapters"] = d.get("chapters", []) + more.get("chapters", [])
        cost += c2 or 0
    order = {e["id"]: i for i, e in enumerate(events)}
    d["chapters"] = sorted(d.get("chapters", []), key=lambda c: order.get(c.get("event"), len(order)))
    by_id = {e["id"]: e for e in events}
    chapters = []
    for c in d.get("chapters", []):
        e = by_id.get(c.get("event"))
        if not e:                                    # a chapter with no event behind it is dropped
            continue
        flags = sorted({m.group(0).lower() for m in RISKY.finditer(c.get("text", ""))})
        flags += [f"seen in photos: {s}" for s in e["sensitive"]]
        chapters.append({"event": e["id"], "time": f"{e['start'][11:16]}-{e['end'][11:16]}",
                         "title": c.get("title", ""), "text": c.get("text", ""),
                         "sources": e["sources"], "caregiver_facts": e["notes"],
                         "flags": flags, "review": "pending"})
    return chapters, cost


def write_markdown(chapters, frames, events):
    lines = [f"# Draft diary for {day}", "",
             f"Model: `{MODEL}`. Every chapter needs approval before it can be played.", ""]
    alerts = [e for e in events if e["sensitive"]]
    if alerts:                                       # listed even when the draft left the event out
        lines += ["## Check first", ""] + [
            f"- {e['start'][11:16]}-{e['end'][11:16]}: {', '.join(e['sensitive'])} seen in "
            + ", ".join(f"`{s}`" for s in e["sources"]) for e in alerts] + [""]
    for c in chapters:
        lines += [f"## {c['time']} {c['title']}", "", c["text"], "",
                  "Sources: " + ", ".join(f"`{s}`" for s in c["sources"])]
        if c["caregiver_facts"]:
            lines.append("Caregiver facts: " + "; ".join(c["caregiver_facts"]))
        if c["flags"]:
            lines.append("**Check first:** " + ", ".join(c["flags"]))
        lines.append("")
    used = {n for e in events for n in e["frames"]}
    dropped = [(f["frame"], f["drop"] or "the vision model could not describe it reliably")
               for f in frames if f["frame"] not in used]
    if dropped:
        lines += ["## Left out", ""] + [f"- `{n}`: {why}" for n, why in dropped] + [""]
    (out / "draft.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    started = time.time()
    status("Processing", f"loading records from {args.records}")
    frames = load("frames.json") or load_frames()
    if not frames:
        status("Needs Attention", "no photos or clips were handed over, so there is no diary to prepare")
        return
    if "drop" not in frames[0]:
        frames = filter_frames(frames)
        save("frames.json", frames)
    kept = [f for f in frames if not f["drop"]]
    status("Processing", f"{len(frames)} frames, {len(kept)} kept after quality and duplicate checks")
    if not KEY:
        status("Needs Attention", "OPENROUTER_API_KEY is missing from .env")
        return

    cache = load("descriptions.json") or {}
    cost = describe(frames, cache)
    events = group(frames, cache)
    save("events.json", events)
    if not events:
        status("Needs Attention", "no usable photos, so no reliable diary could be prepared")
        return

    status("Processing", f"{len(events)} candidate events, writing the draft")
    chapters, c2 = draft(events)
    cost += c2 or 0
    alerts = [{"event": e["id"], "time": f"{e['start'][11:16]}-{e['end'][11:16]}", "seen": e["sensitive"],
               "sources": e["sources"]} for e in events if e["sensitive"]]
    save("draft.json", {"date": day, "model": MODEL, "check_first": alerts, "chapters": chapters})
    write_markdown(chapters, frames, events)
    flagged = sum(1 for c in chapters if c["flags"]) + sum(1 for a in alerts
                                                          if a["event"] not in {c["event"] for c in chapters})
    status("Ready for Review", f"{len(chapters)} chapters from {len(events)} events, {flagged} flagged, "
                               f"{time.time() - started:.0f} s, about ${cost:.4f} this run")
    try:                                         # the morning page is a view; never fail the night over it
        print("morning page:", morning_page.build(out, args.records), flush=True)
    except Exception as e:
        print("morning page failed:", e, flush=True)


try:
    main()
except Exception as e:
    status("Needs Attention", f"stopped: {e}; run again to resume")
    raise
