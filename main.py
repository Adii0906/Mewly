"""
Mewly - Main Entry Point

Wires the subsystems together:

    ProductivityManager ──state_changed──▶ CatBehavior.set_base
    (activity + Pomodoro)                    │ (priority: one-shot > walk > base)
                                             ▼ on_change(anim)
    CatWidget ◀──────────────────────── AnimationPlayer.play  (single authority)
"""
from __future__ import annotations

import logging
import os
import sys

# ── Logging (~/.coding_cat/cat.log + console).  MEWLY_DEBUG=1 for verbose. ──
_LOG_DIR = os.path.join(os.path.expanduser("~"), ".coding_cat")
os.makedirs(_LOG_DIR, exist_ok=True)
_handlers: list[logging.Handler] = [
    logging.FileHandler(os.path.join(_LOG_DIR, "cat.log"), encoding="utf-8"),
]
if sys.stdout is not None:        # a windowed (no-console) .exe has no stdout
    _handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(
    level=logging.DEBUG if os.getenv("MEWLY_DEBUG") else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_handlers,
)
log = logging.getLogger("Mewly.main")


def _fatal(title: str, message: str) -> None:
    """Report a startup failure without needing Qt (it may be what failed)."""
    log.critical("%s: %s", title, message)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)  # MB_ICONERROR
        except Exception:
            pass
    elif sys.stderr is not None:
        print(f"{title}: {message}", file=sys.stderr)


try:
    from PyQt6.QtCore import QPoint, QTimer          # noqa: E402
    from PyQt6.QtGui import QGuiApplication           # noqa: E402
    from PyQt6.QtWidgets import QApplication, QMenu   # noqa: E402
except ImportError as _exc:
    _fatal(
        "Mewly could not start",
        "The Qt libraries failed to load:\n\n"
        f"{_exc}\n\n"
        "If you are running from source, reinstall the dependencies in a clean "
        "virtual environment:  pip install -r requirements.txt\n"
        "If you are running Mewly.exe, please re-download it (the file may be "
        "incomplete) and report this message.\n\n"
        f"Log: {os.path.join(_LOG_DIR, 'cat.log')}",
    )
    raise SystemExit(1)

from animation_manager import AnimationManager    # noqa: E402
from cat_widget import CatWidget                  # noqa: E402
from config import APP_NAME, APP_VERSION, AUTOSAVE_MS, EDGE_MARGIN  # noqa: E402
from movement_manager import MovementManager      # noqa: E402
from productivity_manager import ProductivityManager  # noqa: E402
from settings_dialog import SettingsDialog        # noqa: E402
from settings_manager import SettingsManager      # noqa: E402
from state_manager import CatBehavior, CatState   # noqa: E402
from storage import init_db                       # noqa: E402
from tray_manager import TrayManager              # noqa: E402

_MENU_STYLE = """
    QMenu { background:#1e1e2e; color:#cdd6f4; border:1px solid #313244;
            border-radius:6px; padding:4px; }
    QMenu::item { padding:5px 20px 5px 10px; border-radius:4px; }
    QMenu::item:selected { background:#313244; }
    QMenu::item:disabled { color:#6c7086; }
    QMenu::separator { background:#313244; height:1px; margin:4px 8px; }
"""


