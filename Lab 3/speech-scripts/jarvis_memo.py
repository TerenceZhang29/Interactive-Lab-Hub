#!/usr/bin/env python3
"""JARVIS Memo: a hands-free voice memo device (Lab 3, Part 2).

Say "JARVIS", then "take a memo" and dictate, or "read my memos". Both can be
said in one breath: "JARVIS, take a memo: buy milk."

The MiniPiTFT screen and the green LED on a SparkFun Qwiic Button show what
JARVIS is doing at every moment (see ../images/memo_storyboard_v2.svg):

    state            LED                          screen
    idle             dim, slow breathing          clock + "Say JARVIS"
    listening        solid on                     "Listening" + level bars
    recording        brightness follows voice     REC timer + live transcript
    still listening  slow blink (1/s)             countdown to save
    processing       fast blink (4/s)             "Transcribing..." spinner
    confirm          solid on                     memo + "yes / change / delete"
    saved            2 long flashes               "Saved"
    error            3 quick flashes              "Say that again?"

Solid means it is your turn to talk; blinking means JARVIS is busy. If the
Qwiic Button is not connected, a green dot in the screen's top-right corner
plays the same LED patterns instead.

Taps on the MPR121 capacitive sensor (any pad) work as shortcuts while idle:
one tap = "JARVIS", two quick taps = "take a memo", three = "read my memos".

    python jarvis_memo.py
    python jarvis_memo.py --no-screen     # leave the display to piscreen.service
"""

import argparse
import json
import math
import queue
import re
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import sherpa_onnx
import sounddevice as sd
from faster_whisper import WhisperModel
from piper import PiperVoice

SAMPLE_RATE = 16000
BLOCK = 1600  # 0.1s of audio per read
LAB_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VAD = LAB_DIR / "models" / "silero_vad.onnx"
DEFAULT_VOICE = LAB_DIR / "voices" / "en_GB-alan-medium.onnx"
DEFAULT_MEMOS = Path(__file__).resolve().parent / "memos" / "memos.json"

# Turn-taking, in seconds (chosen from the Part C tests; see the README).
COMMAND_SILENCE = 0.6  # short commands and yes/no answers
MEMO_SILENCE = 1.5     # dictation: thinking pauses stay inside the memo
GRACE = 3.0            # "still listening" countdown after MEMO_SILENCE
WAKE_TIMEOUT = 5.0     # how long to wait for a command after "Yes, sir?"
ANSWER_TIMEOUT = 3.0   # silence after the read-back counts as "yes"
VAD_HANG = 0.3         # the VAD needs this much silence before it reports "not speaking"
TAP_GAP = 0.5          # a tap gesture ends after this long without another tap

WAKE = re.compile(r"\b(jarvis|jarvus|jarves|javis|jervis|travis|charvis)\b[\s,.!?]*", re.I)
# Whisper sometimes hears "memo" as "mammal", "memmo" or "nemo" (see the Part 2 test in the README).
MEMO_WORD = r"(?:memo|memmo|mammal|nemo|mimo|meno|note)"
MEMO_CMD = re.compile(rf"\b(?:take|make|start|record|new|begin)\b.{{0,12}}?\b{MEMO_WORD}s?\b[\s,.:;!?]*", re.I)
READ_CMD = re.compile(rf"\b(?:read|ream|reed|play|list|hear|what are|tell me)\b.{{0,15}}?\b{MEMO_WORD}s\b", re.I)
CANCEL = re.compile(r"\b(never ?mind|cancel|nothing|stop)\b", re.I)
# One or more "change X to Y" in one answer: "change Friday to Thursday and change A to B".
CHANGE = re.compile(r"\b(?:change|replace)\s+(.+?)\s+(?:to|with|into)\s+(.+?)"
                    r"(?=\s*(?:[,;]\s*)?(?:\band\s+)?\b(?:change|replace)\b|[\s.!?]*$)", re.I)
HOTWORDS = "JARVIS, take a memo. Read my memos."  # biases whisper toward the command words
YES = re.compile(r"\b(yes|yeah|yep|yup|sure|save|correct|right|okay|ok)\b", re.I)
NO = re.compile(r"\b(no|nope|delete|discard|cancel|scrap)\b", re.I)
FILLERS = re.compile(r"\b(um+|uh+|erm+|hmm+)\b[,.]?\s*", re.I)


