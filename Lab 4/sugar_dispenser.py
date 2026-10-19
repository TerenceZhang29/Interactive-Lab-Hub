"""Joystick-triggered MS18 prototype; no hardware imports in simulation.

Direct drive has a finite stroke budget. Ratchet mode requires a physical
one-way indexing mechanism: servo return must NOT turn the sugar wheel back.
Pulse widths are calibration inputs, never measured shaft angles.
Alternate mode holds the opposite endpoint after each request; it never
automatically returns a two-slot ring across the outlet.
"""

import argparse
from dataclasses import dataclass
import math
import time


@dataclass(frozen=True)
class Config:
    mode: str = "direct"
    continuous: bool = False
    max_pending: int = 4
    gesture: str = "circle"
    x_sign: int = 1
    y_sign: int = 1
    channel: int = 1
    home_ms: float = 1.0
    step_ms: float = 1.0
    limit_ms: float = 2.0
    capacity: int = 4
    center_x: int = 508
    center_y: int = 510
    neutral_threshold: int = 100
    trigger_threshold: int = 300
    neutral_seconds: float = 0.2
    trigger_seconds: float = 0.08
    move_seconds: float = 0.6
    drop_seconds: float = 0.5
    ramp_seconds: float = 0.0

    def __post_init__(self):
        if self.mode not in ("direct", "ratchet", "alternate") or not 0 <= self.channel < 16:
            raise ValueError("Invalid mechanism mode or servo channel")
        if self.gesture not in ("circle", "push") or self.x_sign not in (-1, 1) or self.y_sign not in (-1, 1):
            raise ValueError("Invalid gesture or joystick orientation")
        if self.continuous and (self.mode not in ("ratchet", "alternate") or self.gesture != "circle" or self.capacity != 0):
            raise ValueError("Continuous test requires repeatable motion, circles, and capacity=0")
        values = (self.home_ms, self.step_ms, self.limit_ms,
                  self.neutral_seconds, self.trigger_seconds,
                  self.move_seconds, self.drop_seconds, self.ramp_seconds)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Calibration and timing must be finite")
        if not (0.5 <= self.home_ms < self.limit_ms <= 2.5):
            raise ValueError("Require 0.5 <= home_ms < limit_ms <= 2.5")
        if not 0 < self.step_ms <= self.limit_ms - self.home_ms + 1e-9:
            raise ValueError("Step must fit within the calibrated pulse range")
        if self.capacity < 0 or self.max_pending < 1 or min(values[3:-1]) <= 0 or self.ramp_seconds < 0:
            raise ValueError("Capacity must be nonnegative; queue size and timing positive")
        if not (0 <= self.center_x <= 1023 and 0 <= self.center_y <= 1023):
            raise ValueError("Joystick center must be in 0..1023")
        if not 0 < self.neutral_threshold < self.trigger_threshold <= 1023:
            raise ValueError("Require neutral threshold < trigger threshold")

    @property
    def direct_steps(self):
        return math.floor((self.limit_ms - self.home_ms) / self.step_ms + 1e-9)


