# Observant Systems: Overnight Sensation

**Team:**

**Members:** Full Name (netid, github-handle), ...

**Project name:**

<details>
	<summary><strong>Instructions for Students (Click to Expand)</strong></summary>
  
	**Submission Cleanup Reminder:**
	- This README.md contains extra instructional text for guidance.
	- Before submitting, remove all instructional text and example prompts from this file.
	- You may delete these sections or use the toggle/hide feature in VS Code to collapse them for a cleaner look.
	- Your final submission should be neat, focused on your own work, and easy to read for grading.
  
	This helps ensure your README.md is clear, professional, and uniquely yours!
</details>


For lab this week, we focus on creating interactive systems that can detect and respond to events or stimuli in the environment of the Pi, like the Boat Detector we mentioned in lecture. 
Your **observant device** could, for example, count items, find objects, recognize an event or continuously monitor a room.

This lab will help you think through the design of observant systems, particularly corner cases that the algorithms need to be aware of.

**New this year: the AI runs on the Pi.** Your Pi 5 can run an object detector ([YOLO](https://docs.ultralytics.com/)) and a small language model ([Qwen](https://ollama.com/library/qwen3.5) through [Ollama](https://ollama.com)) completely offline. In Part 1 you get both running and connect them: YOLO *sees*, Qwen *reasons* about what was seen. These models are slow, but they have all night. In Part 2 you use them to design a **night-time interaction**: what you tell the device before bed, what it does while you sleep, and what it shows you when you wake up.

**Please indicate anyone that helped with this Lab here.**
Be generous in acknowledging their contributions! And also recognizing any other influences (e.g. from YouTube, Github, Twitter) that informed your design. 

## Overview

**Part 1: the tools**

A) [Set up your Pi for on-device AI](#part-a)

B) [See: recognize people in real time with YOLO](#part-b)

C) [See more: hands and pose with MediaPipe](#part-c)

D) [Reason: run Qwen on the Pi with Ollama](#part-d)

E) [Connect: from YOLO readings to Qwen reasoning](#part-e)

**Part 2: Overnight Sensation**

F) [Read Part 2 and storyboard your night-time interaction](#part-f)

G) [Design the interaction before bed](#part-g)

H) [Incorporate the observant system during sleep](#part-h)

I) [Design the interaction when awake](#part-i)

The tools from earlier versions of this lab (MobileNet, Teachable Machine, Moondream, audio analysis, classic OpenCV) live in the [legacy folder](legacy/README.md). They are optional, but any of them can be the sensor in your Part 2 system.


## Prep for Part 1

Please check the instructions in [prep.md](prep.md) and complete them before lab. The installs in Part A take a while, so prep.md also tells you how to get a head start.

## The Report

This readme.md page in your own repository should be edited to include the work you have done. You can delete everything but the headers and the sections between the \*\*\***stars**\*\*\*. Write the answers to the questions under the starred sentences. Include any material that explains what you did in this lab hub folder, and link it in the readme.

---

# Part 1

## Part A. 
### Set up your Pi for on-device AI

Create a virtual environment and install the requirements. They include `ultralytics` (YOLO), which pulls in torch, so this takes a while:

```
pi@raspberrypi:~$ cd Interactive-Lab-Hub/Lab\ 5
pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python3 -m venv .venv
pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ source .venv/bin/activate
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ pip install -r requirements.txt
```

As in Lab 3, [`uv`](https://docs.astral.sh/uv/) is a much faster drop-in for `pip`: `pip install uv && uv pip install -r requirements.txt`.

### YOLO: download the nano model and export it for the Pi

We use the nano model of [YOLO26](https://docs.ultralytics.com/models/yolo26/), exported once to NCNN, the format that runs fastest on the Pi. This downloads the weights:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python -c "from ultralytics import YOLO; YOLO('yolo26n.pt').export(format='ncnn')"
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ yolo export model=yolo26n.pt format=ncnn
```
If every ultralytics message is followed by a `--- Logging error ---` traceback ending in `UnicodeEncodeError: 'latin-1' codec can't encode character`, fix your shell's locale once::

```
echo 'export LANG=C.UTF-8' >> ~/.bashrc
echo 'export LC_ALL=C.UTF-8' >> ~/.bashrc
echo 'export PYTHONIOENCODING=utf-8' >> ~/.bashrc
source ~/.bashrc
```

The second command converts the .pt model to a .ncnn model.

Test it on an image from the internet. `project="$PWD"` keeps the output in `predict` in the current lab folder; without it, ultralytics writes to a `runs/` folder at the top of your git repo, where you will not think to look.

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ yolo predict model=yolo26n_ncnn_model source=https://ultralytics.com/images/bus.jpg project="$PWD"
```

The result is in `predict/bus.jpg`: boxes around the people and the bus.

Now a photo of your own. Plug in the webcam and take one with `snap.py` (`--delay 3` gives you three seconds to get into the frame), or choose any picture you downloaded from the internet and put under this folder. Put your selected picture after the `source=` Then run the same command on it:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python snap.py --delay 3
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ yolo predict model=yolo26n_ncnn_model source=snap.jpg project=runs
```

Every run gets its own numbered folder, so this one is in `runs/predict2/snap.jpg`; the command prints where it saved. Keep `snap.jpg`, you will show it to Qwen in Part D.

> YOLO26n on my own `snap.jpg`: it labels the shaker bottle a `cup` (0.64), the Pi's screen a `cell phone` (0.45) and the desk a `dining table` (0.43). Close enough, but none of these are the real object, and the black power adapter isn't detected at all.
>
> ![YOLO detections on snap.jpg](Readme_files/snap_yolo.jpg)

### Ollama: install it and pull Qwen

[Ollama](https://ollama.com) runs language models locally. Nothing leaves the Pi: no API key, no internet after the download.

```
pi@raspberrypi:~ $ curl -fsSL https://ollama.com/install.sh | sh
pi@raspberrypi:~ $ ollama pull qwen3.5:0.8b
pi@raspberrypi:~ $ ollama pull qwen3:0.6b
pi@raspberrypi:~ $ ollama list
```

| model | download | what it does |
|---|---|---|
| `qwen3.5:0.8b` | ~1.3 GB | text **and images**; the one we use in this lab |
| `qwen3:0.6b` | ~0.5 GB | text only, smaller and faster (~16 tokens/s on a Pi 5) |

\*\*\***Include a screenshot of `ollama list` showing your models.**\*\*\*

> ![ollama list on jarvis showing qwen3.5:0.8b and qwen3:0.6b](Readme_files/ollama_list.png)


## Part B. 
### See: recognize people in real time with YOLO

YOLO is an *object detector*: it finds every person, cup, cat and so on (the 80 [COCO](https://cocodataset.org/) classes), draws a box around each, and gives a confidence. For an observant system that is exactly what you want: *how many*, *where*, *how sure*.

Connect your webcam, connect to your Pi through **VNC** (the script opens a window), and run the person detector. Read `yolo_person.py` first; the loop at the bottom is the whole idea.

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python yolo_person.py
```

While it runs, walk in and out of the frame, sit down, turn your back, hold up a photo of a person on your phone. Watch the confidence number on the box change with each.

Then press q to quit and run it again with a flag. Each one changes a single thing:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python yolo_person.py --conf 0.2     # lower the bar: see what the model is unsure about
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python yolo_person.py --conf 0.7     # raise the bar: see what you lose
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python yolo_person.py --all          # all 80 classes, not only people: what else is on your desk, and what does it get wrong?
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python yolo_person.py --headless     # no window, only the printed readings: how it runs over ssh, and at night
```

\*\*\***Include a short video or screenshots of your experiments with the person detection. Write down three situations where it did not see you, or saw a person who was not there, and what you think the cause was.**\*\*\*


> I recorded four 7-second runs back to back on jarvis: the default, `--conf 0.2`, `--conf 0.7` and `--all`. The webcam was at 640×480 and the model looked at 320 px, the same settings as `yolo_person.py`. It ran headless at 8–11 fps, and the Pi sat at 75 °C with no cooler. The GIF plays all four runs at 1.7× speed:
>
> ![YOLO person detection, four variants](Readme_files/partb_yolo.gif)
>
> | default (`conf 0.4`) | `--conf 0.2` |
> |---|---|
> | ![default](Readme_files/partb_default.jpg) | ![conf 0.2](Readme_files/partb_conf02.jpg) |
> | **`--conf 0.7`** | **`--all`** |
> | ![conf 0.7](Readme_files/partb_conf07.jpg) | ![all classes](Readme_files/partb_all.jpg) |
>
> **Three situations where it got me wrong**
>
> 1. **It lost me when my head left the frame** (`--all` run, 2.9 s, 3.2 s and 3.8 s). I was standing right in front of the camera, so only my shirt and jeans showed, cut off at the top and the left edge. My score fell from 0.66 to 0.45, and in three frames I disappeared completely, even though I fill a third of the image. *Cause:* most of what the model relies on is the head, shoulders and a whole silhouette. A close-up torso, blurred by motion, is mostly a dark rectangle of fabric.
>
>    ![missed: head out of frame](Readme_files/partb_miss.jpg)
> 2. **It saw a person who wasn't there at the left edge** in every run: x ≈ 20, about 200–250 px tall, scored anywhere from 0.3 to 0.88 and flickering from frame to frame. It's a dark shape cut off by the edge of the frame. *Cause:* a tall, dark, vertical shape at the edge looks like someone half in frame, which is a very common pose in the photos YOLO learned from (COCO). Because the score flickers, a naive counter would report people coming and going all night.
> 3. **At `--conf 0.2` it saw extra people next to me**, as faint boxes at x ≈ 500–545 (conf 0.20–0.21) while I moved, beside my real box at 0.73–0.80. *Cause:* these are the model's weaker second guesses about my own body. The default threshold of 0.4 hides them, and a threshold of 0.2 counts them as more people.
>
> **Other observations**
> * **Close to the camera, facing it or not, I'm a person at 0.85–0.93.** My back scored about as high as my face (0.87 in the `conf 0.7` still), and motion blur while I sat down barely mattered.
> * **`--conf 0.2`** added 29 boxes the default would have dropped, mostly the ghosts and the edge sliver. When I leaned so only my torso was in the frame, I still got a box, but only at 0.56.
> * **`--conf 0.7`** was stable: I was the only box in most frames, but the edge "person" came and went. So a high threshold doesn't remove a false positive, it only makes it flicker.
> * **`--all`** found the water bottle on the right (0.57–0.83) every time it was visible. It also called a 33 px sliver a `book` and the chair with a jacket on it a `bed` (0.44), and in three frames it found nothing at all.
>
> For the overnight system, this means: **don't count raw boxes frame by frame.** Ignore the frame edges, ask for a detection to hold for several samples before it counts, and treat "a bed in the room" with suspicion.


## Part C. 
### See more: hands and pose with MediaPipe

YOLO tells you that a person is there. Google's [MediaPipe](https://mediapipe.dev/) tells you what their hands and body are doing: face, hand and body pose detection, fast on the Pi.

![Media pipe](Readme_files/mp.gif)

The demo plays a looping audio file, so make the helper script executable first:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ chmod +x loop_audio.sh
```

Connect your webcam, connect to your Pi through **VNC**, and run the hand pose script:
(***it will not work if you use ssh from your laptop***)

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python hand_pose.py
```

Try the two main features of this script: 1) pinching for percentage control (the thumb-to-index distance sets the volume), and 2) "[Quiet Coyote](https://www.youtube.com/watch?v=qsKlNVpY7zg)" for instant percentage setting (the gesture mutes it). Notice how this example uses hardcoded positions and relates those positions with a desired set of events, in `hand_pose.py`: a hand is 21 landmark coordinates, and an *event* is a rule you write over them. That is the same job as `interpret()` in Part E.

Consider how you might use this position based approach to create an interaction, and write how you might use it on either face, hand or body pose tracking.

\*\*\***Include a screenshot or short video of the hand pose demo, and write how you might use face, hand or body pose tracking in your observant system.**\*\*\*

> I ran `hand_pose.py` on jarvis's desktop and took a screenshot every 2 s. From left to right: barely open (2%), wide open (86%), half open (39%), and pinched shut (0%; the midpoint turns green below 50 px).
>
> ![hand pose pinch volume control](Readme_files/partc_pinch.jpg)
>
> * **The pinch works well.** MediaPipe tracked all 21 landmarks at 13–34 fps, even with my hand a few inches from the lens. The thumb-to-index distance ranged from 6 to 401 px across 338 frames, and the volume followed it smoothly.
> * **On my first try, the Quiet Coyote registered only once** in about 15 s, with my hand a few inches from the lens. The rule (`length > 100 and length1 > 100 and length2 < 100 ...`) compares fingertip distances in **raw pixels**. Up close my fingers are far apart in pixels, so the "< 100" checks fail.
> * **On the second try, with my hand at about arm's length, it triggered in 187 of the 194 frames where it saw my hand.** The volume went straight to 0%:
>
>   ![quiet coyote detected](Readme_files/partc_coyote.jpg)
>
>   So the gesture is reliable, but only at the distance the thresholds were tuned for. A sturdier rule would divide each distance by the hand's size (say, wrist to the middle-finger knuckle), so it works at any distance. It could also ask the gesture to hold for about half a second, so a single lucky frame can't trigger it.
>
> **How I'd use pose tracking in my observant system** *(draft, edit to match your design)*
> * **Hand, before bed:** a Quiet Coyote held up to the camera for one second is the bedtime hand-off ("I'm going to sleep, start watching"). The device acknowledges it by dimming the screen. It's a gesture nobody makes by accident and it needs no button, which fits the thirty-second ritual in Part G. Here, holding still for a moment matters more than the exact pixel thresholds.
> * **Body, while asleep:** YOLO only says "a person"; body pose says *what they're doing*. Comparing shoulder and hip landmarks tells standing from sitting from lying down. That makes it possible to log "got up at 3:12 and stood by the desk for 4 minutes" instead of "1 person(s) at center/close", without storing any face or image.
> * **Face:** I'd avoid it overnight, for privacy and because it fails in the dark and from behind (Part B showed my back scores as well as my face for YOLO, but there are no face landmarks from behind).


## Part D. 
### Reason: run Qwen on the Pi with Ollama

Talk to the model in the terminal first. Qwen3 models "think" before they answer, which is slow on a Pi, so turn it off. Then ask about something you can check:

```
pi@raspberrypi:~ $ ollama run qwen3.5:0.8b
>>> /set nothink
>>> Tell me a bit about the history of Roosevelt Island. Three sentences.
>>> /bye
```

Roosevelt Island is a good first question because you know the ground truth: it was Blackwell's Island, then Welfare Island, got its current name in 1973, and Cornell Tech opened on it in 2017. Count how many of the model's facts are true.

From Python, qwen requests can be triggered by the `ask_qwen.py` script. It turns thinking off, tells the model to answer in at most three sentences, and cuts it off after 120 tokens (`--max-tokens` changes that), because a small model left alone writes an essay. Read the script, then run:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python ask_qwen.py "Tell me a bit about the history of Roosevelt Island."
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python ask_qwen.py --model qwen3:0.6b "Tell me a bit about the history of Roosevelt Island."
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python ask_qwen.py --image snap.jpg "What is in this photo?"
```

Things in the [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md) worth knowing:

* `think: false` skips the reasoning trace. Always, on a Pi. `ask_qwen.py` sends it on every request; `--think` turns the trace back on for one question, so you can see what you are skipping and how long it takes.
* `format` makes the model answer as JSON with the fields you name (`--json`). Handy when a display or a servo has to read the answer.
* `images` sends a photo along with the prompt (`--image snap.jpg`, the photo from Part A). `qwen3.5:0.8b` can look at pictures.

A 0.8B model is slow and sometimes wrong. It will invent events that are not in the data and agree with a wrong premise. Give it the data, keep its job narrow, and decide what the device does when the model is unsure.

\*\*\***Ask Qwen three questions to answer. Paste the questions, the answers and how long each took. Try one of them with `qwen3:0.6b` and compare.**\*\*\*

<details>
<summary>Q&A (run on jarvis, Pi 5 8 GB, thinking off, default 120-token cap)</summary>

**1. "Tell me a bit about the history of Roosevelt Island."**

`qwen3.5:0.8b` (26.0 s):
> Roosevelt Island is a historic neighborhood on Manhattan's East Side, originally built as an exclusive residential enclave for wealthy New Yorkers during the late 19th century. It was designed to separate the upper-class from the rest of the city while serving as a prestigious commercial hub and social center. The island has been home to many significant figures in American history, including President Franklin D. Roosevelt, who lived in his luxurious mansion on the property. Today, it remains a popular tourist destination known for its beautiful waterfront views and vibrant nightlife.

`qwen3:0.6b` (10.6 s):
> Roosevelt Island was established in 1910 as a temporary refuge for the displaced and homeless, offering a safe haven for the isolated. It became a significant community center and a hub for the local population, fostering growth and connection. Today, it remains a vital part of the community and a symbol of resilience and hope.

Fact check: the 0.8b model gets essentially nothing right. The island was never a wealthy enclave, FDR never lived there, and it isn't known for nightlife. It also ignored the three-sentence limit. The 0.6b model is vaguer, and because of that a little closer: the island really did hold hospitals, an asylum and a workhouse, but "1910" is made up. Neither one mentions Blackwell's Island, Welfare Island, the 1973 renaming or Cornell Tech. Both answer confidently and fluently, which makes them dangerous as a source of facts.

**2. `--image snap.jpg` "What is in this photo?"** (`qwen3.5:0.8b`, 32.6 s)
> A clear plastic water bottle with a gray lid sits on a white table next to a black power strip and several cables.

All correct, and better than YOLO on the same photo (Part A): it calls the bottle a bottle and sees the power strip, which YOLO missed. It was also the slowest call, even though the answer is only one sentence, so most of that time goes into processing the image.

**3. `--json` "Someone was at the door at 3 am. Is that unusual?"**

`qwen3.5:0.8b` (4.9 s):
```json
{ "headline": "Unusual: Someone at 3 AM", "unusual": true }
```

`qwen3:0.6b` (2.3 s, plain text):
> No, that's unusual if someone is at the door at 3 am. It's unusual for someone to be at the door at such a late hour. The timing doesn't align with typical routines.

The JSON schema keeps the 0.8b model short, fast and easy for a program to read. The 0.6b model contradicts itself in the first sentence ("No, that's unusual"), so free text from it can't be trusted for a yes/no decision. **Takeaway for Part 2:** give the model the data, ask for a structured answer, and never use it as a source of facts.

**Bonus: question 1 again with `--think`** (`qwen3.5:0.8b`, **582.6 s**, cut off with no answer at all)

The model spent almost ten minutes reasoning in a loop. The same few lines repeat 37 times ("Wait, I think I need to check if there's a specific historical fact about the founding of Roosevelt Island…", "It was founded in 1857 by John Quincy Adams? No."), and it never got as far as an answer. It also heated the Pi from about 75 °C to 85 °C, enough to trigger the Pi's soft temperature limit (`vcgencmd get_throttled` = `0xe0008`). The run took 22× longer than with thinking off and produced nothing, which is why `think: false` is the rule on a Pi.
</details>


## Part E. 
### Connect: from YOLO readings to Qwen reasoning

An observant system is a pipeline: a **detector** turns pixels into boxes, an **interpreter** turns boxes into readings in words ("one person, left, close"), the readings pile up in a **log**, and a **reasoner** answers a question about the log. The language model never sees pixels, only the words you chose in the interpreter. That makes the interpreter the most important design decision in the system.

`yolo_to_qwen.py` is the pipeline in one file, one function per stage. Read it before you run it:

* `interpret(r)` is the interpreter. It takes one YOLO result and returns one reading. A person is *left*, *center* or *right* by which third of the frame the middle of their box is in, and *close* if the box is taller than 60% of the frame, *far* otherwise. The reading is a string like `1 person(s) at center/close`, or `nobody`. Fifteen lines, and they decide everything the model can know.
* `watch(seconds)` is the detector and the log. Twice a second it reads a frame, runs YOLO on it and calls `interpret()`. A time-stamped reading goes into the log **only when it differs from the previous one**, so a minute of sitting still is one line, not 120.
* `ask(log, question)` is the reasoner. It pastes the log and your question into one prompt, tells Qwen to answer in at most three sentences using only what is in the log, and sends it to Ollama with thinking off.

Run it through VNC and a window opens with YOLO's boxes, the current reading and the seconds left. Press q to stop watching early. Over plain ssh add `--headless` and you get the same thing minus the window.

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python yolo_to_qwen.py
```

It watches for a minute, saves the log to `watch_log.txt` and asks Qwen the default question. The terminal looks something like this:

```
14:02:11 nobody
14:02:19 1 person(s) at right/far
14:02:24 1 person(s) at center/close
14:02:51 nobody

4 lines saved to watch_log.txt
asking Qwen...

Qwen (18.4 s):
One person came in from the right, moved close to the camera, and left after about half a minute. ...
```

> **My run.** Instead of walking through the room, I played a movie clip on my phone under the webcam, with the phone filling most of the frame. I watched for 30 s with the window open on jarvis. The log is saved in [`watch_log.txt`](watch_log.txt).
>
> ![YOLO to Qwen window: a person on the phone screen at 0.52, reading "1 person(s) at center/far"](Readme_files/parte_window.jpg)
>
> ```
> 21:07:22 nobody
> 21:07:33 1 person(s) at center/far
> 21:07:34 nobody
> 21:07:35 1 person(s) at center/far
> 21:07:38 1 person(s) at left/far
> 21:07:38 1 person(s) at center/far
> 21:07:40 nobody
> 21:07:47 3 person(s) at center/far, right/far, center/far
> 21:07:47 1 person(s) at center/far
> 21:07:49 2 person(s) at center/far, right/far
> 21:07:49 1 person(s) at center/far
> 21:07:50 nobody
> 21:07:51 1 person(s) at center/far
>
> 13 lines saved to watch_log.txt
> asking Qwen...
>
> Qwen (15.7 s):
> There were 10 people total across the room. They were all located in the center or far area of the room. No one was doing
> anything specific; they were just standing around. The only change occurred at 21:07:49, where two people moved to the right
> side of the room.
> ```
>
> **The detector saw the people on screen, but only weakly.** The man in the still scores just 0.52, barely above the 0.4 cut-off, and shots with glare or dim lighting read as `nobody`. Everyone is `far`: "close" means a box taller than 60% of the frame, and a person on a phone screen never gets that big. This is the interpreter's vocabulary at work. The words it has decide what the model can say.
>
> **The reasoner got the log wrong in four ways.** The most people at once was 3 (21:07:47), yet Qwen says **"10 people total"**: it seems to add up readings across lines, as if each line were new people. "Just standing around" is made up, because the log has no information about posture. It says the only change was at 21:07:49, when the log changes 12 times. It also ignored the three-sentence limit. Logging only changes keeps the log short (13 lines instead of about 60), but a 0.8B model still treats each line as new people.
>
> **Same log, `--json`** (7.4 s): `{"people": 3, "activity": "standing", "unusual": true}`. The schema forced one number, and this time it's the right one: the peak count of 3. "Standing" is still made up.
>
> **A hand-edited contradiction.** As the script suggests, I inserted a fake line, `21:07:41 2 person(s) at left/close, right/close`, between two `nobody` lines one second apart. That's physically implausible: two people suddenly appearing close to the camera and vanishing within a second.
> * With the default question (12.2 s), Qwen now says *"5 people in total"* whose *"positions remained stable with no changes detected"*. The answer changed, it's still wrong, and it never mentions the planted line.
> * Asked directly *"Is there anything in this log that looks like a detector error rather than a real event?"* (18.3 s), it says yes, but for the wrong reasons. It flags `1 person(s) at center/far` "appearing twice" and the repeated `nobody` lines, which are normal. It never mentions the planted two-person line.
>
> **For Part 2:** the reasoner can't count across lines, can't tell noise from events, and will invent details such as posture. So the cleanup has to happen *before* the log. Require a reading to hold for a few samples before it's logged, and let the interpreter, not Qwen, compute the numbers that matter (peak count, time present). Then give Qwen only that tidied summary and a narrow question, ideally with a JSON answer that a display can show directly.

---

# Lab 5 Part 2: Overnight Sensation

For Part 2, you will use the observant system from Part 1 to design a night-time interaction. On-device AI is slow, so let it work while you sleep. The person meets the device twice: **before bed**, when they hand the night over, and **when awake**, when the device gives something back. In between, the pipeline from Part E runs on its own.

Two flavors, pick one or mix them:

* **Sense all night.** The Pi watches, listens or measures from bedtime until morning and keeps a log.
* **Process all night.** You already have the data (a day of phone photos, a long recording) and the Pi needs hours to get through it.

Two house rules. Sample rather than stream: one look every 5 to 30 seconds is plenty, and it keeps the Pi cool. And keep everything on the Pi: tell the people you live with, point the camera at things rather than at beds, and delete the snapshots after the demo.

## Part F. 
### Read Part 2 and storyboard your night-time interaction

Storyboard a night-time interaction built on your observant system, in three panels:

1. **Before bed.** How does the person hand the night over, and how does the device acknowledge it?
2. **While asleep.** What does the device watch or work through?
3. **When awake.** What is the one thing the person learns, and in what medium?

Stuck? A kitchen that tells you who raided the fridge. A desk that reports whether you actually went to bed. A window that names the quietest hour. A plant that describes its night. Find something better.

Use storyboards and/or [Verplank diagrams](https://ccrma.stanford.edu/courses/250a-fall-2004/IDSketchbok.pdf).

\*\*\***Insert ideas, sketches, Verplank diagrams and storyboards for your night-time interaction here.**\*\*\*

## Prep for Part 2

1. Look at and give feedback on the Part F storyboards.
   **Put the feedback for your ideas here.**
2. [Update your Lab Hub](prep.md#get-the-latest-content) to get the latest content for Part 2.
3. Decide where the device will spend the night and who else lives there. Get their OK before the first run.
4. Revise your storyboard with the feedback and with what you learned in Part E about where the pipeline breaks.

\*\*\***Post your revised storyboard here.**\*\*\*

## Part G. 
### Design the interaction before

The hand-off: the person tells the device what to watch tonight, and the device acknowledges it. Keep it to a thirty-second ritual. A button or a touch (Lab 4), a spoken sentence (Lab 3), a wave or a Quiet Coyote at the camera (Part C). The acknowledgement can be a line on the display, a tone, or an LED that dims rather than lights up. At its simplest, the hand-off just sets the question that the morning will answer.

\*\*\***Describe the interaction before.**\*\*\*

## Part H. 
### Incorporate the observant system

The Part E pipeline becomes the night shift. `overnight.py` runs your `interpret()` from `yolo_to_qwen.py` every few seconds, people only unless you pass `--all`, and writes the readings to `night_log.jsonl`; the reasoning waits for the morning. Start it inside `tmux` so it keeps running after you close your laptop, and stop it with Ctrl-C in the morning:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ tmux new -s night
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python overnight.py
```

Fake a night first: run it for thirty seconds while you walk around, stop it, and run `morning.py` from Part I. When that looks right, run a real night. If your storyboard needs a sensor rather than the camera, swap in the Lab 4 example code and log its reading the same way.

\*\*\***Screenshots or videos of the running system.**\*\*\*

## Part I. 
### Design the interaction after

The reveal. The night produced a log; the morning turns it into something a half-awake person can take in. `morning.py` is the smallest version: it asks Qwen for a three-sentence report.

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python morning.py
```

Make it yours: show the report on the Mini PiTFT, read it aloud with Piper from Lab 3, plot the night as a timeline, or ask for JSON (`--json`, Part D) and move a servo. Whatever you pick, make sure it is honest about a night in which nothing happened.

## Final documentation

Document all the prototypes and iterations you have designed and worked on. The deliverables for this lab are writings, sketches, photos, and videos that show what your system:

* "Looks like": how the device sits in the room at night, and what it looks like at bedtime and in the morning.
* "Works like": the pipeline from detector to interpreter to log to reasoner, with a real night's data.
* "Acts like": how a person hands the night over and what they get back.

\*\*\***Include a short video of the whole system**\*\*\*

As always, make sure you document contributions and ideas from others (and AI) explicitly in your writeup.

You are permitted (but not required) to work in groups and share a turn in; you are expected to make equal contribution on any group work you do, and N people's group project should look like N times the work of a single person's lab. Make sure the page for the group turn in is linked to your personal Interactive Lab Hub page.

## Deliverables & Submission for Lab 5

For submission, the readme.md page for this lab should be edited to include the work you have done:
* Upload any materials that explain what you did, including your code and night log, into your Lab 5 repository, and link them in your Lab 5 readme.md.
* Labs are due on Sundays, make sure to submit your Lab 5 readme.md to Canvas.

<details>
  <summary><strong>Submission Cleanup Reminder (Click to Expand)</strong></summary>

  **Before submitting your README.md:**
  - This readme.md file has a lot of extra text for guidance.
  - Remove all instructional text and example prompts from this file.
  - You may either delete these sections or use the toggle/hide feature in VS Code to collapse them for a cleaner look.
  - Your final submission should be neat, focused on your own work, and easy to read for grading.
</details>
