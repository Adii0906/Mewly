# 🐱 CodingCat

A cute pixel-art desktop pet that lives on your Windows taskbar, reacts to your coding activity, and keeps you on-task with a built-in Pomodoro timer.

---

## Features

| Feature | Details |
|---|---|
| **Animated sprites** | 9 states: idle, walk, sleep, jump, code, focus, task, debug, break |
| **IDE detection** | Detects VS Code, Cursor, Windsurf → switches to CODE state |
| **Keyboard monitoring** | Typing speed adjusts state (idle → code → focus) |
| **Pomodoro timer** | 25/5-minute sessions with tray countdown |
| **Persistent settings** | Position, FPS, size stored in SQLite |
| **System tray** | Right-click menu with all controls |
| **Draggable** | Drag the cat anywhere on any monitor |

---

## Quick Start

### Option A — Run from source

```bash
# 1. Clone / unzip the project
cd coding-cat

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Generate tray icon from sprite sheet
python utils/icon_gen.py

# 4. Launch
python main.py
```

### Option B — Build CodingCat.exe

```bat
build.bat
```

The executable is output to `dist\CodingCat.exe`. Double-click to launch. No installation required.

---

## Asset Setup

The two sprite sheets must be present in the `assets/` folder:

```
assets/
  sprite_basic.png   ← Sheet 2 (IDLE, WALK, SLEEP, JUMP)
  sprite_coding.png  ← Sheet 1 (CODE, FOCUS, TASK, DEBUG, BREAK)
```

These are the images you provided (renamed). The app slices them automatically at startup — no manual frame extraction needed.

### Sprite Sheet Layout

**`sprite_coding.png`** (1535×1024) — 5-column grid, `col_w=307px`, skip column 0 (label):

| Row | Y | State | Frames |
|-----|---|-------|--------|
| 0 | 0–208 | CODE | 3 |
| 1 | 208–418 | FOCUS | 3 |
| 2 | 418–623 | TASK | 4 |
| 3 | 623–824 | DEBUG | 4 |
| 4 | 824–1024 | BREAK | 4 |

**`sprite_basic.png`** (1536×1024) — 6-column grid, `col_w=256px`, `row_h=256px`, skip column 0:

| Row | Y | State | Frames |
|-----|---|-------|--------|
| 0 | 0 | IDLE | 4 |
| 1 | 256 | WALK | 4 |
| 2 | 512 | SLEEP | 4 |
| 3 | 768 | JUMP | 4 |

---

## Controls

| Action | Result |
|--------|--------|
| **Left-click** cat | Random reaction + brief jump |
| **Double-click** cat | Heart reaction |
| **Right-click** cat | Context menu |
| **Drag** cat | Move to any position |
| **Tray → Start Pomodoro** | Begin 25-min work session |
| **Tray → Task Completed** | Play TASK celebration animation |
| **Tray → Debug Mode** | Play DEBUG animation |
| **Tray → Settings** | Open settings dialog |
| **Tray → Exit** | Quit and save position |

---

## Settings

Stored in `~/.coding_cat/coding_cat.db` (SQLite):

- **Cat Size** — 60–240 px
- **FPS** — 4–24 frames per second
- **Always on top** — toggle
- **Pomodoro Work** — 1–90 minutes
- **Pomodoro Break** — 1–30 minutes

---

## API / Integration

```python
# From another script or terminal
import subprocess, json

# Trigger task completed (via tray or direct call)
# If running main.py directly:
from main import CodingCatApp
app.trigger_task_completed()
app.trigger_debug_mode()
```

---

## Project Structure

```
coding-cat/
├── main.py                  ← Entry point & app controller
├── config.py                ← Constants & sprite layout config
├── cat_widget.py            ← PyQt6 transparent window + animation loop
├── animation_manager.py     ← Sprite sheet slicing & frame management
├── state_manager.py         ← Finite-state machine
├── movement_manager.py      ← Random roaming & screen-edge detection
├── productivity_manager.py  ← Keyboard monitor, IDE detect, Pomodoro
├── tray_manager.py          ← System tray icon & menu
├── settings_manager.py      ← Load/save settings
├── settings_dialog.py       ← Settings UI dialog
├── storage.py               ← SQLite helpers
├── utils/
│   ├── __init__.py
│   └── icon_gen.py          ← Auto-generate .ico from sprite
├── assets/
│   ├── sprite_basic.png
│   ├── sprite_coding.png
│   └── icon.ico             ← Auto-generated on first run
├── requirements.txt
├── coding_cat.spec          ← PyInstaller config
├── build.bat                ← One-click build script
└── README.md
```

---

## Requirements

- Python 3.12+
- Windows 10/11 (tested)
- `PyQt6`, `Pillow`, `psutil`, `pynput`

---

## Performance

- CPU: ~0.5–2% typical (Qt rendering + polling)
- RAM: ~50–80 MB
- The animation timer is paused when the window is hidden
