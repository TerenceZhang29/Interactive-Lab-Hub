"""Finite, unloaded servo test after wiring and separate power are confirmed.

Target values use a 180-degree mapping over 1–2 ms pulses; they are not
measurements of the actual shaft angle. The final command holds center.
"""

import argparse
import time

import pi_servo_hat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", type=int, choices=range(16), default=0)
    channel = parser.parse_args().channel
    servo = pi_servo_hat.PiServoHat(address=0x40, min_pt=1, max_pt=2)
    servo.restart()
    try:
        for cycle in range(1, 3):
            for target in (90, 75, 90, 105, 90):
                servo.move_servo_position(channel, target, swing=180)
                print(f"Channel {channel}, cycle {cycle}: target={target}, pulse={1 + target / 180:.3f} ms")
                time.sleep(1)
    finally:
        servo.move_servo_position(channel, 90, swing=180)
        print("Center command sent (1.5 ms).")


if __name__ == "__main__":
    main()
