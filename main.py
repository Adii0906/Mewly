"""
CodingCat - Main Entry Point  (v2)
Single-instance guard + structured logging added.
"""
from __future__ import annotations
import sys
import os
import logging

# ── PyInstaller frozen-bundle path fix ───────────────────────────────────────
if getattr(sys, "frozen", False):
    _BASE = sys._MEIPASS          # type: ignore[attr-defined]
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("CODING_CAT_BASE", _BASE)

# ── Logging setup (writes to ~/.coding_cat/cat.log + stderr) ─────────────────
_LOG_DIR = os.path.join(os.path.expanduser("~"), ".coding_cat")
os.makedirs(_LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(_LOG_DIR, "cat.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("CodingCat.main")

from PyQt6.QtWidgets import QApplication, QMenu
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QCursor

from config import APP_NAME, CAT_DISPLAY_SIZE, DEFAULT_FPS
from storage import init_db
from settings_manager import SettingsManager
from animation_manager import AnimationManager
from state_manager import StateManager, CatState
from movement_manager import MovementManager
from productivity_manager import ProductivityManager
from cat_widget import CatWidget
from tray_manager import TrayManager
from settings_dialog import SettingsDialog


class CodingCatApp:
    """Top-level controller.  Owns exactly ONE CatWidget."""

    def __init__(self, app: QApplication) -> None:
        self._app = app
        init_db()
        log.info("CodingCat %s starting up", APP_NAME)

        # ── Settings ──────────────────────────────────────────────
        self._settings_mgr = SettingsManager()
        cfg = self._settings_mgr.settings
        log.info("Settings: pos=(%d,%d) fps=%d size=%d", cfg.pos_x, cfg.pos_y, cfg.fps, cfg.display_size)

        # ── Core subsystems (one each) ────────────────────────────
        self._anim_mgr  = AnimationManager(display_size=cfg.display_size)
        self._state_mgr = StateManager(on_state_change=self._on_state_change)
        self._move_mgr  = MovementManager()
        self._prod_mgr  = ProductivityManager()

        # ── Single cat window ─────────────────────────────────────
        self._cat = CatWidget(
            anim_manager=self._anim_mgr,
            state_manager=self._state_mgr,
            movement_manager=self._move_mgr,
            display_size=cfg.display_size,
            fps=cfg.fps,
        )
        self._cat.right_clicked.connect(self._show_context_menu)
        self._cat.exit_requested.connect(self._quit)

        # Restore last position BEFORE show()
        self._cat.move(cfg.pos_x, cfg.pos_y)
        self._move_mgr.set_position(cfg.pos_x, cfg.pos_y)
        self._cat.set_always_on_top(cfg.always_on_top)
        self._cat.show()
        self._cat.show_reaction("Right click cat to Exit")
        log.info("Cat window shown at (%d, %d)", cfg.pos_x, cfg.pos_y)

        # ── System tray ───────────────────────────────────────────
        self._tray = TrayManager(
            on_exit              = self._quit,
            on_toggle_visibility = self._toggle_visibility,
            on_start_pomodoro    = self._start_pomodoro,
            on_stop_pomodoro     = self._stop_pomodoro,
            on_open_settings     = self._open_settings,
            on_trigger_task      = self.trigger_task_completed,
            on_trigger_debug     = self.trigger_debug_mode,
        )
        self._tray.notify("CodingCat", "Right-click the cat or tray icon to Exit")

        # ── Productivity → state bridge ───────────────────────────
        self._prod_mgr.state_changed.connect(self._on_productivity_state)
        self._prod_mgr.pomodoro_tick.connect(self._on_pomodoro_tick)

        # ── Autosave every 30 s ───────────────────────────────────
        self._save_timer = QTimer()
        self._save_timer.timeout.connect(self._autosave)
        self._save_timer.start(30_000)

    # ── Public trigger API ────────────────────────────────────────────────────

    def trigger_task_completed(self) -> None:
        log.info("trigger_task_completed")
        self._state_mgr.force_state(CatState.TASK, duration_ticks=40)
        self._cat.show_reaction("✅ Done!")
        self._tray.notify("CodingCat", "Task completed! 🎉")

    def trigger_debug_mode(self) -> None:
        log.info("trigger_debug_mode")
        self._state_mgr.force_state(CatState.DEBUG, duration_ticks=40)
        self._cat.show_reaction("🐛 Debug!")

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_state_change(self, old: CatState, new: CatState) -> None:
        log.info("State  %s → %s", old.value, new.value)

    def _on_productivity_state(self, state) -> None:
        self._state_mgr.set_productivity_state(state)
        if state:
            log.debug("Productivity state → %s", state.value)

    def _on_pomodoro_tick(self, remaining: int, total: int, phase: str) -> None:
        self._tray.update_pomodoro_label(remaining, phase)
        if remaining == 0:
            if phase == "work":
                self._tray.notify("CodingCat 🍅", "Pomodoro done! Take a break ☕")
                self._cat.show_reaction("☕ Break!")
            else:
                self._tray.notify("CodingCat 🍅", "Break over! Back to work 💪")
                self._cat.show_reaction("💪 Work!")

    def _show_context_menu(self, pos: QPoint) -> None:
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background:#1e1e2e; color:#cdd6f4; border:1px solid #313244;
                    border-radius:6px; padding:4px; }
            QMenu::item { padding:5px 20px 5px 10px; border-radius:4px; }
            QMenu::item:selected { background:#313244; }
            QMenu::separator { background:#313244; height:1px; margin:4px 8px; }
        """)
        menu.addAction("✅ Task Done",      self.trigger_task_completed)
        menu.addAction("🐛 Debug Mode",     self.trigger_debug_mode)
        menu.addSeparator()
        menu.addAction("▶ Start Pomodoro",  self._start_pomodoro)
        menu.addAction("⏹ Stop Pomodoro",   self._stop_pomodoro)
        menu.addSeparator()
        menu.addAction("⚙  Settings",       self._open_settings)
        menu.addSeparator()
        menu.addAction("✖  Exit",           self._quit)
        menu.exec(pos)

    def _toggle_visibility(self) -> None:
        if self._cat.isVisible():
            self._cat.hide()
        else:
            self._cat.show()

    def _start_pomodoro(self) -> None:
        self._prod_mgr.start_pomodoro()
        self._cat.show_reaction("🍅 Start!")
        self._tray.notify("CodingCat", "Pomodoro started! 🍅")
        log.info("Pomodoro started")

    def _stop_pomodoro(self) -> None:
        self._prod_mgr.stop_pomodoro()
        self._cat.show_reaction("⏹ Stop")
        log.info("Pomodoro stopped")

    def _open_settings(self) -> None:
        cfg = self._settings_mgr.settings
        dlg = SettingsDialog(cfg)
        if dlg.exec():
            self._settings_mgr.save()
            self._cat.set_fps(cfg.fps)
            self._cat.set_display_size(cfg.display_size)
            self._cat.set_always_on_top(cfg.always_on_top)
            self._prod_mgr.set_pomodoro_times(
                cfg.pomodoro_work_mins, cfg.pomodoro_break_mins
            )
            log.info("Settings saved")

    def _autosave(self) -> None:
        cfg = self._settings_mgr.settings
        cfg.pos_x = self._cat.x()
        cfg.pos_y = self._cat.y()
        self._settings_mgr.save()
        log.debug("Position autosaved (%d, %d)", cfg.pos_x, cfg.pos_y)

    def _quit(self) -> None:
        log.info("Quitting — saving position")
        self._autosave()
        QApplication.quit()


def main() -> None:
    # ── Single-instance guard (Windows named mutex) ───────────────
    _mutex = None
    if sys.platform == "win32":
        try:
            import ctypes
            _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "CodingCat_SingleInstance")
            if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                log.warning("Another CodingCat instance is already running — exiting")
                sys.exit(0)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    controller = CodingCatApp(app)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
