"""
Part I: the caregiver's morning page. Turns one overnight_diary.py run into review.html:
the day on a timeline, what needs checking first, each draft chapter beside the frames
it came from, and everything that was left out and why.

    python morning_page.py runs/2026-11-01 real_day      # writes runs/2026-11-01/review.html

overnight_diary.py calls build() at the end of every run. The page is a snapshot for
review: the Approve / Edit / Remove buttons are drawn but not wired up yet.
"""
import datetime
import html
import json
import pathlib
import sys

import cv2

DAY_START, DAY_END = 7, 21                     # hours shown on the timeline


def build(run, records):
    run, records = pathlib.Path(run), pathlib.Path(records)
    load = lambda name: json.loads((run / name).read_text(encoding="utf-8"))
    frames, events, draft, status = load("frames.json"), load("events.json"), load("draft.json"), load("status.json")
    chapters, alerts = draft["chapters"], draft.get("check_first", [])
    used = {n for e in events for n in e["frames"]}
    left_out = [(f, f["drop"] or "the vision model could not describe it reliably")
                for f in frames if f["frame"] not in used]

    thumbs = run / "thumbs"
    thumbs.mkdir(exist_ok=True)

    def thumb(name):
        src = run / "frames" / name
        src = src if src.exists() else records / name
        dst = thumbs / (pathlib.Path(name).stem + ".jpg")
        if not dst.exists():
            img = cv2.imread(str(src))
            h, w = img.shape[:2]
            img = cv2.resize(img, (320, round(320 * h / w)), interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(dst), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
        return f"thumbs/{dst.name}"

    # what was handed over at bedtime
    files = sorted({f["source"].split("@")[0] for f in frames})
    clips = [n for n in files if pathlib.Path(n).suffix.lower() in {".mp4", ".mov", ".m4v"}]
    seconds = 0.0
    for n in clips:
        cap = cv2.VideoCapture(str(records / n))
        seconds += cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 30)
        cap.release()

    e = html.escape
    day = datetime.date.fromisoformat(draft["date"])
    chapter_of = {c["event"]: c for c in chapters}
    alert_ids = {a["event"] for a in alerts}

    def pos(t):
        t = datetime.datetime.fromisoformat(t)
        hours = t.hour + t.minute / 60 + t.second / 3600
        return max(0.0, min(100.0, (hours - DAY_START) / (DAY_END - DAY_START) * 100))

    # timeline -------------------------------------------------------------------------
    at = lambda p: f"left:calc(40px + (100% - 80px) * {p / 100:.4f})"     # 40 px gutter on each side
    ticks = "".join(f'<span class="tick" style="{at((h - DAY_START) / (DAY_END - DAY_START) * 100)}">'
                    f'{h:02d}:00</span>' for h in range(DAY_START, DAY_END + 1, 2))
    marks = []
    for i, ev in enumerate(events):
        kind = "m-alert" if ev["id"] in alert_ids else ("m-chapter" if ev["id"] in chapter_of else "m-quiet")
        title = chapter_of.get(ev["id"], {}).get("title") or "no chapter"
        side = "up" if i % 2 == 0 else "down"           # alternate so neighbouring labels never collide
        marks.append(f'<div class="mark {kind} {side}" style="{at(pos(ev["start"]))}">'
                     f'<span class="dot"></span><span class="mlabel"><b>{ev["start"][11:16]}</b><br>{e(title)}</span></div>')
    for f, why in left_out:
        marks.append(f'<span class="miss" style="{at(pos(f["t"]))}" title="{e(why)}"></span>')
    timeline = f'<div class="timeline"><div class="axis"></div>{ticks}{"".join(marks)}</div>'

    # cards ----------------------------------------------------------------------------
    def strip(names, limit=4):
        shown = "".join(f'<img src="{thumb(n)}" alt="">' for n in names[:limit])
        more = f'<span class="more">+{len(names) - limit}</span>' if len(names) > limit else ""
        return f'<div class="strip">{shown}{more}</div>'

    alert_html = "".join(
        f'<div class="alert"><div class="alert-text"><b>Check first · {e(a["time"][:5])}</b>'
        f'<p>The photos show: <strong>{e(", ".join(a["seen"]))}</strong>. The diary leaves this out; '
        f'you decide whether it matters.</p></div>'
        f'{strip([n for ev in events if ev["id"] == a["event"] for n in ev["frames"]], 2)}</div>' for a in alerts)

    cards = []
    for ev in events:
        c = chapter_of.get(ev["id"])
        if not c:
            people = any(o.get("people") for o in ev["observations"])
            cards.append(f'<article class="card quiet"><div class="when">{ev["start"][11:16]}</div><div class="body">'
                         f'<h3>No chapter</h3><p class="why">{"Nobody is in these photos, so there is nothing to tell you about." if not people else "The draft skipped this event."}</p>'
                         f'</div>{strip(ev["frames"])}</article>')
            continue
        facts = "".join(f'<span class="chip fact">Caregiver: {e(x)}</span>' for x in c["caregiver_facts"])
        flags = "".join(f'<span class="chip flag">{e(x)}</span>' for x in c["flags"])
        cards.append(
            f'<article class="card{" flagged" if c["flags"] else ""}"><div class="when">{e(c["time"][:5])}</div>'
            f'<div class="body"><h3>{e(c["title"])}</h3><p class="text">“{e(c["text"])}”</p>'
            f'<div class="chips">{facts}{flags}<span class="chip src">{len(ev["frames"])} frame{"s" * (len(ev["frames"]) != 1)}'
            f' from {len(set(s.split("@")[0] for s in c["sources"]))} file{"s" * (len(set(s.split("@")[0] for s in c["sources"])) != 1)}</span></div>'
            f'<div class="actions"><button>Approve</button><button>Edit</button><button>Remove</button></div></div>'
            f'{strip(ev["frames"])}</article>')

    left_html = "".join(f'<figure><img src="{thumb(f["frame"])}" alt=""><figcaption><b>{f["t"][11:16]}</b> {e(why)}'
                        f'</figcaption></figure>' for f, why in left_out)

    kept = len(frames) - len(left_out)
    stats = [(len(files), f"records handed over<br>{len(files) - len(clips)} photos · {len(clips)} clips ({int(seconds // 60)} min {round(seconds % 60)} s)"),
             (len(frames), f"frames looked at<br>{kept} used · {len(left_out)} left out"),
             (len(events), "moments found"),
             (len(chapters), "chapters drafted"),
             (len(alerts), "to check first")]
    kpis = "".join(f'<div class="kpi{" warn" if i == 4 and n else ""}"><b>{n}</b><span>{label}</span></div>'
                   for i, (n, label) in enumerate(stats))

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Morning review · {day.isoformat()}</title>
<style>
:root {{ --paper:#f7f3ec; --card:#fffdf9; --ink:#2b2724; --muted:#7b736b; --line:#e4dccf;
  --sage:#5f7d63; --sage-soft:#e3ece2; --amber:#b9772a; --amber-soft:#f8ead6; --grey:#b9b1a6; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink); font:16px/1.5 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }}
#dashboard {{ max-width:1200px; margin:0 auto; padding:40px 44px 48px; }}
header {{ display:flex; justify-content:space-between; align-items:flex-end; border-bottom:1px solid var(--line); padding-bottom:18px; }}
.eyebrow {{ font-size:13px; letter-spacing:.14em; text-transform:uppercase; color:var(--sage); font-weight:700; }}
h1 {{ font-size:34px; margin:4px 0 0; font-weight:700; letter-spacing:-.01em; }}
.status {{ text-align:right; color:var(--muted); font-size:13px; }}
.pill {{ display:inline-block; background:var(--sage-soft); color:var(--sage); font-weight:700; border-radius:999px; padding:4px 14px; font-size:14px; margin-bottom:6px; }}
.kpis {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin:22px 0 8px; }}
.kpi {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px 16px; }}
.kpi b {{ display:block; font-size:30px; line-height:1.1; }}
.kpi span {{ color:var(--muted); font-size:13px; line-height:1.35; }}
.kpi.warn {{ background:var(--amber-soft); border-color:#ecd2ad; }} .kpi.warn b {{ color:var(--amber); }}
h2 {{ font-size:15px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); margin:30px 0 12px; }}
.timeline {{ position:relative; height:190px; background:var(--card); border:1px solid var(--line); border-radius:14px; margin-top:6px; }}
.axis {{ position:absolute; left:40px; right:40px; top:98px; height:2px; background:var(--line); }}
.tick {{ position:absolute; bottom:8px; transform:translateX(-50%); font-size:11px; color:var(--grey); }}
.tick::before {{ content:""; position:absolute; left:50%; bottom:20px; height:70px; border-left:1px dotted var(--line); }}
.mark {{ position:absolute; top:92px; width:0; }}
.miss {{ position:absolute; top:76px; }}
.dot {{ display:block; margin-left:-7px; width:14px; height:14px; border-radius:50%; background:var(--sage); border:3px solid var(--card); box-shadow:0 0 0 1px var(--sage); }}
.mark.m-alert .dot {{ background:var(--amber); box-shadow:0 0 0 1px var(--amber); }}
.mark.m-quiet .dot {{ background:var(--card); box-shadow:0 0 0 1.5px var(--grey); }}
.mlabel {{ position:absolute; left:0; transform:translateX(-50%); width:96px; font-size:11px; line-height:1.25; color:var(--muted); text-align:center; }}
.mlabel b {{ color:var(--ink); }}
.mark.up .mlabel {{ bottom:34px; }}
.mark.down .mlabel {{ top:22px; }}
.miss {{ width:9px; height:9px; margin:3px 0 0 -4px; border-radius:2px; background:var(--grey); transform:rotate(45deg); opacity:.8; }}
.legend {{ display:flex; gap:20px; font-size:12px; color:var(--muted); margin-top:8px; }}
.legend i {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; vertical-align:-1px; }}
.alert {{ display:flex; justify-content:space-between; gap:20px; align-items:center; background:var(--amber-soft); border:1px solid #ecd2ad; border-left:6px solid var(--amber); border-radius:14px; padding:16px 18px; }}
.alert b {{ color:var(--amber); }} .alert p {{ margin:4px 0 0; }}
.card {{ display:grid; grid-template-columns:70px 1fr 360px; gap:18px; align-items:start; background:var(--card); border:1px solid var(--line); border-radius:16px; padding:18px 20px; margin-bottom:12px; }}
.card.flagged {{ border-left:6px solid var(--amber); }}
.card.quiet {{ opacity:.72; background:transparent; border-style:dashed; }}
.when {{ font-size:22px; font-weight:700; color:var(--sage); font-variant-numeric:tabular-nums; }}
.card h3 {{ margin:0 0 4px; font-size:19px; }}
.text {{ margin:0 0 10px; font-size:17px; }}
.why {{ margin:0; color:var(--muted); }}
.chips {{ display:flex; flex-wrap:wrap; gap:6px; }}
.chip {{ font-size:12px; border-radius:999px; padding:3px 10px; background:#f1ece4; color:var(--muted); }}
.chip.fact {{ background:var(--sage-soft); color:var(--sage); }}
.chip.flag {{ background:var(--amber-soft); color:var(--amber); }}
.actions {{ margin-top:12px; display:flex; gap:8px; }}
.actions button {{ font:inherit; font-size:13px; border:1px solid var(--line); background:var(--paper); color:var(--muted); border-radius:8px; padding:4px 12px; }}
.actions button:first-child {{ border-color:var(--sage); color:var(--sage); }}
.strip {{ display:flex; gap:6px; justify-content:flex-end; align-items:center; }}
.strip img {{ width:84px; height:63px; object-fit:cover; border-radius:8px; border:1px solid var(--line); }}
.alert .strip img {{ width:120px; height:90px; }}
.more {{ font-size:13px; color:var(--muted); margin-left:2px; }}
.left {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }}
.left figure {{ margin:0; background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
.left img {{ width:100%; height:120px; object-fit:cover; display:block; filter:grayscale(.35); }}
.left figcaption {{ font-size:12px; color:var(--muted); padding:8px 10px; line-height:1.35; }}
footer {{ margin-top:30px; padding-top:14px; border-top:1px solid var(--line); font-size:12px; color:var(--muted); }}
@media (max-width:760px) {{ #dashboard {{ padding:20px 16px; }} .kpis {{ grid-template-columns:repeat(2,1fr); }}
  .card {{ grid-template-columns:1fr; }} .strip {{ justify-content:flex-start; }} .left {{ grid-template-columns:repeat(2,1fr); }}
  header {{ display:block; }} .status {{ text-align:left; margin-top:10px; }} }}
</style></head>
<body><main id="dashboard">
<header><div><div class="eyebrow">Yesterday Together · morning review</div>
<h1>{day.strftime("%A, %-d %B %Y")}</h1></div>
<div class="status"><span class="pill">{e(status["state"])}</span><br>{e(status["detail"])}<br>model {e(status["model"])}</div></header>
<div class="kpis">{kpis}</div>
<h2>The day at a glance</h2>
{timeline}
<div class="legend"><span><i style="background:var(--sage)"></i>chapter drafted</span><span><i style="background:var(--amber)"></i>check first</span>
<span><i style="border:1.5px solid var(--grey)"></i>no chapter</span><span><i style="background:var(--grey);border-radius:2px"></i>left out</span></div>
{"<h2>Check first</h2>" + alert_html if alerts else ""}
<h2>Draft chapters · nothing plays until you approve it</h2>
{"".join(cards)}
<h2>Left out ({len(left_out)})</h2>
<div class="left">{left_html}</div>
<footer>Generated by morning_page.py from {e(run.name)} · every chapter cites the frames beside it · review buttons are a mockup in this prototype</footer>
</main></body></html>
"""
    (run / "review.html").write_text(page, encoding="utf-8")
    return run / "review.html"


if __name__ == "__main__":
    print(build(sys.argv[1], sys.argv[2]))
