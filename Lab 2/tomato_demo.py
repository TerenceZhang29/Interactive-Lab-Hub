"""Speed-run demo of the Tomato Crate Timer, for videos and show-and-tell.

Runs the real clock, just faster: set up the day with the buttons as usual, start it
with A + B, and each crate fills in seconds. Crates follow breaks on their own, so a
whole day plays through to the day-done screen; any button there goes back to setup.
Progress goes to a throwaway file, so the real day and bank are never touched.

On the Pi:
    sudo systemctl stop piscreen.service
    ~/venv/bin/python tomato_demo.py                          # crate in 15 s, basket in 5 s
    ~/venv/bin/python tomato_demo.py --work-seconds 10 --break-seconds 3
    ~/venv/bin/python tomato_demo.py --wait-on-ready          # press B to start each crate, as in the clock

Tip: 1 box x 2 crates on the setup screen makes a full day take under a minute.
"""
import argparse
import os
import tempfile
import time

import tomato_crate_timer as clock
from tomato_render import BASKET_SIZE, CRATE_SIZE, render

RESULT_SPEED = 0.5    # packing and truck screens at half their normal length, long enough to watch


def run(disp, button_a, button_b, work_seconds=15, break_seconds=5, wait_on_ready=False, seconds=None):
    """Drive the clock on the display until interrupted (or for `seconds`). Returns the timer."""
    clock.STATE_PATH = os.path.join(tempfile.gettempdir(), "tomato_demo_state.json")   # never the real day
    if os.path.exists(clock.STATE_PATH):
        os.remove(clock.STATE_PATH)

    timer = clock.Timer(work_seconds / CRATE_SIZE, break_seconds / BASKET_SIZE)   # starts on setup
    timer.speed = RESULT_SPEED
    start = time.monotonic()
    last_mode = None
    try:
        while seconds is None or time.monotonic() - start < seconds:
            now = time.monotonic()
            button_a.poll(now)
            button_b.poll(now)
            timer.handle_input(now, button_a, button_b)
            timer.update(now)
            if timer.mode == "ready" and not wait_on_ready:
                timer.enter("work", now)
            if timer.mode != last_mode:                 # a running log of screens, handy while filming
                print(f"{now - start:6.1f}s  {timer.mode}", flush=True)
                last_mode = timer.mode
            disp.image(render(timer.view(now)), 90)
            time.sleep(clock.TICK)
    except KeyboardInterrupt:
        pass
    return timer


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--work-seconds", type=float, default=15, help="time to fill the 25-tomato crate")
    parser.add_argument("--break-seconds", type=float, default=5, help="time to fill the 5-tomato basket")
    parser.add_argument("--wait-on-ready", action="store_true", help="wait for B before each crate, as the clock does")
    parser.add_argument("--seconds", type=float, help="stop by itself after this long")
    args = parser.parse_args()

    disp, button_a, button_b = clock.setup_hardware()
    run(disp, button_a, button_b, args.work_seconds, args.break_seconds, args.wait_on_ready, args.seconds)
    clock.blank(disp)


if __name__ == "__main__":
    main()