class Dispenser:
    """Nonblocking state machine; optional queue counts complete circles only."""

    def __init__(self, config, write_pulse, report=print):
        self.config = config
        self.write_pulse = write_pulse
        self.report = report
        self.state = "WAIT_NEUTRAL"
        self.completed_cycles = 0  # Commands completed, NOT confirmed sugar drops.
        self.pending_cycles = 0
        self.deadline = 0.0
        self.neutral_since = None
        self.push_since = None
        self.circle_angle = None
        self.circle_time = None
        self.circle_progress = 0.0
        self.commanded_ms = config.home_ms
        self.motion_start_ms = config.home_ms
        self.motion_target_ms = config.home_ms
        self.motion_started = 0.0

    def command(self, pulse_ms):
        if not self.config.home_ms - 1e-9 <= pulse_ms <= self.config.limit_ms + 1e-9:
            raise ValueError("Servo command outside configured range")
        self.write_pulse(pulse_ms)
        self.commanded_ms = pulse_ms

    def reset_circle(self):
        self.circle_angle = self.circle_time = None
        self.circle_progress = 0.0

    def circle_complete(self, now, x, y):
        c = self.config
        dx = (x - c.center_x) * c.x_sign
        dy = (y - c.center_y) * c.y_sign
        if math.hypot(dx, dy) < c.trigger_threshold:
            self.reset_circle()
            return False
        # With X increasing right and Y increasing down: top -> right is CW.
        angle = math.atan2(dx, -dy)
        if self.circle_angle is not None:
            delta = (angle - self.circle_angle + math.pi) % math.tau - math.pi
            if now - self.circle_time > 0.25 or abs(delta) > math.pi / 4:
                # Lost samples or jumps between directions aren't a traced circle.
                self.reset_circle()
            else:
                # Signed accumulation: retracing a path cancels its forward travel.
                self.circle_progress += delta
                if self.circle_progress >= math.tau - 1e-9:
                    self.reset_circle()
                    return True
                if self.circle_progress <= -math.tau:
                    self.reset_circle()
        self.circle_angle = angle
        self.circle_time = now
        return False

    def advance(self, now):
        c = self.config
        step = self.completed_cycles + 1 if c.mode == "direct" else 1
        target = c.home_ms + step * c.step_ms
        if c.mode == "alternate" and self.completed_cycles % 2:
            target = c.home_ms
        if target > c.limit_ms + 1e-9:
            raise ValueError("Servo target exceeds calibrated limit")
        self.motion_start_ms = self.commanded_ms
        self.motion_target_ms = min(target, c.limit_ms)
        self.motion_started = now
        if c.ramp_seconds:
            self.state = "RAMPING"
            self.deadline = now + c.ramp_seconds
        else:
            self.command(self.motion_target_ms)
            self.state = "ADVANCING"
            self.deadline = now + c.move_seconds
        self.push_since = self.neutral_since = None
        if not c.continuous:
            self.reset_circle()
        self.report("ADVANCING: gesture accepted; additional full circles can queue."
                    if c.continuous else
                    "ADVANCING: gesture accepted; further input ignored.")
        if c.mode == "alternate":
            self.report(f"RING: {self.motion_start_ms:.3f} -> "
                        f"{self.motion_target_ms:.3f} ms; hold endpoint, no automatic return.")

    def tick(self, now, x, y, button=1):
        if self.state == "STOPPED":
            return
        if button == 0:
            self.state = "STOPPED"
            self.pending_cycles = 0
            self.report("STOP: button pressed; inspect wheel before restarting.")
            return
        if not (0 <= x <= 1023 and 0 <= y <= 1023 and button == 1):
            raise ValueError("Invalid joystick sample; stopping rather than dispensing")
        c = self.config
        distance = max(abs(x - c.center_x), abs(y - c.center_y))

        if c.continuous and self.state in ("RAMPING", "ADVANCING", "DROPPING", "RETURNING"):
            if self.circle_complete(now, x, y):
                if self.pending_cycles < c.max_pending:
                    self.pending_cycles += 1
                    self.report(f"QUEUED: {self.pending_cycles} pending cycle(s).")
                else:
                    self.report("QUEUE FULL: this circle was not accepted; slow down.")

        if self.state == "RAMPING":
            progress = min(1.0, max(0.0, (now - self.motion_started) / c.ramp_seconds))
            self.command(self.motion_start_ms +
                         (self.motion_target_ms - self.motion_start_ms) * progress)
            if progress >= 1.0:
                self.state = "ADVANCING"
                self.deadline = now + c.move_seconds
        elif self.state == "ADVANCING" and now >= self.deadline:
            self.state = "DROPPING"
            self.deadline = now + c.drop_seconds
        elif self.state == "DROPPING" and now >= self.deadline:
            if c.mode == "ratchet":
                self.command(c.home_ms)
                self.state = "RETURNING"
                self.deadline = now + c.move_seconds
            else:
                self.finish_cycle()
        elif self.state == "RETURNING" and now >= self.deadline:
            self.finish_cycle()
        elif self.state == "WAIT_NEUTRAL":
            if distance <= c.neutral_threshold:
                if self.neutral_since is None:
                    self.neutral_since = now
                if now - self.neutral_since >= c.neutral_seconds:
                    self.state = "READY"
                    self.report("READY: trace a full clockwise circle for one cycle."
                                if c.gesture == "circle" else
                                "READY: move stick in any direction for one cycle.")
            else:
                self.neutral_since = None
        elif self.state == "READY":
            if c.gesture == "circle":
                if self.circle_complete(now, x, y):
                    self.advance(now)
                return
            if distance >= c.trigger_threshold:
                if self.push_since is None:
                    self.push_since = now
                if now - self.push_since >= c.trigger_seconds:
                    self.advance(now)
            else:
                self.push_since = None

        if c.continuous and self.state == "READY" and self.pending_cycles:
            self.pending_cycles -= 1
            self.advance(now)

    def finish_cycle(self):
        self.completed_cycles += 1
        c = self.config
        self.neutral_since = self.push_since = None
        if not c.continuous:
            self.reset_circle()
        if c.capacity and self.completed_cycles >= c.capacity:
            self.state = "EMPTY_ESTIMATE"
        elif c.mode == "direct" and self.completed_cycles >= c.direct_steps:
            self.state = "TRAVEL_LIMIT"
        else:
            self.state = "READY" if c.gesture == "circle" else "WAIT_NEUTRAL"
        capacity_label = str(c.capacity) if c.capacity else "unlimited"
        self.report(f"Cycle {self.completed_cycles}/{capacity_label}: {self.state}. "
                    "Sugar drop has not been sensed.")


