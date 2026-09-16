"""Tomato Crate Timer: a Pomodoro clock that counts time in tomatoes.

1 tomato = 1 minute. 25 tomatoes fill a crate (a work session), 5 fill a basket
(a break). Full crates are packed into boxes; when the day's boxes are packed a
truck ships them and the pay lands in the bank. Ending a session early ends the day:
the unfinished crate sells loose for its share of a crate's pay, full boxes ship and
pay, crates in an unfinished box are lost, and the clock returns to setup.

Buttons (Mini PiTFT): A = top (GPIO 23), B = bottom (GPIO 24).

On the Pi:
    sudo systemctl stop piscreen.service
    ~/venv/bin/python tomato_crate_timer.py                          # real time
    ~/venv/bin/python tomato_crate_timer.py --seconds-per-tomato 2   # fast demo
    ~/venv/bin/python tomato_crate_timer.py --reset                  # clear saved day

Without a Pi, render every screen to PNGs:
    python tomato_crate_timer.py --png-tour out_dir
"""
import argparse
import json
import os
import time
from datetime import date

from tomato_render import BASKET_SIZE, CRATE_SIZE, View, render

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tomato_state.json")
HOLD_TO_END = 2.0        # seconds of holding B that ends a crate early
TICK = 0.05

# how long the non-interactive screens stay up, at full speed.
# "partial" and "day_done" are not here on purpose: giving up on a crate and finishing
# a day both wait for the user to acknowledge them.
DWELL = {"crate_done": 3.0, "box_packed": 3.5, "ship": 7.0, "shipped": 8.0}

SETTINGS = [                        # label, state key, values to cycle through
    ("Boxes today", "boxes_per_day", [1, 2, 3, 4, 5, 6]),
    ("Crates / box", "crates_per_box", [1, 2, 3, 4, 5, 6]),
    ("Pay / box", "pay_per_box", [4, 6, 8, 10, 12, 16, 20, 30]),
]
DEFAULT_CONFIG = {"boxes_per_day": 3, "crates_per_box": 4, "pay_per_box": 12}


class Button:
    """One Mini PiTFT button: pulled up, so it reads low while pressed."""

    def __init__(self, pin):
        import digitalio
        self.io = digitalio.DigitalInOut(pin)
        self.io.switch_to_input(pull=digitalio.Pull.UP)
        self.down = False
        self.since = 0.0
        self.clicked = False
        self.released = False

    def poll(self, now):
        pressed = not self.io.value
        self.clicked = pressed and not self.down
        self.released = self.down and not pressed
        if self.clicked:
            self.since = now
        self.down = pressed

    def held_for(self, now):
        return now - self.since if self.down else 0.0


