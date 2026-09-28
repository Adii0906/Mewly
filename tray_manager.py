"""
CodingCat - Tray Manager
System tray icon, right-click menu, and Pomodoro status.
"""
from __future__ import annotations
import os
from typing import Callable, Optional
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont
from PyQt6.QtCore import Qt, QTimer

from config import ASSETS_DIR


def _make_tray_icon() -> QIcon:
    """Create a simple pixel-art tray icon if no .ico is present."""
    ico_path = os.path.join(ASSETS_DIR, "icon.ico")
    if os.path.exists(ico_path):
        return QIcon(ico_path)

    # Draw a tiny orange cat face
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Face
    p.setBrush(QColor("#F4A460"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(4, 8, 24, 20)
    # Ears
    p.setBrush(QColor("#F4A460"))
    p.drawPolygon(*[
        __import__("PyQt6.QtCore", fromlist=["QPoint"]).QPoint(*xy)
        for xy in [(4,12),(8,4),(12,12)]
    ])
    p.drawPolygon(*[
        __import__("PyQt6.QtCore", fromlist=["QPoint"]).QPoint(*xy)
        for xy in [(20,12),(24,4),(28,12)]
    ])
    # Eyes
    p.setBrush(QColor("#1a1a2e"))
    p.drawEllipse(9, 14, 5, 5)
    p.drawEllipse(18, 14, 5, 5)
    p.end()
    return QIcon(pix)


class TrayManager:
    def __init__(
        self,
        on_exit: Callable,
        on_toggle_visibility: Callable,
        on_start_pomodoro: Callable,
        on_stop_pomodoro: Callable,
        on_open_settings: Callable,
        on_trigger_task: Callable,
        on_trigger_debug: Callable,
    ) -> None:
        self._on_exit = on_exit
        self._tray = QSystemTrayIcon()
        self._tray.setIcon(_make_tray_icon())
        self._tray.setToolTip("Mewly 🐱")
        self._tray.activated.connect(self._on_activated)

        self._on_toggle = on_toggle_visibility
        self._pomo_action = None      # created by _build_menu (must not be reset after it)
        self._menu: Optional[QMenu] = None
        self._build_menu(
            on_toggle_visibility, on_start_pomodoro, on_stop_pomodoro,
            on_open_settings, on_trigger_task, on_trigger_debug,
        )
        self._tray.show()

    # ── Public ────────────────────────────────────────────────────────────────

    def update_pomodoro_label(self, remaining: Optional[int], phase: str) -> None:
        if self._pomo_action:
            if remaining is None:
                self._pomo_action.setText("🍅  Pomodoro")
                return
            m, s = divmod(remaining, 60)
            icon = "🍅" if phase == "work" else "☕"
            self._pomo_action.setText(f"{icon} {m:02d}:{s:02d}")

    def notify(self, title: str, msg: str) -> None:
        self._tray.showMessage(title, msg, QSystemTrayIcon.MessageIcon.Information, 3000)

    def hide(self) -> None:
        self._tray.hide()

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_menu(self, on_toggle, on_start_pomo, on_stop_pomo,
                    on_settings, on_task, on_debug) -> None:
        # Keep a reference: QSystemTrayIcon does not own its context menu,
        # so a local QMenu would be garbage-collected and the menu would vanish.
        menu = self._menu = QMenu()

        title_action = menu.addAction("🐱  Mewly")
        title_action.setEnabled(False)
        menu.addSeparator()

        self._pomo_action = menu.addAction("🍅  Pomodoro")
        self._pomo_action.setEnabled(False)

        start_pomo = menu.addAction("▶  Start Pomodoro")
        start_pomo.triggered.connect(on_start_pomo)

        stop_pomo = menu.addAction("⏹  Stop Pomodoro")
        stop_pomo.triggered.connect(on_stop_pomo)

        menu.addSeparator()

        task_action = menu.addAction("✅  Task Completed!")
        task_action.triggered.connect(on_task)

        debug_action = menu.addAction("🐛  Debug Mode")
        debug_action.triggered.connect(on_debug)

        menu.addSeparator()

        toggle_action = menu.addAction("👁  Show / Hide")
        toggle_action.triggered.connect(on_toggle)

        settings_action = menu.addAction("⚙  Settings")
        settings_action.triggered.connect(on_settings)

        menu.addSeparator()

        exit_action = menu.addAction("✖  Exit")
        exit_action.triggered.connect(self._on_exit)

        self._tray.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_toggle()