# ---------------------------------------------------------------- status

class Status:
    """What JARVIS is doing right now. The main loop writes it; the UI thread draws it."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.state = "idle"
        self.since = time.monotonic()
        self.text = ""          # live transcript, memo under review, or a message
        self.detail = ""
        self.countdown = 0.0    # seconds left in the still-listening grace period
        self.rec_start = 0.0
        self.memo_count = 0
        self.level = 0.0        # mic level, 0..1
        self.levels = deque([0.0] * 20, maxlen=20)

    def set(self, state: str, **fields) -> None:
        with self.lock:
            if state != self.state:
                self.state, self.since = state, time.monotonic()
            for key, value in fields.items():
                setattr(self, key, value)

    def set_text(self, text: str) -> None:
        with self.lock:
            self.text = text

    def push_level(self, level: float) -> None:
        with self.lock:
            self.level = level
            self.levels.append(level)

    def snapshot(self) -> dict:
        with self.lock:
            snap = {k: v for k, v in vars(self).items() if k != "lock"}
            snap["levels"] = list(self.levels)
            return snap


def level_of(chunk: np.ndarray) -> float:
    """Maps a chunk's loudness to 0..1 (about -50 dBFS to -20 dBFS)."""
    db = 20 * math.log10(float(np.sqrt(np.mean(chunk ** 2))) + 1e-9)
    return min(1.0, max(0.0, (db + 50) / 30))


# ---------------------------------------------------------------- LED

def led_brightness(state: str, t: float, level: float) -> float:
    """LED brightness (0..255) for a state, t seconds after entering it."""
    if state == "idle":
        return 8 + 50 * (0.5 - 0.5 * math.cos(2 * math.pi * t / 3))
    if state in ("listening", "confirm"):
        return 200
    if state == "recording":
        return 25 + 230 * level
    if state == "grace":
        return 200 if t % 1.0 < 0.5 else 0
    if state == "processing":
        return 200 if t % 0.25 < 0.125 else 0
    if state == "saved":
        return 230 if t < 0.35 or 0.55 <= t < 0.9 else 0
    if state == "error":
        return 230 if t < 0.6 and t % 0.24 < 0.12 else 0
    if state == "reading":  # JARVIS talking at length: a gentle pulse, not a busy blink
        return 60 + 140 * (0.5 - 0.5 * math.cos(2 * math.pi * t / 1.2))
    return 0


class Led:
    """The green LED on a SparkFun Qwiic Button. Does nothing if the button is missing."""

    def __init__(self) -> None:
        self.button = None
        self.last = -1
        try:
            import qwiic_button
            button = qwiic_button.QwiicButton()
            if button.is_connected():
                button.begin()
                self.button = button
        except Exception as e:  # no I2C bus, library missing, ...
            print(f"Qwiic Button unavailable ({e}).")
        if self.button is None:
            print("Qwiic Button not found on I2C; showing the LED on the screen instead.")

    def set(self, brightness: float) -> None:
        if self.button is None:
            return
        value = int(max(0, min(255, brightness)))
        if value == self.last or (abs(value - self.last) < 3 and value not in (0, 255)):
            return  # skip tiny changes to keep I2C traffic down
        try:
            if value == 0:
                self.button.LED_off()
            else:
                self.button.LED_on(value)
            self.last = value
        except OSError:
            pass


# ---------------------------------------------------------------- screen

BLUE, RED, AMBER = (96, 165, 250), (248, 113, 113), (251, 191, 36)
GREEN, GREY, WHITE = (52, 211, 153), (156, 163, 175), (229, 231, 235)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