def simulate(config):
    """Hold, release and repeat: deterministic demo without real hardware."""
    pulses = []
    controller = Dispenser(config, lambda p: pulses.append(p))
    now = 0.0
    if config.gesture == "circle":
        for _ in range(25):
            controller.tick(now, config.center_x, config.center_y)
            now += 0.02
        for _ in range((config.capacity or 5) + 1):
            for i in range(121):
                angle = math.tau * i / 120
                x = config.center_x + round(400 * math.sin(angle)) * config.x_sign
                y = config.center_y - round(400 * math.cos(angle)) * config.y_sign
                controller.tick(now, x, y)
                now += 0.02
            wait = max(2.0, config.ramp_seconds + config.move_seconds *
                       (2 if config.mode == "ratchet" else 1) + config.drop_seconds + 0.2)
            for _ in range(round(wait / 0.02)):
                controller.tick(now, config.center_x, config.center_y)
                now += 0.02
    else:
        simulate_push(controller, config, now)
    pulse_summary = pulses if len(pulses) <= 20 else {
        "count": len(pulses), "min_ms": min(pulses),
        "max_ms": max(pulses), "last_ms": pulses[-1]}
    print(f"SIMULATION ONLY: completed={controller.completed_cycles}, "
          f"state={controller.state}, pulse commands={pulse_summary}")


def simulate_push(controller, config, now):
    for _ in range(config.capacity + 1):
        for x, duration in ((config.center_x, 0.5), (1023, 3.0)):
            for _ in range(round(duration / 0.02)):
                controller.tick(now, x, config.center_y)
                now += 0.02


