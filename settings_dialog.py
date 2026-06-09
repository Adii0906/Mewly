"""
CodingCat - Settings Dialog
PyQt6 dialog for adjusting FPS, display size, Pomodoro durations.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QSpinBox, QPushButton, QGroupBox,
    QCheckBox, QFormLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from settings_manager import Settings


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("CodingCat ⚙ Settings")
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
        self.fps_spin.setRange(4, 24)
        self.fps_spin.setValue(self.settings.fps)
        form.addRow("Animation FPS:", self.fps_spin)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(60, 240)
        self.size_spin.setSingleStep(10)
        self.size_spin.setValue(self.settings.display_size)
        form.addRow("Cat Size (px):", self.size_spin)

        self.aot_check = QCheckBox("Always on top")
        self.aot_check.setChecked(self.settings.always_on_top)
        form.addRow("", self.aot_check)
        layout.addWidget(disp_group)

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
        self.accept()
