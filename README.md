# Mewly

A cute pixel-art desktop cat that lives on your screen, reacts to your coding activity, and helps you stay productive with a built-in Pomodoro timer.

> Your tiny coding companion that silently watches you work... and judges your procrastination.

---

## 🐈‍⬛ Download Mewly

**Windows:** [Download Mewly v1.0.0](https://github.com/Adii0906/Mewly/releases/download/v1.0.0/Mewly.exe)

Download the `.exe`, run it, and Mewly will appear on your desktop. No Python or additional setup required.

## Overview

Mewly is a lightweight desktop pet for Windows that sits on your screen, reacts to your activity, and changes its behavior based on what you're doing.

Whether you're coding, debugging, taking a break, or away from your keyboard, Mewly keeps you company throughout the day.

---

## Features

- Multiple pixel-art animations
- Activity-based state changes
- IDE detection (VS Code, Cursor, Windsurf)
- Keyboard activity monitoring
- Built-in Pomodoro timer
- System tray controls
- Draggable desktop pet
- Persistent settings using SQLite
- Multi-monitor support

---

## States

| State | Description |
|---------|-------------|
| Idle | You're around but not coding |
| Code | Typing in VS Code / Cursor / Windsurf (foreground) |
| Focus | Sustained fast typing in the IDE |
| Sleep | No keyboard/mouse input for a while (configurable) |
| Wake | Plays when you come back |
| Walk | Auto-positioning on activity changes, or when you ask — never random |
| Jump / Heart | Click / double-click reactions |
| Task / Debug | Menu or tray actions |
| Break | Pomodoro break |

Behaviour is fully deterministic — see [BEHAVIOR_SYSTEM.md](BEHAVIOR_SYSTEM.md).

---

## Quick Start

### Run from Source

```bash
git clone <repo-url>
cd mewly

pip install -r requirements.txt

python main.py
```

### Build Executable

```bat
build.bat
```

Output:

```text
dist/
└── Mewly.exe
```

`Mewly.exe` is a single self-contained 64-bit file: Python, PyQt6/Qt, the
Microsoft C++ runtime and all assets are inside. Users just download and run
it; there's nothing to install and no environment setup.

What `build.bat` does (needs 64-bit Python 3.10+ from python.org on the
build PC only):

1. Deletes old `build/`, `dist/` and the previous build environment.
2. Creates a fresh `.build-venv` and installs `requirements-build.txt` into it,
   with a PATH that contains only Windows (so no stray DLLs from the developer
   machine can end up in the exe).
3. Checks the environment (`tools/check_build_env.py`): 64-bit, matching
   PyQt6 / PyQt6-Qt6 versions, no second Qt binding, no conda Python.
4. Builds from `Mewly.spec`. The spec ships one consistent, newest copy of the
   MSVC runtime DLLs (`tools/pyinstaller/msvc_runtime.py`), and a runtime hook
   (`tools/pyinstaller/rthook_mewly.py`) makes the exe use only its bundled
   DLLs.
5. Runs `dist\Mewly.exe --self-test` with a bare Windows PATH and fails the
   build if Qt, the platform plugin, sprites, tray icon or activity monitoring
   don't load.

Use `build.bat /norun` for scripted/CI builds.

---

## Assets

```text
assets/
├── source/            original sprite sheets (JPEG, black background)
│   ├── sprite_basic.jpg
│   └── sprite_coding.jpg
├── sprites/           generated: one transparent strip per animation + manifest.json
└── icon.ico
```

The app only loads `assets/sprites/`. Those strips are generated once from the
source sheets by `tools/build_sprites.py`, which keys out the background,
detects each frame (even frames that touch), and places every frame on one
shared canvas with the feet on a common ground line, so the cat never jumps
or shakes when frames change. Re-run it after editing the source sheets:

```bash
python tools/build_sprites.py
```

---

## Controls

| Action | Result |
|---------|---------|
| Left Click | Jump + meow (wakes a sleeping cat) |
| Double Click | Heart reaction |
| Right Click | Open context menu |
| Right Drag | Place Mewly yourself (manual mode: it stays there) |
| Drag | Move Mewly anywhere (dropped half off-screen → walks back) |
| ← / → | Walk left / right (click the cat first; manual mode) |
| Walk to… | Walk to the left edge, center or right edge (manual mode) |
| Auto-move | Toggle automatic positioning (on by default) |
| Start Pomodoro | Begin work session |
| Task Completed | Play task animation |
| Debug Mode | Play debug animation |
| Settings | Open settings |
| How Mewly works | Show the introduction window again |
| Esc | Close Mewly (click the cat first) |
| Exit | Save position and quit |

By default Mewly positions itself based on what you're doing: beside your
editor while you code, in the center when you're idle or on a break, and it
stays put while it takes a break. If you're away for 10 seconds, Mewly takes a
little break too (break animation, movement pauses) and wakes up as soon as
you use your computer again. See [BEHAVIOR_SYSTEM.md](BEHAVIOR_SYSTEM.md).

On first launch a small introduction window explains the basics. Tick
**Don't show this again** to skip it on future launches. You can reopen it
any time from the right-click menu (**❔ How Mewly works**).

---

## Settings

Settings are stored automatically using SQLite.

Available options:

- Cat Size (sprite height in pixels)
- Animation FPS (overall speed; 8 = as designed)
- Always On Top
- Break After (seconds of inactivity before Mewly takes a break; default 10)
- Animation: pick any of Mewly's animations (jump, heart, task done, debug,
  wake up) and play it on the cat
- Movement: Automatic Movement on/off (default on, remembered), and a movement keyword per activity
  (coding: beside my window / left / center / right / stay; idle and break:
  center / left / right / stay)
- Pomodoro Work Duration
- Pomodoro Break Duration

---

## Project Structure

```text
mewly/
├── main.py
├── animation_controller.py   # the single animation authority (frame timing)
├── animation_manager.py      # sprite loading + scaled pixmap cache
├── cat_widget.py
├── config.py
├── movement_manager.py
├── productivity_manager.py
├── settings_manager.py
├── settings_dialog.py
├── state_manager.py
├── storage.py
├── tray_manager.py
├── assets/
├── tests/
├── tools/                    # offline sprite builder
├── utils/
├── requirements.txt
└── README.md
```

---

## Requirements

- Python 3.12+
- Windows 10/11

Dependencies:

- PyQt6
- psutil
- pynput
- Pillow (build-time only: icon generation / sprite builder)

Install them using:

```bash
pip install -r requirements.txt
```

---

## Performance

Typical usage:

- CPU: ~0.5–2%
- RAM: ~50–80 MB

Designed to run quietly in the background without impacting your workflow.

---

## Why Mewly?

Coding alone can get boring.

Mewly sits on your desktop, sleeps when you're inactive, reacts when you're coding, celebrates completed tasks, and reminds you to take breaks.

A simple desktop companion built for developers.

---

Made with Python and a lot of cat animations.