class Screen:
    """The 240x135 MiniPiTFT, drawn in landscape."""

    W, H = 240, 135

    def __init__(self) -> None:
        import board
        import digitalio
        from adafruit_rgb_display import st7789
        from PIL import Image, ImageDraw, ImageFont

        self.Image, self.ImageDraw = Image, ImageDraw
        self.disp = st7789.ST7789(
            board.SPI(), cs=digitalio.DigitalInOut(board.D5), dc=digitalio.DigitalInOut(board.D25),
            rst=None, baudrate=64000000, width=135, height=240, x_offset=53, y_offset=40)
        self.backlight = digitalio.DigitalInOut(board.D22)
        self.backlight.switch_to_output()
        self.backlight.value = True
        self.font = {size: ImageFont.truetype(FONT, size) for size in (12, 13, 14, 16)}
        self.bold = {size: ImageFont.truetype(FONT_BOLD, size) for size in (16, 18, 20, 30, 40)}

    def off(self) -> None:
        self.disp.image(self.Image.new("RGB", (self.W, self.H)), 90)
        self.backlight.value = False

    def draw(self, s: dict, t: float, led=None) -> None:
        """Draws the state. `led` (0..255) adds an on-screen LED when there is no real one."""
        img = self.Image.new("RGB", (self.W, self.H))
        d = self.ImageDraw.Draw(img)
        state = s["state"]
        if led is not None:
            k = led / 255
            d.ellipse((218, 4, 234, 20), fill=(int(34 * k), int(197 * k), int(94 * k)),
                      outline=(55, 65, 81), width=1)

        if state == "idle":
            self.center(d, datetime.now().strftime("%H:%M"), 12, self.bold[40], WHITE)
            self.center(d, "Say “JARVIS”", 72, self.font[16], GREY)
            n = s["memo_count"]
            self.center(d, f"{n} memo{'' if n == 1 else 's'}", 104, self.font[13], GREY)

        elif state == "listening":
            d.text((10, 6), "● Listening", font=self.bold[20], fill=BLUE)
            self.bars(d, s["levels"], 10, 100, 55, BLUE)
            d.text((10, 112), "“take a memo” / “read my memos”", font=self.font[12], fill=GREY)

        elif state == "recording":
            secs = int(time.monotonic() - s["rec_start"])
            d.text((10, 4), f"● REC {secs // 60}:{secs % 60:02d}", font=self.bold[18], fill=RED)
            lines = self.wrap(d, s["text"] or "…", self.font[14], 220)[-4:]
            for i, line in enumerate(lines):
                d.text((10, 30 + 18 * i), line, font=self.font[14], fill=WHITE)
            self.bars(d, s["levels"], 10, 132, 14, RED)

        elif state == "grace":
            d.text((10, 6), "Still listening…", font=self.bold[18], fill=BLUE)
            frac = max(0.0, min(1.0, s["countdown"] / GRACE))
            d.rounded_rectangle((10, 42, 230, 56), radius=7, outline=BLUE, width=2)
            if frac > 0.03:
                d.rounded_rectangle((10, 42, 10 + int(220 * frac), 56), radius=7, fill=BLUE)
            d.text((10, 68), f"saving in {math.ceil(s['countdown'])}s", font=self.font[16], fill=WHITE)
            d.text((10, 100), "keep talking to add more", font=self.font[14], fill=GREY)

        elif state == "processing":
            start = (t * 360) % 360
            d.ellipse((100, 16, 140, 56), outline=(55, 65, 81), width=5)
            d.arc((100, 16, 140, 56), start, start + 90, fill=AMBER, width=5)
            self.center(d, "Transcribing…", 76, self.bold[18], AMBER)

        elif state == "confirm":
            lines = self.wrap(d, s["text"], self.font[14], 200)
            if len(lines) > 4:
                lines = lines[:3] + [lines[3] + " …"]
            for i, line in enumerate(lines):
                d.text((10, 4 + 18 * i), line, font=self.font[14], fill=WHITE)
            d.line((10, 90, 230, 90), fill=(55, 65, 81), width=1)
            self.center(d, "yes · change · delete", 102, self.bold[16], AMBER)

        elif state == "saved":
            self.center(d, "✓ Saved", 24, self.bold[30], GREEN)
            n = s["memo_count"]
            self.center(d, f"Memo {n} of {n}", 80, self.font[16], GREY)

        elif state == "error":
            self.center(d, "Say that again?", 20, self.bold[20], RED)
            for i, line in enumerate(self.wrap(d, s["text"], self.font[13], 220)[:4]):
                self.center(d, line, 60 + 17 * i, self.font[13], GREY)

        elif state == "reading":
            d.text((10, 4), s["detail"], font=self.bold[16], fill=BLUE)
            for i, line in enumerate(self.wrap(d, s["text"], self.font[14], 220)[:5]):
                d.text((10, 30 + 18 * i), line, font=self.font[14], fill=WHITE)

        self.disp.image(img, 90)

    def center(self, d, text, y, font, fill) -> None:
        d.text(((self.W - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)

    @staticmethod
    def bars(d, levels, x, bottom, height, fill) -> None:
        for i, level in enumerate(levels):
            h = max(2, int(level * height))
            d.rectangle((x + i * 11, bottom - h, x + i * 11 + 7, bottom), fill=fill)

    @staticmethod
    def wrap(d, text, font, width) -> list:
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if d.textlength(trial, font=font) <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        return lines + [line] if line else lines


def ui_loop(status: Status, led: Led, screen, stop: threading.Event) -> None:
    """Drives the LED (~30 Hz) and redraws the screen when something changes.

    Without the Qwiic Button, the screen also redraws whenever the LED pattern
    changes noticeably, so its on-screen LED can blink (a frame takes ~15 ms).
    """
    virtual_led = led.button is None
    last_draw, last_key, last_led = 0.0, None, -1.0
    while not stop.is_set():
        s = status.snapshot()
        now = time.monotonic()
        t = now - s["since"]
        brightness = led_brightness(s["state"], t, s["level"])
        led.set(brightness)
        if screen is not None:
            key = (s["state"], s["since"], s["text"], s["memo_count"], s["detail"])
            animated = s["state"] in ("listening", "recording", "grace", "processing")
            led_changed = virtual_led and abs(brightness - last_led) >= 20
            if (key != last_key or (animated and now - last_draw > 0.15) or now - last_draw > 1.0
                    or (led_changed and now - last_draw > 0.04)):
                try:
                    screen.draw(s, t, brightness if virtual_led else None)
                except Exception as e:
                    print(f"screen error: {e}")
                last_draw, last_key, last_led = now, key, brightness
        stop.wait(0.03)


# ---------------------------------------------------------------- touch

class Touch:
    """Tap gestures on the MPR121 capacitive sensor: counts quick taps on any pad.

    A background thread polls the sensor and puts the tap count (1, 2, 3, ...)
    on `gestures` once TAP_GAP passes without another tap.
    """

    def __init__(self) -> None:
        self.gestures = queue.Queue()
        self.sensor = None
        try:
            import adafruit_mpr121
            import board
            self.sensor = adafruit_mpr121.MPR121(board.I2C())
        except Exception as e:  # not plugged in, library missing, ...
            print(f"Capacitive sensor unavailable ({e}); taps are off.")
            return
        threading.Thread(target=self._poll, daemon=True).start()

    def drain(self) -> None:
        """Forgets taps made while JARVIS was busy."""
        while not self.gestures.empty():
            self.gestures.get_nowait()

    def _poll(self) -> None:
        taps, touching, last_release = 0, False, 0.0
        while True:
            try:
                now_touching = self.sensor.touched() != 0  # bitmask of all 12 pads
            except OSError:
                time.sleep(0.1)
                continue
            now = time.monotonic()
            if now_touching and not touching:
                taps += 1
            elif touching and not now_touching:
                last_release = now
            touching = now_touching
            if taps and not touching and now - last_release >= TAP_GAP:
                self.gestures.put(taps)
                taps = 0
            time.sleep(0.02)


# ---------------------------------------------------------------- audio

class Listener:
    """Microphone + VAD. Audio arrives through a callback so nothing is lost while we think."""

    def __init__(self, vad_model: Path, status: Status) -> None:
        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(vad_model)
        config.silero_vad.min_silence_duration = VAD_HANG
        config.silero_vad.min_speech_duration = 0.25
        config.sample_rate = SAMPLE_RATE
        self.vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=120)
        self.window = config.silero_vad.window_size
        self.status = status
        self.audio = queue.Queue()
        self.pending = np.empty(0, dtype=np.float32)
        self.stream = sd.InputStream(channels=1, dtype="float32", samplerate=SAMPLE_RATE,
                                     blocksize=BLOCK, callback=self._callback)
        self.stream.start()

    def _callback(self, indata, frames, time_info, status) -> None:
        self.audio.put(indata[:, 0].copy())

    def flush(self) -> None:
        """Drops audio captured while JARVIS was talking, so it does not hear itself."""
        while not self.audio.empty():
            self.audio.get_nowait()
        self.vad.reset()
        self.pending = np.empty(0, dtype=np.float32)

    def listen(self, end_silence, start_timeout=None, grace=0.0, on_segment=None,
               on_grace=None, already_started=False, interrupt=None):
        """Records one turn and returns its audio.

        The turn ends after `end_silence` seconds of silence, plus `grace` more
        seconds if given (during which `on_grace(seconds_left)` is called, and
        `on_grace(None)` if the speaker starts again). Returns None if nobody
        starts talking within `start_timeout` seconds, or as soon as the
        `interrupt` queue has something in it (a tap gesture).
        """
        preroll = deque(maxlen=5)  # keep 0.5s before speech is detected
        chunks = []
        t, started, last_voice, in_grace = 0.0, already_started, 0.0, False
        loudest = 0.0
        while True:
            chunk = self.audio.get()
            if interrupt is not None and not interrupt.empty():
                return None
            t += len(chunk) / SAMPLE_RATE
            level = level_of(chunk)
            loudest = max(loudest, level)
            self.status.push_level(level)
            (chunks if started else preroll).append(chunk)

            self.pending = np.concatenate([self.pending, chunk])
            while len(self.pending) >= self.window:
                self.vad.accept_waveform(self.pending[:self.window])
                self.pending = self.pending[self.window:]
            while not self.vad.empty():
                if on_segment:
                    on_segment(np.array(self.vad.front.samples, dtype=np.float32))
                self.vad.pop()

            if self.vad.is_speech_detected():
                if not started:
                    started = True
                    chunks = list(preroll)
                last_voice = t
                if in_grace:
                    in_grace = False
                    on_grace(None)
            elif not started:
                if start_timeout is not None and t >= start_timeout:
                    print(f"  (no speech in {start_timeout:.0f}s; loudest mic level {loudest:.2f} of 1)")
                    return None
                continue

            silence = t - last_voice + VAD_HANG
            if silence >= end_silence + grace:
                return np.concatenate(chunks)
            if grace and silence >= end_silence:
                in_grace = True
                on_grace(end_silence + grace - silence)


def tone(freqs, dur=0.09, rate=22050, volume=0.3) -> np.ndarray:
    parts = []
    for f in freqs:
        x = np.arange(int(dur * rate)) / rate
        envelope = np.minimum(1.0, np.minimum(x, dur - x) / 0.01)
        parts.append(volume * np.sin(2 * np.pi * f * x) * envelope)
    return np.concatenate(parts).astype(np.float32)


WAKE_CHIME = tone((660, 990))
REC_CHIME = tone((880,), dur=0.12)


# ---------------------------------------------------------------- memos

class MemoStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.memos = json.loads(path.read_text()) if path.exists() else []

    def add(self, text: str) -> None:
        self.memos.append({"time": datetime.now().isoformat(timespec="seconds"), "text": text})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.memos, indent=2))