class Timer:
    def __init__(self, seconds_per_tomato, break_seconds_per_tomato=None):
        self.spt = seconds_per_tomato
        self.break_spt = break_seconds_per_tomato or seconds_per_tomato
        self.speed = max(0.25, min(1.0, seconds_per_tomato / 60))   # shrink dwells in demo mode
        self.config = dict(DEFAULT_CONFIG)
        self.crates_done = 0
        self.boxes_done = 0
        self.crates_in_box = 0
        self.bank = 0.0
        self.focus_minutes = 0
        self.setup_sel = 0
        self.frozen = 0          # tomatoes in the crate when it was paused
        self.swallow_release = False
        self.chord_fired = False
        self.boxes_paid, self.boxes_pay = 0, 0.0   # full boxes shipped by an early end
        self.consumed_b = None   # the B press that a chord used up, so its release does nothing
        self.load()
        # a restart mid-day waits on the ready screen rather than starting a crate on its own
        self.enter("ready" if self.crates_done or self.boxes_done else "setup")

    # --- persistence ---
    def load(self):
        try:
            with open(STATE_PATH) as f:
                saved = json.load(f)
        except (OSError, ValueError):
            return
        self.config.update(saved.get("config", {}))
        self.bank = saved.get("bank", 0.0)
        if saved.get("date") == date.today().isoformat():       # same day: pick up where we left off
            self.crates_done = saved.get("crates_done", 0)
            self.boxes_done = saved.get("boxes_done", 0)
            self.crates_in_box = saved.get("crates_in_box", 0)
            self.focus_minutes = saved.get("focus_minutes", 0)

    def save(self):
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"date": date.today().isoformat(), "config": self.config, "bank": round(self.bank, 2),
                       "crates_done": self.crates_done, "boxes_done": self.boxes_done,
                       "crates_in_box": self.crates_in_box, "focus_minutes": self.focus_minutes}, f, indent=1)
        os.replace(tmp, STATE_PATH)

    # --- derived numbers ---
    @property
    def crates_goal(self):
        return self.config["boxes_per_day"] * self.config["crates_per_box"]

    @property
    def crate_value(self):
        return self.config["pay_per_box"] / self.config["crates_per_box"]

    def partial_pay(self, tomatoes):
        return round(self.crate_value * tomatoes / CRATE_SIZE, 2)

    def box_slots(self):
        """How many crates sit in each of today's boxes."""
        slots = []
        for i in range(self.config["boxes_per_day"]):
            if i < self.boxes_done:
                slots.append(self.config["crates_per_box"])
            elif i == self.boxes_done:
                slots.append(self.crates_in_box)
            else:
                slots.append(0)
        return slots

    def tomatoes(self, now, limit):
        spt = self.break_spt if self.mode == "break" else self.spt
        return min(limit, int((now - self.started) // spt))

    def dwell(self, mode):
        return max(1.5, DWELL[mode] * self.speed)

    # --- state machine ---
    def enter(self, mode, now=None):
        self.mode = mode
        self.started = now if now is not None else time.monotonic()
        self.payout = 0.0

    def press_a(self, now):
        if self.mode == "setup":
            if self.setup_sel < len(SETTINGS):                           # the last row is Start: A alone does nothing
                label, key, values = SETTINGS[self.setup_sel]
                self.config[key] = values[(values.index(self.config[key]) + 1) % len(values)]
        elif self.mode == "day_done":
            self.new_day(now)
        elif self.mode == "partial":                                     # any button moves on
            self.finish_dwell(now)
        elif self.mode == "work":
            self.frozen = self.tomatoes(now, CRATE_SIZE)
            self.enter("paused", now)
        elif self.mode in ("paused", "end_early"):
            self.enter("work", now - self.frozen * self.spt)             # resume where the crate left off

    def press_b(self, now):
        if self.mode == "setup":
            self.setup_sel = (self.setup_sel + 1) % (len(SETTINGS) + 1)   # wraps, so settings can be revisited
        elif self.mode == "ready":
            self.enter("work", now)
        elif self.mode == "day_done":
            self.new_day(now)
        elif self.mode in ("shipped", "box_packed", "crate_done", "partial"):
            self.finish_dwell(now)

    def handle_input(self, now, a, b):
        """Turn the two buttons into actions. A acts on press, B on release or hold."""
        both = a.down and b.down
        if both and not self.chord_fired:
            self.chord_fired = True
            self.consumed_b = b.since             # this B press belongs to the chord
            self.press_ab(now)
        if a.clicked and not both:
            self.press_a(now)
        if b.down and not (both or self.chord_fired):
            self.hold_b(now, b.held_for(now))
        if b.released:
            if b.since == self.consumed_b or self.swallow_release:
                self.swallow_release = False      # this release was already accounted for
            elif self.mode == "end_early":
                self.release_b(now)
            else:
                self.press_b(now)
        if not (a.down or b.down):
            self.chord_fired = False

    def press_ab(self, now):
        """Both buttons at once: starts the day from the Start row of setup."""
        if self.mode == "setup" and self.setup_sel == len(SETTINGS):
            self.setup_sel = 0
            self.save()
            self.enter("work", now)

    def new_day(self, now):
        """Back to setup for a fresh day; the bank carries over."""
        self.crates_done = self.boxes_done = self.crates_in_box = 0
        self.focus_minutes = 0
        self.setup_sel = 0
        self.save()
        self.enter("setup", now)

    def hold_b(self, now, seconds):
        """B held down: only the paused screen reacts, by ending the crate early."""
        if self.mode == "paused" and seconds > 0.15:
            self.enter("end_early", now)
            self.hold_start = now
        if self.mode == "end_early":
            self.payout = self.partial_pay(self.frozen)
            if seconds >= HOLD_TO_END:
                self.sell_partial(now)

    def release_b(self, now):
        if self.mode == "end_early":                                     # let go early: back to the pause
            self.enter("paused", now)

    def sell_partial(self, now):
        """Ending a crate early ends the day: the loose crate and any full boxes are paid,
        crates sitting in an unfinished box are lost, and the next screen is setup again."""
        tomatoes = self.frozen
        self.boxes_paid = self.boxes_done
        self.boxes_pay = self.boxes_done * self.config["pay_per_box"]
        self.bank += self.partial_pay(tomatoes) + self.boxes_pay
        self.focus_minutes += tomatoes
        self.save()
        self.enter("partial", now)
        self.swallow_release = True
        self.payout = self.partial_pay(tomatoes)
        self.partial_tomatoes = tomatoes

    def finish_crate(self, now):
        self.crates_done += 1
        self.crates_in_box += 1
        self.focus_minutes += CRATE_SIZE
        self.save()
        self.enter("crate_done", now)

    def finish_dwell(self, now):
        """Move on from a screen that is just showing the result of something."""
        if self.mode == "crate_done":
            if self.crates_in_box >= self.config["crates_per_box"]:
                self.boxes_done += 1
                self.crates_in_box = 0
                self.save()
                self.enter("box_packed", now)
            else:
                self.enter("break", now)
        elif self.mode == "box_packed":
            self.enter("ship" if self.boxes_done >= self.config["boxes_per_day"] else "break", now)
        elif self.mode == "ship":
            self.payout = self.config["boxes_per_day"] * self.config["pay_per_box"]
            self.bank += self.payout
            self.save()
            pay = self.payout
            self.enter("shipped", now)
            self.payout = pay
        elif self.mode in ("shipped",):
            self.enter("day_done", now)
        elif self.mode == "partial":
            self.new_day(now)                        # the early end closed the day: set up a new one

    def update(self, now):
        if self.mode == "work" and self.tomatoes(now, CRATE_SIZE) >= CRATE_SIZE:
            self.finish_crate(now)
        elif self.mode == "break" and self.tomatoes(now, BASKET_SIZE) >= BASKET_SIZE:
            self.enter("ready", now)
        elif self.mode in DWELL and now - self.started >= self.dwell(self.mode):
            self.finish_dwell(now)

    # --- what to draw ---
    def view(self, now):
        v = View(mode=self.mode, money=self.bank, crates_done=self.crates_done, crates_goal=self.crates_goal,
                 boxes_done=self.boxes_done, boxes_goal=self.config["boxes_per_day"],
                 crates_per_box=self.config["crates_per_box"], box_slots=self.box_slots(),
                 crate_value=self.crate_value, crate_index=self.crates_done + 1,
                 hours=self.focus_minutes / 60, payout=self.payout)
        if self.mode == "work":
            v.tomatoes = self.tomatoes(now, CRATE_SIZE)
        elif self.mode in ("paused", "end_early"):
            v.tomatoes = self.frozen
        elif self.mode == "break":
            v.tomatoes = self.tomatoes(now, BASKET_SIZE)
        elif self.mode == "partial":
            v.tomatoes = getattr(self, "partial_tomatoes", 0)
            v.boxes_paid, v.boxes_pay = self.boxes_paid, self.boxes_pay
        if self.mode == "end_early":
            v.hold = min(1.0, (now - self.hold_start) / HOLD_TO_END)
        if self.mode == "setup":
            v.setup_sel = self.setup_sel
            v.setup_rows = [(label, f"${self.config[key]}" if key == "pay_per_box" else str(self.config[key]))
                            for label, key, _ in SETTINGS]
            v.setup_rows.append(("Start day", "A + B"))
            v.hours = self.crates_goal * (CRATE_SIZE + BASKET_SIZE) / 60
        if self.mode in ("ship", "shipped"):
            v.anim = min(1.0, (now - self.started) / self.dwell(self.mode))
        return v


def png_tour(out_dir, spt):
    """Render one frame of every screen, for checking the layouts without a Pi."""
    os.makedirs(out_dir, exist_ok=True)
    t = Timer(spt)
    t.config = dict(DEFAULT_CONFIG)
    now = time.monotonic()
    frames = []

    t.mode, t.setup_sel = "setup", 0
    frames.append(("01-setup", t.view(now)))

    t.enter("work", now - 1 * spt)
    frames.append(("02-work", t.view(now)))

    t.frozen = 12
    t.enter("paused", now)
    frames.append(("03-paused", t.view(now)))

    t.enter("end_early", now)
    t.hold_start = now - 1.4
    t.payout = t.partial_pay(12)
    frames.append(("04-end-early", t.view(now)))

    t.partial_tomatoes, t.payout = 12, t.partial_pay(12)
    t.bank += t.payout
    t.mode = "partial"
    frames.append(("05-partial", t.view(now)))

    t.enter("ready", now)
    frames.append(("06-ready", t.view(now)))

    t.crates_done, t.crates_in_box = 1, 1
    t.mode = "crate_done"
    frames.append(("07-crate-done", t.view(now)))

    t.enter("break", now - 2 * spt)
    frames.append(("08-break", t.view(now)))

    t.crates_done, t.crates_in_box, t.boxes_done = 4, 0, 1
    t.mode = "box_packed"
    frames.append(("09-box-packed", t.view(now)))

    t.crates_done, t.boxes_done, t.focus_minutes = 12, 3, 360
    t.enter("ship", now - 3.5 * t.speed)
    frames.append(("10-ship", t.view(now)))

    t.payout = 36
    t.bank += 36
    t.enter("shipped", now - 1.0)
    t.payout = 36
    frames.append(("11-shipped", t.view(now)))

    t.enter("day_done", now)
    frames.append(("12-day-done", t.view(now)))

    for name, view in frames:
        render(view).save(os.path.join(out_dir, name + ".png"))
    print(f"wrote {len(frames)} frames to {out_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seconds-per-tomato", type=float, default=60)
    parser.add_argument("--reset", action="store_true", help="forget the saved day and bank")
    parser.add_argument("--png-tour", metavar="DIR", help="render every screen to PNGs and exit")
    args = parser.parse_args()

    if args.reset and os.path.exists(STATE_PATH):
        os.remove(STATE_PATH)
    if args.png_tour:
        png_tour(args.png_tour, args.seconds_per_tomato)
        return

    disp, button_a, button_b = setup_hardware()
    timer = Timer(args.seconds_per_tomato)
    try:
        while True:
            now = time.monotonic()
            button_a.poll(now)
            button_b.poll(now)
            timer.handle_input(now, button_a, button_b)
            timer.update(now)
            disp.image(render(timer.view(now)), 90)
            time.sleep(TICK)
    except KeyboardInterrupt:
        timer.save()
        blank(disp)


def setup_hardware():
    """The Mini PiTFT display (landscape, backlight on) and its two buttons."""
    import board
    import digitalio
    import adafruit_rgb_display.st7789 as st7789

    disp = st7789.ST7789(
        board.SPI(),
        cs=digitalio.DigitalInOut(board.D5),
        dc=digitalio.DigitalInOut(board.D25),
        rst=None,
        baudrate=64000000,
        width=135,
        height=240,
        x_offset=53,
        y_offset=40,
    )
    backlight = digitalio.DigitalInOut(board.D22)
    backlight.switch_to_output()
    backlight.value = True
    return disp, Button(board.D23), Button(board.D24)


def blank(disp):
    from PIL import Image
    disp.image(Image.new("RGB", (240, 135), (0, 0, 0)), 90)


if __name__ == "__main__":
    main()
