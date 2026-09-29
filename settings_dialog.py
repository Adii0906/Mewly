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
    QFrame, QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
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
        self.setStyleSheet("""
            QDialog { background:#1e1e2e; color:#cdd6f4; }
            QLabel  { color:#cdd6f4; }
            QGroupBox { color:#89b4fa; font-weight:bold; border:1px solid #313244;
                        border-radius:6px; margin-top:10px; padding:10px 8px 6px 8px; }
            QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }
            QPushButton { background:#313244; color:#cdd6f4; border:none;
                          border-radius:4px; padding:6px 16px; }
            QPushButton:hover  { background:#45475a; }
            QPushButton#save   { background:#89b4fa; color:#1e1e2e; font-weight:bold; }
            QPushButton#save:hover { background:#b4befe; }
            QSpinBox  { background:#313244; color:#cdd6f4; border:1px solid #45475a;
                        border-radius:4px; padding:2px 6px; min-height:20px; }
            QSlider::groove:horizontal { background:#313244; height:6px; border-radius:3px; }
            QSlider::handle:horizontal { background:#89b4fa; width:14px; height:14px;
                                         border-radius:7px; margin:-4px 0; }
            QCheckBox { color:#cdd6f4; }
            QComboBox { background:#313244; color:#cdd6f4; border:1px solid #45475a;
                        border-radius:4px; padding:2px 6px; min-height:20px; }
            QComboBox QAbstractItemView { background:#313244; color:#cdd6f4;
                                          selection-background-color:#45475a; }
            QScrollArea, QScrollArea > QWidget > QWidget { background:transparent; border:none; }
        """)
        self._build()
        self._fit_to_screen()

    @staticmethod
    def _form(group: QGroupBox) -> QFormLayout:
        form = QFormLayout(group)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(7)
        form.setContentsMargins(4, 4, 4, 2)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        return form

    def _build(self) -> None:
        # Two columns of groups keep the window short; the Save/Cancel footer
        # sits outside the (rarely needed) scroll area so it is always visible.
        left = QVBoxLayout()
        left.setSpacing(8)
        right = QVBoxLayout()
        right.setSpacing(8)

        # ── Display (left) ───────────────────────────────────────
        disp_group = QGroupBox("Display")
        form = self._form(disp_group)

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
        left.addWidget(disp_group)

        # ── Behaviour (left) ─────────────────────────────────────
        beh_group = QGroupBox("Behaviour")
        bform = self._form(beh_group)
        self.sleep_spin = QSpinBox()
        self.sleep_spin.setRange(MIN_SLEEP_AFTER_SECS, MAX_SLEEP_AFTER_SECS)
        self.sleep_spin.setSingleStep(15)
        self.sleep_spin.setSuffix(" s")
        self.sleep_spin.setValue(self.settings.sleep_after_secs)
        self.sleep_spin.setToolTip("No keyboard/mouse input for this long → Mewly takes a break")
        bform.addRow("Break after:", self.sleep_spin)
        left.addWidget(beh_group)

        # ── Pomodoro (left) ──────────────────────────────────────
        pomo_group = QGroupBox("🍅  Pomodoro")
        pform = self._form(pomo_group)

        self.work_spin = QSpinBox()
        self.work_spin.setRange(1, 90)
        self.work_spin.setValue(self.settings.pomodoro_work_mins)
        pform.addRow("Work (mins):", self.work_spin)

        self.break_spin = QSpinBox()
        self.break_spin.setRange(1, 30)
        self.break_spin.setValue(self.settings.pomodoro_break_mins)
        pform.addRow("Break (mins):", self.break_spin)
        left.addWidget(pomo_group)
        left.addStretch()

        # ── Movement (right) ─────────────────────────────────────
        move_group = QGroupBox("🐾  Movement")
        mform = self._form(move_group)
        self.auto_check = QCheckBox("Automatic Movement")
        self.auto_check.setChecked(self.auto_move)
        self.auto_check.setToolTip("On by default: Mewly moves on its own based on your activity")
        mform.addRow(self.auto_check)
        self.auto_hint = QLabel()
        self.auto_hint.setWordWrap(True)
        self.auto_hint.setStyleSheet("color:#a6adc8; font-size:11px;")
        mform.addRow(self.auto_hint)
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
        right.addWidget(move_group)

        # ── Animation (right) ────────────────────────────────────
        anim_group = QGroupBox("Animation")
        arow = QHBoxLayout(anim_group)
        arow.setContentsMargins(4, 4, 4, 2)
        arow.setSpacing(8)
        self.anim_combo = QComboBox()
        for name, label in PREVIEW_ANIMATIONS.items():
            self.anim_combo.addItem(label, name)
        arow.addWidget(QLabel("Play:"))
        arow.addWidget(self.anim_combo, 1)
        play_btn = QPushButton("▶")
        play_btn.setToolTip("Play the chosen animation on Mewly")
        play_btn.setFixedWidth(40)
        play_btn.clicked.connect(self._play_animation)
        play_btn.setEnabled(self._on_play_animation is not None)
        arow.addWidget(play_btn)
        right.addWidget(anim_group)
        right.addStretch()

        columns = QHBoxLayout()
        columns.setSpacing(12)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)

        body = QWidget()
        body.setLayout(columns)
        self._scroll = QScrollArea()
        self._scroll.setWidget(body)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.setAutoFillBackground(False)             # keep the dark dialog background
        self._scroll.viewport().setAutoFillBackground(False)

        # ── Buttons (always visible) ─────────────────────────────
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(10)
        layout.addWidget(self._scroll, 1)
        layout.addLayout(btn_row)

    def _fit_to_screen(self) -> None:
        """Size to the content, but never taller/wider than the screen allows."""
        body = self._scroll.widget()
        want = body.sizeHint()
        screen = self.screen() or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        footer = 60                                  # buttons + margins
        w = want.width() + 32
        h = want.height() + footer
        if avail is not None:
            w = min(w, int(avail.width() * 0.9))
            h = min(h, int(avail.height() * 0.85))
        self.resize(max(w, 520), h)

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
        self.auto_hint.setText(
            "Mewly moves left, right or to the center based on your activity."
            if auto else
            "Automatic movement disabled. Manual / keyword movement remains "
            "available: right-drag, or right-click → Walk to… Left / Center / Right."
        )