def clean_memo(text: str) -> str:
    """Strips the wake word, the "take a memo" command and fillers from a dictated memo."""
    m = WAKE.search(text)
    if m and m.start() < 5:
        text = text[m.end():]
    m = MEMO_CMD.search(text)
    if m and m.start() < 12:
        text = text[m.end():]
    text = re.sub(r"\s+", " ", FILLERS.sub("", text)).strip(" ,.;:-…")
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    return text if text[-1] in ".!?" else text + "."


def strip_words(text: str) -> str:
    return text.strip(" .,!?;:\"'’“”")


# ---------------------------------------------------------------- JARVIS

class Jarvis:
    def __init__(self, args, status: Status) -> None:
        self.status = status
        self.tiny = WhisperModel(args.wake_model, device="cpu", compute_type="int8")
        self.base = WhisperModel(args.memo_model, device="cpu", compute_type="int8")
        self.voice = PiperVoice.load(str(args.voice))
        self.store = MemoStore(args.memos)
        self.listener = Listener(args.vad_model, status)
        self.touch = Touch()

    # --- speech out

    def say(self, text: str) -> None:
        print(f"  JARVIS: {text}")
        for chunk in self.voice.synthesize(text):
            sd.play(np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16), samplerate=chunk.sample_rate)
            sd.wait()
        self.listener.flush()

    def chime(self, sound: np.ndarray) -> None:
        sd.play(sound, samplerate=22050)
        sd.wait()
        self.listener.flush()

    @staticmethod
    def transcribe(model: WhisperModel, audio: np.ndarray, hotwords=None) -> str:
        segments, _ = model.transcribe(audio, beam_size=1, hotwords=hotwords)
        return " ".join(s.text.strip() for s in segments).strip()

    # --- states

    def idle(self) -> None:
        self.status.set("idle", text="", memo_count=len(self.store.memos))

    def error(self, message: str) -> None:
        self.status.set("error", text=message)
        self.say(message)

    def run(self) -> None:
        self.idle()
        print("Ready. Say “JARVIS”.\n")
        while True:
            self.touch.drain()
            audio = self.listener.listen(COMMAND_SILENCE, interrupt=self.touch.gestures)
            if audio is None:  # tapped instead of talking
                self.on_taps(self.touch.gestures.get())
                self.idle()
                continue
            # tiny.en only has to spot the wake word; it runs on everything the mic hears
            heard = self.transcribe(self.tiny, audio, hotwords=HOTWORDS)
            m = WAKE.search(heard)
            if not m:
                continue  # speech that was not meant for us
            command = heard[m.end():].strip()
            if command:  # "JARVIS, read my memos" in one breath: re-read the command accurately
                heard = self.transcribe(self.base, audio, hotwords=HOTWORDS)
                m = WAKE.search(heard)
                command = heard[m.end():].strip() if m else heard
            print(f"  heard: {heard}")
            self.on_wake(command, audio)
            self.idle()

    def on_taps(self, taps: int) -> None:
        """Tap shortcuts: 1 = "JARVIS", 2 = "take a memo", 3 = "read my memos"."""
        print(f"  tapped {taps}x")
        if taps == 1:
            self.on_wake("", None)
        elif taps == 2:
            self.take_memo()
        else:
            self.read_memos()

    def on_wake(self, command: str, audio) -> None:
        if not MEMO_CMD.search(command) and not READ_CMD.search(command):
            self.status.set("listening")
            self.chime(WAKE_CHIME)
            self.say("Yes, sir?")
            audio = self.listener.listen(COMMAND_SILENCE, start_timeout=WAKE_TIMEOUT)
            if audio is None:
                self.say("Standing by.")
                return
            command = self.transcribe(self.base, audio, hotwords=HOTWORDS)
            print(f"  heard: {command}")

        if m := MEMO_CMD.search(command):
            dictated = command[m.end():].strip()
            # "take a memo: buy milk" in one breath -> that audio is the start of the memo
            if len(dictated.split()) >= 2:
                self.take_memo(first_audio=audio, first_text=dictated)
            else:
                self.take_memo()
        elif READ_CMD.search(command):
            self.read_memos()
        elif CANCEL.search(command):
            self.say("Standing by.")
        else:
            self.error("Sorry, sir. I can take a memo or read your memos.")

    def take_memo(self, first_audio=None, first_text="") -> None:
        live = [first_text] if first_text else []
        segments = queue.Queue()

        def live_transcript() -> None:  # rough words for the screen while recording
            while (segment := segments.get()) is not None:
                if text := self.transcribe(self.tiny, segment):
                    live.append(text)
                    self.status.set_text(" ".join(live))

        worker = threading.Thread(target=live_transcript, daemon=True)
        worker.start()
        self.status.set("recording", text=" ".join(live), rec_start=time.monotonic())
        if first_audio is None:
            self.chime(REC_CHIME)

        def on_grace(seconds_left) -> None:
            if seconds_left is None:
                self.status.set("recording")
            else:
                self.status.set("grace", countdown=seconds_left)

        audio = self.listener.listen(
            MEMO_SILENCE, start_timeout=None if first_audio is not None else WAKE_TIMEOUT,
            grace=GRACE, on_segment=segments.put, on_grace=on_grace,
            already_started=first_audio is not None)
        segments.put(None)

        if audio is None:
            worker.join()
            self.error("I did not hear a memo, sir.")
            return
        self.status.set("processing")
        if first_audio is not None:
            audio = np.concatenate([first_audio, audio])
        t0 = time.perf_counter()
        memo = clean_memo(self.transcribe(self.base, audio))
        print(f"  memo ({len(audio) / SAMPLE_RATE:.1f}s audio, "
              f"{time.perf_counter() - t0:.2f}s to transcribe): {memo}")
        worker.join()
        if not memo:
            self.error("My apologies, sir. I did not catch a memo.")
            return
        self.confirm(memo)

    def confirm(self, memo: str) -> None:
        for _ in range(3):
            self.status.set("confirm", text=memo)
            self.say(f"Memo: {memo} Save it, sir?")
            audio = self.listener.listen(COMMAND_SILENCE, start_timeout=ANSWER_TIMEOUT)
            if audio is None:
                self.save(memo)  # silence counts as yes
                return
            self.status.set("processing")
            answer = self.transcribe(self.base, audio)
            print(f"  heard: {answer}")
            if changes := CHANGE.findall(answer):
                applied, missing = [], []
                for old, new in changes:
                    old, new = strip_words(old), strip_words(new)
                    memo, n = re.subn(re.escape(old), new, memo, count=1, flags=re.I)
                    (applied if n else missing).append(new if n else old)
                if not missing:
                    self.save(memo, f"Changed to {' and '.join(applied)}. Saved, sir.")
                    return
                # keep the changes that worked, then read the memo back again
                self.error(f"I could not find “{' and '.join(missing)}” in the memo, sir.")
            elif NO.search(answer):
                self.idle()
                self.say("Memo discarded.")
                return
            elif YES.search(answer):
                self.save(memo)
                return
            else:
                self.error("Sorry, sir. Say yes, change something, or delete.")
        self.save(memo, "I will save it as it is, sir.")

    def save(self, memo: str, reply: str = "Saved, sir.") -> None:
        self.store.add(memo)
        self.status.set("saved", memo_count=len(self.store.memos))
        started = time.monotonic()
        self.say(reply)
        time.sleep(max(0.0, 1.3 - (time.monotonic() - started)))  # let both flashes finish

    def read_memos(self) -> None:
        memos = self.store.memos
        if not memos:
            self.say("You have no memos, sir.")
            return
        n = len(memos)
        self.status.set("reading", text="", detail=f"{n} memo{'' if n == 1 else 's'}")
        self.say(f"You have {n} memo{'' if n == 1 else 's'}.")
        for i, memo in enumerate(memos, 1):
            self.status.set("reading", text=memo["text"], detail=f"Memo {i} of {n}")
            self.say(("First: " if i == 1 else "Next: ") + memo["text"])
            time.sleep(1.0)  # a gap between memos
        self.say("That is all, sir.")


