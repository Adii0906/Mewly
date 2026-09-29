"""
Deterministic tests for Mewly's Qt-free core:
AnimationPlayer, ActivityClassifier and CatBehavior.

Run:  python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from animation_controller import AnimationPlayer                       # noqa: E402
from config import (                                                   # noqa: E402
    ANIMATIONS, AnimSpec, CODE_GRACE_SECS, FOCUS_MIN_CODE_SECS, MIN_STATE_DWELL_SECS,
)
from state_manager import ActivityClassifier, ActivitySample, CatBehavior, CatState  # noqa: E402
from positioning import CENTER, LEFT, RIGHT, target_zone, zone_of, zone_target  # noqa: E402


class AnimationPlayerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.anims = {
            "loop": AnimSpec((("a", 0), ("a", 1), ("a", 2)), fps=4),
            "once": AnimSpec((("b", 0), ("b", 1)), fps=10, loop=False, hold_ms=300),
            "twice": AnimSpec((("c", 0), ("c", 1)), fps=10, loop=False, repeat=2),
        }
        self.p = AnimationPlayer(self.anims)

    def test_same_animation_is_not_restarted(self) -> None:
        self.p.play("loop", 0)
        self.p.update(260)
        self.assertEqual(self.p.frame, ("a", 1))
        self.assertFalse(self.p.play("loop", 300))
        self.assertEqual(self.p.frame, ("a", 1))

    def test_loop_timing_is_time_based(self) -> None:
        self.p.play("loop", 0)
        seen = []
        for t in range(0, 1501, 50):          # tick rate is irrelevant
            self.p.update(t)
            seen.append(self.p.frame[1])
        # 4 fps → a frame every 250 ms, wrapping after 3 frames.
        self.assertEqual(seen[0], 0)
        self.assertEqual(seen[5], 1)          # t=250
        self.assertEqual(seen[10], 2)         # t=500
        self.assertEqual(seen[15], 0)         # t=750 wraps

    def test_oneshot_holds_then_finishes_exactly_once(self) -> None:
        self.p.play("once", 0)
        self.assertEqual(self.p.update(100), (True, None))    # frame 1 at 100 ms
        self.assertEqual(self.p.update(499), (False, None))   # last frame: 100 ms + 300 ms hold
        self.assertEqual(self.p.update(501), (False, "once"))
        self.assertEqual(self.p.update(900), (False, None))   # no second report
        self.assertEqual(self.p.frame, ("b", 1))

    def test_repeat(self) -> None:
        self.p.play("twice", 0)
        frames = []
        t = 0
        while True:
            t += 10
            _, done = self.p.update(t)
            frames.append(self.p.frame[1])
            if done:
                break
        self.assertAlmostEqual(t, 400, delta=10)  # 4 steps x 100 ms
        self.assertEqual(sorted(set(frames)), [0, 1])

    def test_stall_does_not_fast_forward(self) -> None:
        self.p.play("loop", 0)
        self.p.update(60_000)                 # machine slept for a minute
        self.p.update(60_010)
        self.assertLess(self.p.ms_until_next(60_010), 251)

    def test_real_animation_table_is_consistent(self) -> None:
        import json
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "assets", "sprites", "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)["animations"]
        for name, spec in ANIMATIONS.items():
            for strip, idx in spec.frames:
                self.assertIn(strip, manifest, name)
                self.assertLess(idx, manifest[strip]["frames"], name)


class ClassifierTest(unittest.TestCase):
    def sample(self, now, idle=0.0, keys=(), on_break=False):
        return ActivitySample(now=now, idle_secs=idle, coding_key_times=list(keys), on_break=on_break)

    def test_single_keystroke_does_not_start_coding(self) -> None:
        c = ActivityClassifier(120)
        self.assertEqual(c.update(self.sample(10, keys=[9.5])), CatState.IDLE)

    def test_idle_to_code_to_idle_with_grace(self) -> None:
        c = ActivityClassifier(120)
        keys = [9.0, 9.3, 9.6, 9.9]
        self.assertEqual(c.update(self.sample(10, keys=keys)), CatState.CODE)
        # A pause shorter than the grace period keeps CODE (no thrashing).
        self.assertEqual(c.update(self.sample(10 + CODE_GRACE_SECS - 1, idle=5, keys=keys)), CatState.CODE)
        self.assertEqual(c.update(self.sample(10 + CODE_GRACE_SECS + 1, idle=5, keys=keys)), CatState.IDLE)

    def test_minimum_dwell_prevents_flip_flop(self) -> None:
        c = ActivityClassifier(120)
        c.update(self.sample(10, keys=[9.0, 9.3, 9.6, 9.9]))
        # Right after entering CODE, even a (hypothetical) idle target must wait.
        self.assertEqual(c.update(self.sample(10 + MIN_STATE_DWELL_SECS / 2, keys=[])), CatState.CODE)

    def test_focus_requires_sustained_fast_typing_and_has_hysteresis(self) -> None:
        c = ActivityClassifier(600)
        t0 = 100.0
        keys = [t0 - 1 + i * 0.01 for i in range(5)]
        c.update(self.sample(t0, keys=keys))
        self.assertEqual(c.state, CatState.CODE)
        # 4 keys/s for a long time → FOCUS only after FOCUS_MIN_CODE_SECS.
        t = t0
        states = []
        while t < t0 + FOCUS_MIN_CODE_SECS + 5:
            t += 1
            keys = [k for k in keys if k >= t - 60] + [t - 0.75, t - 0.5, t - 0.25, t]
            states.append((t, c.update(self.sample(t, keys=keys))))
        first_focus = next(tt for tt, s in states if s == CatState.FOCUS)
        self.assertGreaterEqual(first_focus - t0, FOCUS_MIN_CODE_SECS)
        # Slow down to ~100 kpm: above the exit threshold → stays FOCUS.
        for _ in range(60):
            t += 1
            keys = [k for k in keys if k >= t - 60] + [t - 0.4, t]
        c.update(self.sample(t, keys=[k for k in keys if k >= t - 60]))
        self.assertEqual(c.state, CatState.FOCUS)

    def test_sleep_and_immediate_wake(self) -> None:
        c = ActivityClassifier(60)
        self.assertEqual(c.update(self.sample(100, idle=60)), CatState.SLEEP)
        # Any input wakes immediately (no dwell for SLEEP transitions).
        self.assertEqual(c.update(self.sample(100.5, idle=0)), CatState.IDLE)

    def test_break_overrides_everything(self) -> None:
        c = ActivityClassifier(60)
        self.assertEqual(c.update(self.sample(10, idle=999, on_break=True)), CatState.BREAK)
        self.assertEqual(c.update(self.sample(11, idle=999)), CatState.SLEEP)


class BehaviorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.shown = []
        self.b = CatBehavior(self.shown.append)

    def test_waking_plays_wake_then_new_state(self) -> None:
        self.b.set_base(CatState.SLEEP)
        self.b.set_base(CatState.CODE)
        self.assertEqual(self.b.animation(), "wake")
        self.b.oneshot_finished("wake")
        self.assertEqual(self.shown, ["sleep", "wake", "code"])

    def test_oneshot_is_not_overwritten_by_activity(self) -> None:
        self.b.trigger("task")
        self.b.set_base(CatState.CODE)
        self.b.set_base(CatState.FOCUS)
        self.assertEqual(self.b.animation(), "task")
        self.b.oneshot_finished("task")
        self.assertEqual(self.b.animation(), "focus")
        self.assertEqual(self.shown, ["task", "focus"])

    def test_priority(self) -> None:
        self.assertTrue(self.b.trigger("jump"))
        self.assertFalse(self.b.trigger("jump"))     # spam-click: first one finishes
        self.assertTrue(self.b.trigger("task"))      # higher priority replaces
        self.assertFalse(self.b.trigger("heart"))
        self.b.oneshot_finished("jump")              # stale completion ignored
        self.assertEqual(self.b.animation(), "task")

    def test_walk_reaction_walk(self) -> None:
        self.b.set_walking(True)
        self.assertEqual(self.b.animation(), "walk")
        self.b.trigger("jump")
        self.assertTrue(self.b.movement_paused)
        self.b.oneshot_finished("jump")
        self.assertEqual(self.b.animation(), "walk")
        self.b.set_walking(False)
        self.assertEqual(self.shown, ["walk", "jump", "walk", "idle"])


class PositioningTest(unittest.TestCase):
    WORK = (0, 0, 1920, 1040)

    def test_zones_are_thirds(self) -> None:
        self.assertEqual(zone_of(0, 0, 900), LEFT)
        self.assertEqual(zone_of(450, 0, 900), CENTER)
        self.assertEqual(zone_of(900, 0, 900), RIGHT)
        self.assertEqual(zone_target(CENTER, 100, 900), 500)

    def test_state_targets(self) -> None:
        self.assertIsNone(target_zone(CatState.SLEEP, None, None))      # sleeping: stay put
        self.assertEqual(target_zone(CatState.IDLE, None, None), CENTER)
        self.assertEqual(target_zone(CatState.BREAK, None, None), CENTER)
        self.assertEqual(target_zone(CatState.CODE, None, None), RIGHT)  # no window info

    def test_code_sits_beside_the_active_window(self) -> None:
        # Editor docked on the left half → free space on the right.
        self.assertEqual(target_zone(CatState.CODE, (0, 0, 960, 1040), self.WORK), RIGHT)
        # Editor docked on the right half → free space on the left.
        self.assertEqual(target_zone(CatState.FOCUS, (960, 0, 1920, 1040), self.WORK), LEFT)
        # Maximized editor → no room anywhere → right corner.
        self.assertEqual(target_zone(CatState.CODE, (0, 0, 1920, 1040), self.WORK), RIGHT)
        # Window on another monitor → default.
        self.assertEqual(target_zone(CatState.CODE, (2000, 0, 3000, 900), self.WORK), RIGHT)

    def test_movement_keywords(self) -> None:
        editor_left = (0, 0, 960, 1040)
        # Defaults = the built-in behaviour.
        self.assertEqual(target_zone(CatState.CODE, editor_left, self.WORK, {}), RIGHT)
        self.assertEqual(target_zone(CatState.IDLE, None, None, {}), CENTER)
        # Custom keywords per activity.
        prefs = {"code": "left", "idle": "right", "break": "stay"}
        self.assertEqual(target_zone(CatState.FOCUS, editor_left, self.WORK, prefs), LEFT)
        self.assertEqual(target_zone(CatState.IDLE, None, None, prefs), RIGHT)
        self.assertIsNone(target_zone(CatState.BREAK, None, None, prefs))
        self.assertIsNone(target_zone(CatState.SLEEP, None, None, prefs))   # sleep always stays
        # Unknown / invalid keywords fall back to the default.
        self.assertEqual(target_zone(CatState.IDLE, None, None, {"idle": "beside"}), CENTER)
        self.assertEqual(target_zone(CatState.IDLE, None, None, {"idle": "bogus"}), CENTER)

    def test_deterministic(self) -> None:
        results = {target_zone(CatState.FOCUS, (700, 0, 1920, 1040), self.WORK) for _ in range(50)}
        self.assertEqual(results, {LEFT})


class ScenarioTest(unittest.TestCase):
    """End-to-end simulation of the QA transition list at 1 s activity polls
    and a 16 ms render loop, driving the real animation table."""

    def test_full_day(self) -> None:
        clf = ActivityClassifier(sleep_after_secs=60)
        requests = []
        player = AnimationPlayer()
        now_ms = [0.0]

        def on_change(name):
            requests.append(name)
            player.play(name, now_ms[0])

        beh = CatBehavior(on_change)
        player.play(beh.animation(), 0)
        restarts = []
        orig_play = player.play

        def spy(name, t, restart=False):
            changed = orig_play(name, t, restart)
            if changed:
                restarts.append((round(t / 1000), name))
            return changed
        player.play = spy

        last_input = 0.0
        keys = []

        def run(seconds, typing_rate=0.0, on_break=False):
            nonlocal last_input
            end = now_ms[0] + seconds * 1000
            next_poll = now_ms[0]
            acc = 0.0
            while now_ms[0] < end:
                now_ms[0] += 16
                t = now_ms[0] / 1000
                acc += typing_rate * 0.016
                while acc >= 1:
                    acc -= 1
                    keys.append(t)
                    last_input = t
                _, done = player.update(now_ms[0])
                if done:
                    beh.oneshot_finished(done)
                if now_ms[0] >= next_poll:
                    next_poll += 1000
                    recent = [k for k in keys if k >= t - 60]
                    beh.set_base(clf.update(ActivitySample(t, t - last_input, recent, on_break)))

        run(5)                                   # user present, not coding
        self.assertEqual(beh.animation(), "idle")
        run(30, typing_rate=2)                   # IDLE → CODE
        self.assertEqual(beh.animation(), "code")
        run(60, typing_rate=4)                   # CODE → FOCUS
        self.assertEqual(beh.animation(), "focus")
        beh.trigger("jump")                      # click during FOCUS
        run(0.3, typing_rate=4)
        self.assertEqual(beh.animation(), "jump")
        run(2, typing_rate=4)
        self.assertEqual(beh.animation(), "focus")
        run(40)                                  # stop typing: FOCUS → IDLE
        self.assertEqual(beh.animation(), "idle")
        run(40)                                  # long inactivity → SLEEP
        self.assertEqual(beh.animation(), "sleep")
        last_input = now_ms[0] / 1000            # user comes back
        run(0.5, typing_rate=3)
        self.assertEqual(beh.animation(), "wake")
        run(5, typing_rate=3)
        self.assertIn(beh.animation(), ("idle", "code"))
        run(10, typing_rate=3)
        self.assertEqual(beh.animation(), "code")
        beh.trigger("task")                      # TASK → normal state
        run(4, typing_rate=3)
        self.assertEqual(beh.animation(), "code")
        run(3, typing_rate=3, on_break=True)     # Pomodoro break
        self.assertEqual(beh.animation(), "break")

        # Each state change requested the new animation exactly once —
        # nothing restarted on every tick.
        self.assertEqual(len(requests), len(restarts))
        for a, b in zip(requests, requests[1:]):
            self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
