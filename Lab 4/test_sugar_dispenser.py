"""Control logic checks; these do not verify motion or actual sugar drops."""

import unittest
import math
from unittest.mock import Mock, PropertyMock, patch
from types import SimpleNamespace
from sugar_dispenser import Config, Dispenser, main, run_hardware


class DispenserTests(unittest.TestCase):
    def setUp(self):
        self.pulses = []
        self.now = 0.0
        self.app = Dispenser(Config(mode="ratchet", gesture="push"), self.pulses.append,
                             lambda _: None)

    def sample_for(self, x, seconds, button=1):
        for _ in range(round(seconds / 0.02)):
            self.app.tick(self.now, x, 510, button)
            self.now += 0.02

    def gesture(self):
        self.sample_for(508, 0.5)
        self.sample_for(1023, 3.0)

    def test_startup_requires_neutral(self):
        self.sample_for(1023, 4)
        self.assertEqual(self.pulses, [])

    def test_long_hold_dispenses_only_once(self):
        self.gesture()
        self.sample_for(1023, 10)
        self.assertEqual(self.app.completed_cycles, 1)
        self.assertEqual(self.pulses, [2.0, 1.0])

    def test_noise_and_short_push_do_not_trigger(self):
        self.sample_for(508, 0.5)
        for _ in range(20):
            self.sample_for(1023, 0.04)
            self.sample_for(750, 0.1)
        self.assertEqual(self.pulses, [])

    def test_requires_stable_center_between_cycles(self):
        self.gesture()
        self.sample_for(508, 0.1)
        self.sample_for(1023, 3)
        self.assertEqual(self.app.completed_cycles, 1)
        self.gesture()
        self.assertEqual(self.app.completed_cycles, 2)

    def test_gestures_during_motion_are_not_queued(self):
        self.sample_for(508, 0.5)
        self.sample_for(1023, 0.2)
        self.sample_for(508, 0.3)
        self.sample_for(0, 3)
        self.assertEqual(self.app.completed_cycles, 1)

    def test_four_cycles_then_inventory_lockout(self):
        for _ in range(7):
            self.gesture()
        self.assertEqual(self.app.completed_cycles, 4)
        self.assertEqual(self.app.state, "EMPTY_ESTIMATE")
        self.assertEqual(len(self.pulses), 8)

    def test_direct_drive_does_not_wrap_or_return(self):
        self.app = Dispenser(Config(gesture="push"), self.pulses.append, lambda _: None)
        for _ in range(4):
            self.gesture()
        self.assertEqual(self.pulses, [2.0])
        self.assertEqual(self.app.state, "TRAVEL_LIMIT")

    def test_direct_drive_can_use_multiple_calibrated_strokes(self):
        self.app = Dispenser(Config(step_ms=0.5, gesture="push"), self.pulses.append,
                             lambda _: None)
        for _ in range(4):
            self.gesture()
        self.assertEqual(self.pulses, [1.5, 2.0])
        self.assertEqual(self.app.completed_cycles, 2)

    def test_stop_during_each_motion_phase_never_returns(self):
        for phase in ("RAMPING", "ADVANCING", "DROPPING", "RETURNING"):
            with self.subTest(phase=phase):
                pulses = []
                app = Dispenser(Config(mode="ratchet"), pulses.append,
                                lambda _: None)
                app.state = phase
                app.tick(0, 508, 510, button=0)
                app.tick(100, 1023, 510)
                self.assertEqual(app.state, "STOPPED")
                self.assertEqual(pulses, [])
                self.assertEqual(app.completed_cycles, 0)

    def test_bad_calibration_rejected(self):
        for kwargs in ({"step_ms": 0}, {"limit_ms": 3},
                       {"home_ms": 2, "limit_ms": 1},
                       {"step_ms": float("nan")}, {"channel": 16},
                       {"capacity": -1}, {"move_seconds": -1},
                       {"ramp_seconds": -1}, {"ramp_seconds": float("inf")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Config(**kwargs)

    def test_decimal_endpoints_allow_exact_stroke_without_exceeding_limit(self):
        config = Config(home_ms=1.3, step_ms=0.4, limit_ms=1.7,
                        gesture="push")
        self.app = Dispenser(config, self.pulses.append, lambda _: None)
        self.gesture()
        self.assertEqual(self.pulses, [1.7])
        self.assertEqual(self.app.state, "TRAVEL_LIMIT")
        with self.assertRaises(ValueError):
            Config(home_ms=1.3, step_ms=0.4001, limit_ms=1.7)

    def test_invalid_sensor_sample_rejected(self):
        with self.assertRaises(ValueError):
            self.app.tick(0, 65535, 510)
        self.assertEqual(self.pulses, [])

    def test_hardware_stop_and_read_failure_disable_pwm_without_rewind(self):
        for failure in (False, True):
            with self.subTest(read_failure=failure):
                joystick = Mock(connected=True)
                joystick.begin.return_value = True
                if failure:
                    type(joystick).button = PropertyMock(side_effect=OSError("I2C read"))
                else:
                    joystick.button = 0
                    # A stop should be handled before attempting either axis read.
                    type(joystick).horizontal = PropertyMock(side_effect=AssertionError)
                hat = Mock()
                hat.PCA9685.address = 0x40
                hat.PCA9685.set_channel_word.side_effect = lambda ch, on, value: 0 <= value <= 4095
                modules = {
                    "qwiic_joystick": SimpleNamespace(QwiicJoystick=lambda: joystick),
                    "pi_servo_hat": SimpleNamespace(PiServoHat=lambda **_: hat),
                }
                with patch.dict("sys.modules", modules), \
                     patch("builtins.input", return_value=""), \
                     patch("builtins.print"), patch("sugar_dispenser.time.sleep"):
                    if failure:
                        with self.assertRaises(OSError):
                            run_hardware(Config())
                    else:
                        run_hardware(Config())
                # Homing is the only positive pulse; no shutdown return stroke.
                hat.set_duty_cycle.assert_called_once_with(1, 5.0)
                self.assertEqual(hat.PCA9685.set_channel_word.call_args_list,
                                 [unittest.mock.call(1, 1, 0)])
                hat.PCA9685._i2c.writeWord.assert_called_once_with(0x40, 0x0C, 0x1000)


class CircleTests(unittest.TestCase):
    def setUp(self):
        self.pulses = []
        self.app = Dispenser(Config(mode="ratchet"), self.pulses.append,
                             lambda _: None)
        self.now = 0.0
        self.center(0.5)

    def center(self, seconds):
        for _ in range(round(seconds / 0.02)):
            self.app.tick(self.now, 508, 510)
            self.now += 0.02

    def arc(self, start, end, samples=121):
        for i in range(samples):
            angle = math.radians(start + (end - start) * i / (samples - 1))
            self.app.tick(self.now, 508 + round(400 * math.sin(angle)),
                          510 - round(400 * math.cos(angle)))
            self.now += 0.02

    def test_full_clockwise_circle_triggers_once(self):
        self.arc(0, 360)
        self.assertEqual(self.pulses, [2.0])
        self.center(2)
        self.assertEqual(self.app.completed_cycles, 1)

    def test_quarter_and_half_circle_do_not_trigger(self):
        self.arc(0, 90)
        self.arc(90, 180)
        self.assertEqual(self.pulses, [])

    def test_counterclockwise_circles_do_not_trigger(self):
        self.arc(0, -720, samples=241)
        self.assertEqual(self.pulses, [])

    def test_backtracking_cancels_forward_progress(self):
        for _ in range(5):
            self.arc(0, 180)
            self.arc(180, 0)
        self.assertEqual(self.pulses, [])

    def test_center_breaks_incomplete_circle(self):
        self.arc(0, 180)
        self.center(0.1)
        self.arc(180, 360)
        self.assertEqual(self.pulses, [])

    def test_holding_direction_does_not_repeat(self):
        self.arc(0, 360)
        for _ in range(500):
            self.app.tick(self.now, 508, 110)
            self.now += 0.02
        self.assertEqual(self.app.completed_cycles, 1)

    def test_jump_or_lost_sample_does_not_join_arcs(self):
        self.arc(0, 180)
        self.now += 1
        self.arc(180, 360)
        self.assertEqual(self.pulses, [])
        self.center(0.1)
        self.arc(0, 360, samples=5)
        self.assertEqual(self.pulses, [])

    def test_four_circles_reach_inventory_lockout(self):
        for _ in range(6):
            self.arc(0, 360)
            self.center(2)
        self.assertEqual(self.app.completed_cycles, 4)
        self.assertEqual(self.app.state, "EMPTY_ESTIMATE")

    def test_direct_mode_still_locks_at_travel_limit(self):
        self.app = Dispenser(Config(), self.pulses.append, lambda _: None)
        self.center(0.5)
        for _ in range(3):
            self.arc(0, 360)
            self.center(2)
        self.assertEqual(self.pulses, [2.0])
        self.assertEqual(self.app.state, "TRAVEL_LIMIT")

    def test_circle_while_busy_is_not_queued(self):
        self.arc(0, 360)
        self.arc(0, 360, samples=31)
        self.center(2)
        self.assertEqual(self.app.completed_cycles, 1)


class ContinuousTests(unittest.TestCase):
    center = CircleTests.center
    arc = CircleTests.arc

    def setUp(self):
        self.pulses = []
        self.reports = []
        self.now = 0.0
        self.config = Config(mode="ratchet", continuous=True, capacity=0,
                             home_ms=0.875, step_ms=1.25, limit_ms=2.125)
        self.app = Dispenser(self.config, self.pulses.append, self.reports.append)
        self.center(0.5)

    def test_more_than_four_circles_keep_working(self):
        for _ in range(7):
            self.arc(0, 360)
            self.center(2)
        self.assertEqual(self.app.completed_cycles, 7)
        self.assertEqual(self.app.state, "READY")
        self.assertEqual(self.pulses, [2.125, 0.875] * 7)

    def test_circles_during_motion_queue_and_run_exactly_once(self):
        for _ in range(5):
            self.arc(0, 360, samples=61)
        self.center(10)
        self.assertEqual(self.app.completed_cycles, 5)
        self.assertEqual(self.pulses, [2.125, 0.875] * 5)
        self.assertEqual(self.app.pending_cycles, 0)
        self.assertTrue(any(r.startswith("QUEUED") for r in self.reports))

    def test_stop_discards_pending_cycles(self):
        for _ in range(3):
            self.arc(0, 360, samples=31)
        self.assertGreater(self.app.pending_cycles, 0)
        self.app.tick(self.now, 508, 510, button=0)
        before = list(self.pulses)
        self.center(10)
        self.assertEqual(self.app.state, "STOPPED")
        self.assertEqual(self.app.pending_cycles, 0)
        self.assertEqual(self.pulses, before)

    def test_queue_is_bounded_and_overflow_is_reported(self):
        config = Config(mode="ratchet", continuous=True, capacity=0,
                        max_pending=2, move_seconds=10, drop_seconds=10)
        self.app = Dispenser(config, self.pulses.append, self.reports.append)
        self.center(0.5)
        for _ in range(8):
            self.arc(0, 360, samples=31)
        self.assertEqual(self.app.pending_cycles, 2)
        self.assertTrue(any(r.startswith("QUEUE FULL") for r in self.reports))
        self.center(100)
        self.assertEqual(self.app.completed_cycles, 3)

    def test_partial_arc_survives_servo_phase_changes(self):
        self.arc(0, 360)
        self.arc(0, 180, samples=31)
        self.arc(180, 360, samples=31)
        self.center(10)
        self.assertEqual(self.app.completed_cycles, 2)


class RingTests(unittest.TestCase):
    center = CircleTests.center
    arc = CircleTests.arc

    def setUp(self):
        self.pulses = []
        self.now = 0.0
        self.config = Config(mode="alternate", capacity=0, home_ms=0.5,
                             step_ms=1.9, limit_ms=2.4, ramp_seconds=3)
        self.app = Dispenser(self.config, self.pulses.append, lambda _: None)
        self.center(0.5)

    def test_first_circle_holds_far_endpoint_without_auto_return(self):
        self.arc(0, 360)
        self.center(6)
        self.assertAlmostEqual(self.pulses[-1], 2.4)
        self.assertEqual(self.app.completed_cycles, 1)
        self.assertEqual(self.app.state, "READY")
        before = list(self.pulses)
        self.center(10)
        self.assertEqual(self.pulses, before)

    def test_next_circle_reverses_to_start_without_wrapping(self):
        for _ in range(2):
            self.arc(0, 360)
            self.center(6)
        self.assertAlmostEqual(self.pulses[-1], 0.5)
        self.assertEqual(self.app.completed_cycles, 2)
        self.assertEqual(self.app.state, "READY")

    def test_ramp_is_gradual_bounded_and_monotonic(self):
        self.arc(0, 360)
        self.center(6)
        self.assertGreater(len(self.pulses), 100)
        self.assertTrue(all(0.5 <= p <= 2.4 for p in self.pulses))
        self.assertTrue(all(a <= b for a, b in zip(self.pulses, self.pulses[1:])))
        self.assertLess(max(b - a for a, b in zip(self.pulses, self.pulses[1:])), 0.02)

    def test_stop_mid_ramp_prevents_remaining_motion(self):
        self.arc(0, 360)
        self.center(0.5)
        self.assertEqual(self.app.state, "RAMPING")
        self.app.tick(self.now, 508, 510, button=0)
        before = list(self.pulses)
        self.center(10)
        self.assertEqual(self.pulses, before)
        self.assertEqual(self.app.completed_cycles, 0)

    def test_initial_ring_test_does_not_queue_busy_circles(self):
        self.arc(0, 360)
        self.arc(0, 360, samples=31)
        self.center(6)
        self.assertEqual(self.app.completed_cycles, 1)
        self.assertEqual(self.app.pending_cycles, 0)

    def test_ring_can_run_more_than_four_separate_requests(self):
        for _ in range(6):
            self.arc(0, 360)
            self.center(6)
        self.assertEqual(self.app.completed_cycles, 6)
        self.assertAlmostEqual(self.pulses[-1], 0.5)

    def test_cli_profile_selects_slow_alternating_motion(self):
        with patch("sys.argv", ["sugar_dispenser.py", "--ring-180"]), \
             patch("sugar_dispenser.simulate") as simulation:
            main()
        config = simulation.call_args.args[0]
        self.assertEqual(config.mode, "alternate")
        self.assertEqual((config.home_ms, config.step_ms, config.limit_ms), (0.5, 1.9, 2.4))
        self.assertEqual(config.capacity, 0)
        self.assertFalse(config.continuous)
        self.assertEqual(config.ramp_seconds, 3)


if __name__ == "__main__":
    unittest.main()
