"""
CodingCat - Settings Dialog
PyQt6 dialog for adjusting FPS, display size, Pomodoro durations.
"""
from __future__ import annotations
from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QSpinBox, QPushButton, QGroupBox,
    QCheckBox, QFormLayout, QSizePolicy, QComboBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from config import (
    MIN_FPS, MAX_FPS, MIN_DISPLAY_SIZE, MAX_DISPLAY_SIZE,
    MIN_SLEEP_AFTER_SECS, MAX_SLEEP_AFTER_SECS,
)
from positioning import MOVEMENT_CHOICES
from settings_manager import Settings

# Animations the user can pick and play on the cat (name → label).
PREVIEW_ANIMATIONS = {
    "jump":  "Jump",
    "heart": "Heart",
    "task":  "Task done",
    "debug": "Debug",
    "wake":  "Wake up",
}

_MOVEMENT_LABELS = {
    "beside": "Beside my window",
    "left":   "Left",
    "center": "Center",
    "right":  "Right",
    "stay":   "Stay where it is",
}


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: Settings,
        parent=None,
        auto_move: bool = True,
        on_play_animation: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.auto_move = auto_move
        self._on_play_animation = on_play_animation
        self.setWindowTitle("Mewly ⚙ Settings")
        self.setMinimumWidth(380)
        self.setStyleSheet("""
            QDialog { background:#1e1e2e; color:#cdd6f4; }
            QLabel  { color:#cdd6f4; }
            QGroupBox { color:#89b4fa; border:1px solid #313244;
                        border-radius:6px; margin-top:8px; padding:8px; }
            QGroupBox::title { subcontrol-origin:margin; padding:0 4px; }
            QPushButton { background:#313244; color:#cdd6f4; border:none;
                          border-radius:4px; padding:6px 16px; }
            QPushButton:hover  { background:#45475a; }
            QPushButton#save   { background:#89b4fa; color:#1e1e2e; }
            QPushButton#save:hover { background:#b4befe; }
            QSpinBox  { background:#313244; color:#cdd6f4; border:1px solid #45475a;
                        border-radius:4px; padding:2px 6px; }
            QSlider::groove:horizontal { background:#313244; height:6px; border-radius:3px; }
            QSlider::handle:horizontal { background:#89b4fa; width:14px; height:14px;
                                         border-radius:7px; margin:-4px 0; }
            QCheckBox { color:#cdd6f4; }
            QComboBox { background:#313244; color:#cdd6f4; border:1px solid #45475a;
                        border-radius:4px; padding:2px 6px; }
            QComboBox QAbstractItemView { background:#313244; color:#cdd6f4;
                                          selection-background-color:#45475a; }
        """)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("⚙  Settings")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color:#89b4fa;")
        layout.addWidget(title)

        # ── Display ──────────────────────────────────────────────
        disp_group = QGroupBox("Display")
        form = QFormLayout(disp_group)

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(MIN_FPS, MAX_FPS)
        self.fps_spin.setToolTip("Overall animation speed (8 = as designed)")
        self.fps_spin.setValue(self.settings.fps)
        form.addRow("Animation FPS:", self.fps_spin)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(MIN_DISPLAY_SIZE, MAX_DISPLAY_SIZE)
        self.size_spin.setSingleStep(10)
        self.size_spin.setValue(self.settings.display_size)
        form.addRow("Cat Size (px):", self.size_spin)

        self.aot_check = QCheckBox("Always on top")
        self.aot_check.setChecked(self.settings.always_on_top)
        form.addRow("", self.aot_check)
        layout.addWidget(disp_group)

        # ── Behaviour ────────────────────────────────────────────
        beh_group = QGroupBox("Behaviour")
        bform = QFormLayout(beh_group)
        self.sleep_spin = QSpinBox()
        self.sleep_spin.setRange(MIN_SLEEP_AFTER_SECS, MAX_SLEEP_AFTER_SECS)
        self.sleep_spin.setSingleStep(15)
        self.sleep_spin.setSuffix(" s")
        self.sleep_spin.setValue(self.settings.sleep_after_secs)
        self.sleep_spin.setToolTip("No keyboard/mouse input for this long → the cat falls asleep")
        bform.addRow("Sleep after:", self.sleep_spin)
        layout.addWidget(beh_group)

        # ── Animation ────────────────────────────────────────────
        anim_group = QGroupBox("Animation")
        arow = QHBoxLayout(anim_group)
        self.anim_combo = QComboBox()
        for name, label in PREVIEW_ANIMATIONS.items():
            self.anim_combo.addItem(label, name)
        arow.addWidget(QLabel("Play:"))
        arow.addWidget(self.anim_combo, 1)
        play_btn = QPushButton("▶")
        play_btn.setToolTip("Play the chosen animation on Mewly")
        play_btn.clicked.connect(self._play_animation)
        play_btn.setEnabled(self._on_play_animation is not None)
        arow.addWidget(play_btn)
        layout.addWidget(anim_group)

        # ── Movement ─────────────────────────────────────────────
        move_group = QGroupBox("🐾  Movement")
        mform = QFormLayout(move_group)
        self.auto_check = QCheckBox("Auto-move (follows your activity)")
        self.auto_check.setChecked(self.auto_move)
        self.auto_check.setToolTip("Off = manual: Mewly stays where you put it (right-drag)")
        mform.addRow("", self.auto_check)
        self.move_combos = {}
        current = self.settings.movement
        for activity, label in (("code", "When coding:"), ("idle", "When idle:"),
                                ("break", "On a break:")):
            combo = QComboBox()
            for keyword in MOVEMENT_CHOICES[activity]:
                combo.addItem(_MOVEMENT_LABELS[keyword], keyword)
            combo.setCurrentIndex(max(0, combo.findData(current[activity])))
            self.move_combos[activity] = combo
            mform.addRow(label, combo)
        self.auto_check.toggled.connect(self._update_movement_enabled)
        self._update_movement_enabled(self.auto_check.isChecked())
        layout.addWidget(move_group)

        # ── Pomodoro ─────────────────────────────────────────────
        pomo_group = QGroupBox("🍅  Pomodoro")
        pform = QFormLayout(pomo_group)

        self.work_spin = QSpinBox()
        self.work_spin.setRange(1, 90)
        self.work_spin.setValue(self.settings.pomodoro_work_mins)
        pform.addRow("Work (mins):", self.work_spin)

        self.break_spin = QSpinBox()
        self.break_spin.setRange(1, 30)
        self.break_spin.setValue(self.settings.pomodoro_break_mins)
        pform.addRow("Break (mins):", self.break_spin)
        layout.addWidget(pomo_group)

        # ── Buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("save")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _save(self) -> None:
        self.settings.fps              = self.fps_spin.value()
        self.settings.display_size     = self.size_spin.value()
        self.settings.always_on_top    = self.aot_check.isChecked()
        self.settings.pomodoro_work_mins  = self.work_spin.value()
        self.settings.pomodoro_break_mins = self.break_spin.value()
        self.settings.sleep_after_secs    = self.sleep_spin.value()
        self.settings.move_code  = self.move_combos["code"].currentData()
        self.settings.move_idle  = self.move_combos["idle"].currentData()
        self.settings.move_break = self.move_combos["break"].currentData()
        self.auto_move = self.auto_check.isChecked()
        self.accept()

    def _play_animation(self) -> None:
        if self._on_play_animation is not None:
            self._on_play_animation(self.anim_combo.currentData())

    def _update_movement_enabled(self, auto: bool) -> None:
        for combo in self.move_combos.values():
            combo.setEnabled(auto)
