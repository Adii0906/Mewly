# Mewly Behavior System

Mewly's behaviour is **deterministic**. There are no random timers, random
walks or random reactions. Every change on screen has a cause: your activity,
something you did to the cat, or a Pomodoro event.

## Layers

```
 ProductivityManager ──► ActivityClassifier ──► base state
 (input + IDE + Pomodoro)   (thresholds, grace,     IDLE / CODE / FOCUS / SLEEP / BREAK
                             hysteresis)                  │
                                                          ▼
 clicks, menu, Pomodoro ──► CatBehavior  (priority: one-shot > walk > base)
                                                          │ desired animation
                                                          ▼
                             AnimationPlayer (the ONLY thing that changes frames)
```

## Base states

| State | Cause | Animation |
|-------|-------|-----------|
| **IDLE**  | You're present (mouse/keyboard) but not typing in an IDE | `idle` loop |
| **CODE**  | ≥ 4 keystrokes within 6 s while VS Code / Cursor / Windsurf is the **foreground** window | `code` loop |
| **FOCUS** | In CODE for ≥ 45 s *and* ≥ 150 coding keystrokes in the last minute | `focus` loop |
| **SLEEP** | No keyboard **or** mouse input for *Sleep after* seconds (default 120, Settings) | `sleep` loop |
| **BREAK** | Pomodoro break phase | `break` loop |

```
            typing in IDE             sustained fast typing
   IDLE ─────────────────► CODE ─────────────────────────► FOCUS
    ▲  ◄──────────────────  │  ◄───────────────────────────  │
    │   20 s after the last │      < 70 keys/min              │
    │   coding keystroke    │                                 │
    │                       └──────────► IDLE ◄───────────────┘
    │  no input for "Sleep after"
    ▼
  SLEEP ── any input ──► WAKE (one-shot) ──► IDLE / CODE
```

### Anti-thrash rules
- **Grace period**: CODE/FOCUS continue for 20 s after the last coding
  keystroke, so pausing to think or glancing at a browser doesn't drop the cat
  to IDLE.
- **Entry threshold**: a single shortcut key doesn't start CODE (4 keys / 6 s).
- **Hysteresis**: FOCUS is entered at 150 keys/min and left below 70.
- **Minimum dwell**: IDLE ⇄ CODE ⇄ FOCUS changes wait until the current state
  has lasted at least 4 s.
- SLEEP, wake-up and Pomodoro changes are applied immediately (responsiveness).
- A state change only happens when the state really changes, and the
  animation player ignores requests for the animation that is already playing.

## One-shot reactions

One-shots play to completion and then the cat returns to whatever the base
state is **now** (activity changes during a reaction are not lost, they are
just not shown until it ends). A one-shot can only be interrupted by a
higher-priority one.

| Priority | One-shot | Cause |
|---|---|---|
| 5 | `task`  | "Task Done" (menu / tray) |
| 4 | `debug` | "Debug Mode" (menu / tray) |
| 3 | `wake`  | Leaving SLEEP (sleep → yawn/stretch → sit up) |
| 2 | `heart` | Double-click (with floating hearts) |
| 1 | `jump`  | Single click; Pomodoro work start / break end |

- A single click waits for the double-click interval, so a double-click shows
  only the heart reaction (never a jump first).
- Clicking a **sleeping** cat wakes it up (the wake animation is the reaction).
- Click texts cycle in a fixed order.

## Movement: automatic (default) and manual

The cat never wanders. Every move has a trigger.

### Automatic mode (default)

The monitor's work area is split into thirds: **left**, **center**, **right**.
The cat walks to the right third for the current activity, and only if it
isn't already there:

| Base state | Where the cat goes |
|---|---|
| CODE / FOCUS | Beside the active window, on the side with more free space. If the window fills the screen: right. (Windows only; elsewhere: right.) |
| IDLE | Center |
| BREAK | Center |
| SLEEP | Stays where it is |

Triggers (nothing else moves the cat automatically):
- a **base-state change** (e.g. IDLE → CODE, SLEEP → wake), and
- a **foreground-window switch** that stays active for 2.5 s
  (`WINDOW_SETTLE_MS`), so alt-tabbing through windows doesn't send the cat
  back and forth.

A left-button drag still moves the cat. In automatic mode, that spot is kept
until the next base-state change (window switches are ignored until then).

### Manual mode (right mouse button)

- **Right-drag** the cat to place it. This switches to manual mode and the cat
  stays exactly where you put it.
- **Right-click → 📍 Walk to… ▸ Left edge / Center / Right edge** walks there
  and switches to manual mode. The **← / →** keys work the same way.
- **Right-click → 🐾 Auto-move** toggles between automatic and manual mode.

Manual mode lasts until you turn Auto-move back on, or until the cat wakes up
after SLEEP (you were away), when automatic positioning resumes.

### Walking details

While walking, a click reaction pauses the walk; the walk resumes afterwards.
Dragging cancels a walk. The walk sprite faces the direction of travel. If you
drop the cat partly outside the monitor, it walks back in.

## Pomodoro

| Event | Result |
|---|---|
| Start | `jump` + "🍅 Focus time!" — the work phase is otherwise activity-driven |
| Work done | BREAK base state for the break duration |
| Break done | `jump` + "💪 Back to work!", back to activity-driven states |

## Activity detection

- **Windows**: `GetLastInputInfo` (system-wide keyboard + mouse idle time) and
  the foreground window's process name. Process names are compared exactly
  (`code`, `code - insiders`, `code-insiders`, `codium`, `vscodium`,
  `cursor`, `windsurf`).
- **Keyboard**: a `pynput` hook that only records timestamps; everything else
  happens on the Qt thread once per second. Keystroke statistics are written to
  SQLite in batches (every 30 s and on exit).
- **Other platforms**: mouse activity comes from cursor polling; the
  foreground app is unknown, so "an IDE is running" (checked every 30 s) is used.

## Animation timing

Frames advance on elapsed time, not timer ticks. The *Animation FPS* setting
scales every animation's authored speed (8 = as designed):

| Animation | FPS | Type |
|---|---|---|
| idle | 4 | loop |
| code | 5 | loop |
| focus | 6 | loop |
| sleep | 2 | loop |
| break | 0.8 | loop |
| walk | 8 | loop |
| jump | 8 | one-shot |
| heart | 3 | one-shot |
| task | 3 | one-shot, holds "DONE!" 1.2 s |
| debug | 4 | one-shot ×2 |
| wake | 4 | one-shot |

One timer drives the widget. It runs at ~60 Hz only while walking or while a
speech bubble or hearts fade; otherwise it sleeps until the next frame is due
(every 500 ms while asleep).

## Tuning

All thresholds live in `config.py` (`CODE_*`, `FOCUS_*`,
`MIN_STATE_DWELL_SECS`, `ANIMATIONS`, `ONESHOT_PRIORITY`). The sleep delay is
a user setting.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests cover the animation player (timing, no-restart, one-shot completion),
the classifier (thresholds, grace, hysteresis, dwell, sleep/wake) and the
priority rules, plus a simulated session through
IDLE → CODE → FOCUS → reaction → IDLE → SLEEP → WAKE → CODE → TASK → BREAK.