def run_hardware(config):
    import pi_servo_hat
    import qwiic_joystick

    joystick = qwiic_joystick.QwiicJoystick()
    if not joystick.connected or joystick.begin() is False:
        raise RuntimeError("Qwiic joystick unavailable")
    hat = pi_servo_hat.PiServoHat(address=0x40)
    if not hat.is_connected():
        raise RuntimeError("Servo pHAT unavailable at 0x40")

    def write_pulse(pulse_ms):
        # At 50 Hz, a frame is 20 ms; specify duty in percent.
        hat.set_duty_cycle(config.channel, pulse_ms / 20.0 * 100.0)

    controller = Dispenser(config, write_pulse)
    try:
        if config.continuous:
            print("CONTINUOUS TEST: one movement cycle per full circle. "
                  "No inventory stop; button clears queued requests and stops.")
        if config.mode == "alternate":
            print("TWO-SLOT RING TEST: alternating endpoints; no automatic return. "
                  "Pulse range is a candidate for 180 degrees, not a measured angle.")
        print(f"Channel {config.channel}: {config.home_ms:.3f} -> "
              f"{config.home_ms + config.step_ms:.3f} ms; "
              f"mode={config.mode}, gesture={config.gesture}.")
        input("Empty/unload the mechanism before homing; Enter to initialize: ")
        # restart() sets 50 Hz and resets the HAT; don't share it with another app.
        hat.restart()
        if config.ramp_seconds:
            # Start from center, then approach the configured start slowly.
            # This is commanded positioning, not position feedback or jam detection.
            print(f"HOMING: center first, then slowly approach {config.home_ms:.3f} ms. "
                  "Press joystick button to stop.")
            write_pulse(1.5)
            time.sleep(config.move_seconds)
            started = time.monotonic()
            while True:
                if joystick.button == 0:
                    raise KeyboardInterrupt
                progress = min(1.0, (time.monotonic() - started) / config.ramp_seconds)
                write_pulse(1.5 + (config.home_ms - 1.5) * progress)
                if progress >= 1:
                    break
                time.sleep(0.02)
        else:
            write_pulse(config.home_ms)
        time.sleep(config.move_seconds)
        input("Keep ring EMPTY; check clearance; Enter to run ring test: "
              if config.mode == "alternate" else
              "Keep mechanism EMPTY for continuous test; Enter to run: "
              if config.continuous or config.mode == "alternate" else
              "Align wheel at a non-drop position, load cubes; Enter to run: ")
        print("Trace a full clockwise circle for one cycle."
              if config.gesture == "circle" else "Push once, then return to center.")
        print("Press stick button or Ctrl+C to stop.")
        while controller.state != "STOPPED":
            # Read the stop button first, including while the servo is moving.
            button = joystick.button
            if button == 0:
                controller.tick(time.monotonic(), config.center_x,
                                config.center_y, button)
                break
            controller.tick(time.monotonic(), joystick.horizontal,
                            joystick.vertical, button)
            time.sleep(0.02)
    finally:
        # Disable ONLY this channel's PWM; never rewind a loaded direct-drive wheel.
        # This removes the control signal, not electrical power or mechanical motion.
        # The older pi_servo_hat implementation maps 0% duty to -1 ticks.
        # Its set_channel_word helper also rejects bit 12 (>4095), so write
        # LEDn_OFF's full-off word through the existing driver after enabling AI.
        hat.PCA9685.set_channel_word(config.channel, 1, 0)
        hat.PCA9685._i2c.writeWord(hat.PCA9685.address,
                                 0x08 + 4 * config.channel, 0x1000)
        print(f"PWM disabled on channel {config.channel}; "
              f"completed command cycles={controller.completed_cycles}. "
              "Inspect position and unload before restart.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hardware", action="store_true",
                        help="use Pi hardware; default is a simulation")
    parser.add_argument("--mode", choices=("direct", "ratchet", "alternate"), default="direct")
    parser.add_argument("--ring-180", action="store_true",
                        help="two-slot ring test: slow alternating half-turn candidates, no auto-return")
    parser.add_argument("--continuous", action="store_true",
                        help="unlimited empty advance/return test; queues up to four circles")
    parser.add_argument("--gesture", choices=("circle", "push"), default="circle")
    parser.add_argument("--x-sign", type=int, choices=(-1, 1), default=1)
    parser.add_argument("--y-sign", type=int, choices=(-1, 1), default=1)
    parser.add_argument("--channel", type=int, default=1)
    parser.add_argument("--home-ms", type=float)
    parser.add_argument("--step-ms", type=float)
    parser.add_argument("--limit-ms", type=float)
    parser.add_argument("--ramp-seconds", type=float)
    parser.add_argument("--capacity", type=int, default=4)
    parser.add_argument("--center-x", type=int, default=508)
    parser.add_argument("--center-y", type=int, default=510)
    args = vars(parser.parse_args())
    hardware = args.pop("hardware")
    ring = args.pop("ring_180")
    if args["continuous"]:
        args["mode"] = "ratchet"
        args["capacity"] = 0
    if ring:
        args["mode"] = "alternate"
        args["capacity"] = 0
    defaults = {"home_ms": 0.5 if ring else 0.875,
                "step_ms": 1.9 if ring else 1.25,
                "limit_ms": 2.4 if ring else 2.125,
                "ramp_seconds": 3.0 if ring else 0.0}
    for name, value in defaults.items():
        if args[name] is None:
            args[name] = value
    try:
        config = Config(**args)
        run_hardware(config) if hardware else simulate(config)
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        parser.exit(1, f"Stopped: {error}\n")
    except (KeyboardInterrupt, EOFError):
        print("Stopped by operator.")


if __name__ == "__main__":
    main()
