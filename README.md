# Mewly

A cute pixel-art desktop cat that lives on your screen, reacts to your coding activity, and helps you stay productive with a built-in Pomodoro timer.

> Your tiny coding companion that silently watches you work... and judges your procrastination.

---

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
| Idle | Waiting for activity |
| Walk | Roaming around the screen |
| Sleep | Triggered after inactivity |
| Jump | Random reaction |
| Code | Active coding detected |
| Focus | High keyboard activity |
| Task | Task completed animation |
| Debug | Debug mode animation |
| Break | Break time animation |

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

No installation required.

---

## Assets

Place the sprite sheets inside the `assets/` folder:

```text
assets/
├── sprite_basic.png
└── sprite_coding.png
```

Mewly automatically loads and slices the sprites at startup.

---

## Controls

| Action | Result |
|---------|---------|
| Left Click | Random reaction |
| Double Click | Heart reaction |
| Right Click | Open context menu |
| Drag | Move Mewly anywhere |
| Start Pomodoro | Begin work session |
| Task Completed | Play task animation |
| Debug Mode | Play debug animation |
| Settings | Open settings |
| Exit | Save position and quit |

---

## Settings

Settings are stored automatically using SQLite.

Available options:

- Cat Size
- Animation FPS
- Always On Top
- Pomodoro Work Duration
- Pomodoro Break Duration

---

## Project Structure

```text
mewly/
├── main.py
├── animation_manager.py
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
- Pillow
- psutil
- pynput

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