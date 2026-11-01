"""
Make synthetic test clips with an OpenRouter image-to-video model, from a start frame.
Test material only: real diaries use clips a caregiver recorded.

    python make_clips.py one start.png "She turns a page slowly." out.mp4 --duration 8
    python make_clips.py shotlist sample_day2                # every clip in sample_day2/shotlist.json

A long take is chained: the last frame of each segment is the first frame of the next,
and ffmpeg joins the segments. Clips that already exist are skipped, so a failed
run can be repeated. Costs are appended to clips_cost.jsonl next to the clips.
"""
import argparse
import base64
import json
import os
import pathlib
import subprocess
import time

import requests
from dotenv import load_dotenv

load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")     # Lab 5/.env, never committed
KEY = os.environ["OPENROUTER_API_KEY"]
API = "https://openrouter.ai/api/v1/videos"


def generate(start, prompt, out, model, duration, resolution, aspect):
    mime = "image/png" if start.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(start.read_bytes()).decode()
    r = requests.post(API, timeout=60, headers={"Authorization": f"Bearer {KEY}"}, json={
        "model": model, "prompt": prompt, "duration": duration, "resolution": resolution,
        "aspect_ratio": aspect, "generate_audio": False,
        "frame_images": [{"type": "image_url", "frame_type": "first_frame",
                          "image_url": {"url": f"data:{mime};base64,{b64}"}}]})
    if not r.ok:
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    job, started = r.json(), time.time()
    while job["status"] not in ("completed", "failed", "cancelled", "expired"):
        time.sleep(10)
        job = requests.get(job["polling_url"], timeout=60, headers={"Authorization": f"Bearer {KEY}"}).json()
    if job["status"] != "completed":
        raise RuntimeError(f"{out.name}: {job['status']} {job.get('error')}")
    video = requests.get(job["unsigned_urls"][0], timeout=300, headers={"Authorization": f"Bearer {KEY}"})
    video.raise_for_status()
    out.write_bytes(video.content)
    cost = job.get("usage", {}).get("cost")
    with open(out.parent / "clips_cost.jsonl", "a") as f:
        f.write(json.dumps({"clip": out.name, "model": model, "seconds": duration, "cost": cost,
                            "wait_s": round(time.time() - started)}) + "\n")
    print(f"{out.name}: {duration} s, ${cost}, {time.time() - started:.0f} s wait", flush=True)


def last_frame(video, png):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.2", "-i", str(video),
                    "-frames:v", "1", "-update", "1", str(png)], check=True)


def shotlist(day, a):
    listing = json.loads((day / "shotlist.json").read_text())
    shots = listing.get("clips", listing) if isinstance(listing, dict) else listing
    date = (listing.get("date", "") if isinstance(listing, dict) else "").replace("-", "")
    work = day / "segments"                      # a subfolder, so the pipeline never reads the parts
    work.mkdir(exist_ok=True)
    for s in shots:
        out = day / (s.get("planned_video_file") or s.get("file")
                     or f"{date}-{s['time'][-8:].replace(':', '')}.mp4")
        if out.exists():
            continue
        start = day / s["start_frame"]
        if not s.get("segments"):
            generate(start, s["motion_prompt"], out, a.model, int(s.get("duration_s", a.duration)),
                     a.resolution, a.aspect)
            continue
        parts = []
        for i, seg in enumerate(s["segments"], 1):
            part = work / f"{out.stem}_seg{i}.mp4"
            if not part.exists():
                generate(start, seg["motion_prompt"] if isinstance(seg, dict) else seg, part, a.model,
                         int(seg.get("duration_s", a.duration)) if isinstance(seg, dict) else a.duration,
                         a.resolution, a.aspect)
            start = work / f"{out.stem}_seg{i}_last.png"
            last_frame(part, start)
            parts.append(part)
        listing = work / f"{out.stem}_parts.txt"
        listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(listing), "-c", "copy", str(out)], check=True)
        print(f"{out.name}: joined {len(parts)} segments", flush=True)


parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=["one", "shotlist"])
parser.add_argument("paths", nargs="+")
parser.add_argument("--model", default="x-ai/grok-imagine-video-1.5-lite")
parser.add_argument("--duration", type=int, default=10)
parser.add_argument("--resolution", default="720p")
parser.add_argument("--aspect", default="16:9")
a = parser.parse_args()
if a.mode == "one":
    start, prompt, out = a.paths
    generate(pathlib.Path(start), prompt, pathlib.Path(out), a.model, a.duration, a.resolution, a.aspect)
else:
    shotlist(pathlib.Path(a.paths[0]), a)
