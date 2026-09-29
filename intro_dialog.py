"""
Mewly - First-launch introduction

A small, dark, one-page window explaining what Mewly is and how to control
it.  Shown at startup until the user ticks "Don't show this again" (stored
as the `show_intro` setting).  No wizard, no pages, no network.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

_STYLE = """
    QDialog  { background:#1e1e2e; color:#cdd6f4; }
    QLabel   { color:#cdd6f4; }
    QLabel#title   { color:#89b4fa; }
    QLabel#section { color:#89b4fa; font-weight:bold; }
    QLabel#muted   { color:#a6adc8; }
    QCheckBox { color:#a6adc8; }
    QPushButton { background:#89b4fa; color:#1e1e2e; border:none;
                  border-radius:4px; padding:6px 18px; font-weight:bold; }
    QPushButton:hover { background:#b4befe; }
"""

_HOW_IT_WORKS = (
    "Mewly reacts to your clicks and to what you're doing.",
    "Size, animations and movement can be changed in Settings.",
)

_HOW_IT_MOVES = (
    "Mewly moves <b>automatically</b> by default. It watches your activity and "
    "moves left, right or to the center based on what you're doing."
    "<br><span style='color:#a6adc8'>Prefer to be in control? Turn off "
    "<b>Automatic Movement</b> in Settings and move Mewly yourself (right-drag "
    "or Walk to… Left / Center / Right).</span>"
)

_TAKING_A_BREAK = (
    "If you're away for {secs} seconds, Mewly takes a little break too. "
    "Start using your computer again and he'll wake up and get back to work. 🐈‍⬛"
)

_CONTROLS = (
    ("🖱  Right-click", "Open the menu. Right-drag to place Mewly yourself."),
    ("⚙  Settings", "In the right-click menu: size, animation and movement."),
    ("⎋  Esc", "Click Mewly, then press Esc to close it."),
)


class IntroDialog(QDialog):
    def __init__(self, cat_pixmap: Optional[QPixmap] = None, parent=None,
                 break_after_secs: int = 10) -> None:
        super().__init__(parent)
        self._break_after_secs = break_after_secs
        self.setWindowTitle("Meet Mewly")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setFixedWidth(400)
        self.setStyleSheet(_STYLE)
        self._build(cat_pixmap)

    @property
    def dont_show_again(self) -> bool:
        return self._dont_show.isChecked()

    def _build(self, cat_pixmap: Optional[QPixmap]) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(10)

        # ── header: cat + greeting ───────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(12)
        if cat_pixmap is not None and not cat_pixmap.isNull():
            pic = QLabel()
            pic.setPixmap(cat_pixmap)
            pic.setAlignment(Qt.AlignmentFlag.AlignBottom)
            header.addWidget(pic)
        text = QVBoxLayout()
        text.setSpacing(4)
        title = QLabel("Meet Mewly")
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        text.addWidget(title)
        blurb = QLabel(
            "A tiny desktop cat, made by a developer who probably spent way "
            "too much time teaching a cat to sit on your screen."
        )
        blurb.setWordWrap(True)
        text.addWidget(blurb)
        header.addLayout(text, 1)
        root.addLayout(header)

        # ── how it works ─────────────────────────────────────────
        root.addWidget(self._section("How it works"))
        items = QLabel("<br>".join(f"• {line}" for line in _HOW_IT_WORKS))
        items.setTextFormat(Qt.TextFormat.RichText)
        items.setWordWrap(True)
        root.addWidget(items)

        # ── how Mewly moves / taking a break ────────────────────
        root.addWidget(self._section("🐾  How Mewly moves"))
        root.addWidget(self._paragraph(_HOW_IT_MOVES))
        root.addWidget(self._section("💤  Taking a break?"))
        root.addWidget(self._paragraph(_TAKING_A_BREAK.format(secs=self._break_after_secs)))

        # ── controls ─────────────────────────────────────────────
        root.addWidget(self._section("Controls"))
        for key, what in _CONTROLS:
            row = QHBoxLayout()
            row.setSpacing(8)
            k = QLabel(key)
            k.setFixedWidth(104)
            k.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            row.addWidget(k, 0, Qt.AlignmentFlag.AlignTop)
            w = QLabel(what)
            w.setObjectName("muted")
            w.setWordWrap(True)
            row.addWidget(w, 1)
            root.addLayout(row)

        # ── footer ───────────────────────────────────────────────
        root.addSpacing(4)
        footer = QHBoxLayout()
        self._dont_show = QCheckBox("Don't show this again")
        footer.addWidget(self._dont_show)
        footer.addStretch()
        ok = QPushButton("Got it")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        footer.addWidget(ok)
        root.addLayout(footer)

    @staticmethod
    def _paragraph(html: str) -> QLabel:
        label = QLabel(html)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        return label

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("section")
        return label