class CodingCatApp:
    """Top-level controller.  Owns exactly ONE CatWidget."""

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._quitting = False
        init_db()
        log.info("%s %s starting up", APP_NAME, APP_VERSION)

        self._settings_mgr = SettingsManager()
        cfg = self._settings_mgr.settings
        log.info("Settings: pos=(%d,%d) fps=%d size=%d sleep_after=%ds",
                 cfg.pos_x, cfg.pos_y, cfg.fps, cfg.display_size, cfg.sleep_after_secs)

        # ── core subsystems ───────────────────────────────────────
        self._anim_mgr = AnimationManager(display_size=cfg.display_size)
        self._move_mgr = MovementManager()
        self._behavior = CatBehavior()
        self._prod_mgr = ProductivityManager(sleep_after_secs=cfg.sleep_after_secs)
        self._prod_mgr.set_pomodoro_times(cfg.pomodoro_work_mins, cfg.pomodoro_break_mins)

        self._cat = CatWidget(
            anim_manager=self._anim_mgr,
            behavior=self._behavior,
            movement_manager=self._move_mgr,
            display_size=cfg.display_size,
            fps=cfg.fps,
        )
        self._behavior.set_listener(self._cat.on_animation_changed)
        self._cat.right_clicked.connect(self._show_context_menu)
        self._cat.exit_requested.connect(self._quit)
        self._cat.user_interacted.connect(self._prod_mgr.note_user_input)

        # Restore position BEFORE show(), validated against current monitors.
        x, y = self._restore_position(cfg.pos_x, cfg.pos_y)
        self._cat.move_to(x, y)
        self._cat.set_always_on_top(cfg.always_on_top)
        self._cat.show()
        self._cat.show_reaction("Hi! Right-click me")
        log.info("Cat window shown at (%d, %d)", x, y)

        # ── tray ──────────────────────────────────────────────────
        self._tray = TrayManager(
            on_exit=self._quit,
            on_toggle_visibility=self._toggle_visibility,
            on_start_pomodoro=self._start_pomodoro,
            on_stop_pomodoro=self._stop_pomodoro,
            on_open_settings=self._open_settings,
            on_trigger_task=self.trigger_task_completed,
            on_trigger_debug=self.trigger_debug_mode,
        )

        # ── activity → behaviour ─────────────────────────────────
        self._prod_mgr.state_changed.connect(self._on_activity_state)
        self._prod_mgr.pomodoro_tick.connect(self._on_pomodoro_tick)
        self._prod_mgr.pomodoro_event.connect(self._on_pomodoro_event)

        # ── autosave & shutdown ──────────────────────────────────
        self._save_timer = QTimer()
        self._save_timer.timeout.connect(self._autosave)
        self._save_timer.start(AUTOSAVE_MS)
        app.aboutToQuit.connect(self._shutdown)

    # ── public trigger API ───────────────────────────────────────

    def trigger_task_completed(self) -> None:
        if self._behavior.trigger("task"):
            self._cat.show_reaction("✅ Done!")
        self._tray.notify(APP_NAME, "Task completed! 🎉")

    def trigger_debug_mode(self) -> None:
        if self._behavior.trigger("debug"):
            self._cat.show_reaction("🐛 Debug!")

    # ── callbacks ─────────────────────────────────────────────────

    def _on_activity_state(self, state: CatState) -> None:
        self._behavior.set_base(state)

    def _on_pomodoro_tick(self, remaining: int, _total: int, phase: str) -> None:
        self._tray.update_pomodoro_label(remaining, phase)

    def _on_pomodoro_event(self, kind: str) -> None:
        if kind == "work_started":
            self._behavior.trigger("jump")
            self._cat.show_reaction("🍅 Focus time!")
            self._tray.notify(f"{APP_NAME} 🍅", "Pomodoro started!")
        elif kind == "work_done":
            # The BREAK base state follows from the classifier on this same poll.
            self._cat.show_reaction("☕ Break time!")
            self._tray.notify(f"{APP_NAME} 🍅", "Pomodoro done! Take a break ☕")
        elif kind == "break_done":
            self._behavior.trigger("jump")
            self._cat.show_reaction("💪 Back to work!")
            self._tray.notify(f"{APP_NAME} 🍅", "Break over! Back to work 💪")
        elif kind == "stopped":
            self._cat.show_reaction("⏹ Stopped")
            self._tray.update_pomodoro_label(None, "")

    def _show_context_menu(self, pos: QPoint) -> None:
        menu = QMenu()
        menu.setStyleSheet(_MENU_STYLE)
        menu.addAction("✅ Task Done", self.trigger_task_completed)
        menu.addAction("🐛 Debug Mode", self.trigger_debug_mode)
        menu.addSeparator()
        walk = menu.addMenu("🐾 Walk to…")
        walk.setStyleSheet(_MENU_STYLE)
        walk.addAction("◀ Left edge", lambda: self._cat.walk_to_edge("left"))
        walk.addAction("● Center", lambda: self._cat.walk_to_edge("center"))
        walk.addAction("▶ Right edge", lambda: self._cat.walk_to_edge("right"))
        menu.addSeparator()
        if self._prod_mgr.pomodoro_running:
            menu.addAction("⏹ Stop Pomodoro", self._stop_pomodoro)
        else:
            menu.addAction("▶ Start Pomodoro", self._start_pomodoro)
        menu.addSeparator()
        menu.addAction("⚙  Settings", self._open_settings)
        menu.addSeparator()
        menu.addAction("✖  Exit", self._quit)
        menu.exec(pos)

    def _toggle_visibility(self) -> None:
        if self._cat.isVisible():
            self._cat.hide()
        else:
            self._cat.show()

    def _start_pomodoro(self) -> None:
        self._prod_mgr.start_pomodoro()

    def _stop_pomodoro(self) -> None:
        self._prod_mgr.stop_pomodoro()

    def _open_settings(self) -> None:
        cfg = self._settings_mgr.settings
        dlg = SettingsDialog(cfg)
        if dlg.exec():
            self._settings_mgr.save()
            self._cat.set_fps(cfg.fps)
            self._cat.set_display_size(cfg.display_size)
            self._cat.set_always_on_top(cfg.always_on_top)
            self._prod_mgr.set_pomodoro_times(cfg.pomodoro_work_mins, cfg.pomodoro_break_mins)
            self._prod_mgr.set_sleep_after(cfg.sleep_after_secs)
            log.info("Settings applied")

    def _restore_position(self, x: int, y: int) -> tuple[int, int]:
        """Use the saved position if it is still on a monitor, else bottom-right of primary."""
        w, h = self._cat.width(), self._cat.height()
        if QGuiApplication.screenAt(QPoint(x + w // 2, y + h // 2)) is not None:
            return x, y
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        log.info("Saved position (%d,%d) is off-screen — resetting", x, y)
        return geo.right() - w - 40, geo.bottom() + 1 - h - EDGE_MARGIN

    def _autosave(self) -> None:
        cfg = self._settings_mgr.settings
        pos = (self._cat.x(), self._cat.y())
        if pos != (cfg.pos_x, cfg.pos_y):
            cfg.pos_x, cfg.pos_y = pos
            self._settings_mgr.save()
            log.debug("Position autosaved (%d, %d)", *pos)

    def _quit(self) -> None:
        QApplication.quit()

    def _shutdown(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        log.info("Shutting down — saving state")
        self._save_timer.stop()
        self._autosave()
        self._prod_mgr.shutdown()
        self._tray.hide()


def self_test(report_path: str | None) -> int:
    """Headless check used by build.bat on the packaged .exe.

    Loads the real Qt platform plugin, all sprites and every runtime
    dependency, without showing a window or touching the user's settings.
    Returns the process exit code (0 = OK).
    """
    lines: list[str] = []
    ok = True

    def check(name: str, fn) -> None:
        nonlocal ok
        try:
            detail = fn()
            lines.append(f"OK    {name}" + (f"  ({detail})" if detail else ""))
        except Exception as exc:          # report every failure, keep going
            ok = False
            lines.append(f"FAIL  {name}: {type(exc).__name__}: {exc}")

    app = QApplication(sys.argv[:1])

    from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR, qVersion
    lines.append(f"Python {sys.version.split()[0]}  PyQt6 {PYQT_VERSION_STR}  "
                 f"Qt {qVersion()} (built for {QT_VERSION_STR})  frozen={getattr(sys, 'frozen', False)}")
    check("Qt platform plugin", lambda: QGuiApplication.platformName() or "unknown")

    def sprites() -> str:
        import json
        from config import SPRITES_DIR
        with open(os.path.join(SPRITES_DIR, "manifest.json"), encoding="utf-8") as f:
            names = list(json.load(f)["animations"])
        am = AnimationManager()
        for n in names:
            if not am.has_strip(n) or am.pixmap(n, 0).isNull():
                raise RuntimeError(f"sprite strip '{n}' did not load")
        return f"{len(names)} strips"
    check("sprites", sprites)

    def tray_icon() -> str:
        from tray_manager import _make_tray_icon
        if _make_tray_icon().isNull():
            raise RuntimeError("tray icon is empty")
        return "icon.ico"
    check("tray icon", tray_icon)

    def activity() -> str:
        import psutil
        from pynput import keyboard
        keyboard.Listener                     # backend import happens here
        return f"psutil {psutil.__version__}, pynput backend {keyboard.Listener.__module__}"
    check("activity monitoring", activity)

    def settings_db() -> str:
        import sqlite3
        sqlite3.connect(":memory:").execute("select 1")
        return f"sqlite {sqlite3.sqlite_version}"
    check("sqlite", settings_db)

    del app
    lines.append("SELF-TEST " + ("PASSED" if ok else "FAILED"))
    text = "\n".join(lines) + "\n"
    log.info("Self-test:\n%s", text)
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(text)
    elif sys.stdout is not None:
        print(text, end="")
    return 0 if ok else 1


def main() -> None:
    if "--self-test" in sys.argv:
        i = sys.argv.index("--self-test")
        report = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
        sys.exit(self_test(report))

    # ── single-instance guard (Windows named mutex) ───────────────
    _mutex = None
    if sys.platform == "win32":
        try:
            import ctypes
            _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "CodingCat_SingleInstance")
            if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                log.warning("Another instance is already running — exiting")
                sys.exit(0)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    controller = CodingCatApp(app)  # noqa: F841  (keep a reference for the app lifetime)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
