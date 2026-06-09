"""
CodingCat – Statistics Dialog
Shows today's time-per-state breakdown.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHBoxLayout,
)
from PyQt6.QtCore import Qt

from storage import Storage


class StatsDialog(QDialog):
    def __init__(self, storage: Storage, pomodoro_count: int = 0, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("CodingCat – Today's Stats")
        self.setMinimumWidth(320)
        self._storage = storage
        self._pomo_count = pomodoro_count
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Today's Activity</b>"))

        stats = self._storage.get_today_stats()

        table = QTableWidget(len(stats) + 1, 2, self)
        table.setHorizontalHeaderLabels(["State", "Duration"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        emoji = {
            "idle": "😴", "walk": "🚶", "sleep": "💤", "jump": "🐾",
            "code": "💻", "focus": "🎧", "task": "✅", "debug": "🐛",
            "break": "☕", "stretch": "🙆", "loaf": "🍞", "groom": "🐱",
        }
        row = 0
        total = 0.0
        for state, secs in sorted(stats.items()):
            total += secs
            icon  = emoji.get(state, "•")
            mins  = int(secs / 60)
            table.setItem(row, 0, QTableWidgetItem(f"{icon} {state.capitalize()}"))
            table.setItem(row, 1, QTableWidgetItem(f"{mins} min"))
            row += 1

        # Total row
        total_item = QTableWidgetItem("TOTAL")
        total_item.setFont(table.font())
        table.setItem(row, 0, total_item)
        table.setItem(row, 1, QTableWidgetItem(f"{int(total/60)} min"))

        layout.addWidget(table)

        pomo_label = QLabel(
            f"🍅 Pomodoro sessions completed today: <b>{self._pomo_count}</b>"
        )
        layout.addWidget(pomo_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