# ---------------------------------------------------------------- main

def take_display() -> bool:
    """piscreen.service also drives the MiniPiTFT: stop it while we run. Returns True if it was running."""
    running = subprocess.run(["systemctl", "is-active", "--quiet", "piscreen.service"]).returncode == 0
    if running:
        subprocess.run(["sudo", "-n", "systemctl", "stop", "piscreen.service"], check=False)
    return running


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # ssh sessions on the Pi default to latin-1
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wake-model", default="tiny.en",
                        help="whisper model that listens for the wake word and shows live text (default: tiny.en)")
    parser.add_argument("--memo-model", default="base.en",
                        help="whisper model for commands, memos and answers (default: base.en)")
    parser.add_argument("--vad-model", type=Path, default=DEFAULT_VAD)
    parser.add_argument("--voice", type=Path, default=DEFAULT_VOICE)
    parser.add_argument("--memos", type=Path, default=DEFAULT_MEMOS)
    parser.add_argument("--no-screen", action="store_true", help="do not use the MiniPiTFT")
    args = parser.parse_args()

    for path, what in [(args.vad_model, "VAD model"), (args.voice, "Piper voice")]:
        if not path.is_file():
            sys.exit(f"{what} not found at {path}. Run ./setup.sh first "
                     f"(and download en_GB-alan-medium for the voice).")

    status = Status()
    led = Led()
    screen, restore_piscreen = None, False
    if not args.no_screen:
        restore_piscreen = take_display()
        try:
            screen = Screen()
        except Exception as e:
            print(f"Screen unavailable ({e}); running without it.")

    stop = threading.Event()
    ui = threading.Thread(target=ui_loop, args=(status, led, screen, stop), daemon=True)
    ui.start()
    try:
        print("Loading models...", flush=True)
        status.set("processing")
        Jarvis(args, status).run()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stop.set()
        ui.join(timeout=1)
        led.set(0)
        if screen is not None:
            screen.off()
        if restore_piscreen:
            subprocess.run(["sudo", "-n", "systemctl", "start", "piscreen.service"], check=False)


if __name__ == "__main__":
    main()
