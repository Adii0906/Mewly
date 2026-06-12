"""
CodingCat - Cat Widget (v3 - ground-up rewrite)

WHAT WAS WRONG:
  QLabel inside WA_TranslucentBackground on Windows does not properly
  clear its own background between frames — the label compositor leaves
  ghost pixels from the previous frame because the child widget gets a
  dirty region that doesn't match the transparent parent's clear pass.

THE ONLY CORRECT APPROACH FOR A TRANSPARENT ANIMATED WINDOW ON WINDOWS:
  1. One QWidget, no child widgets at all.
  2. Override paintEvent.
  3. FIRST call painter.eraseRect() / fillRect with transparent, THEN draw.
  4. Call update() to schedule a repaint each tick.
  5. One QTimer. No interval changes. Frame index counter gates speed.
"""
from __future__ import annotations
import random
import logging
from typing import Optional

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import (
    QPixmap, QCursor, QMouseEvent, QEnterEvent,
    QPainter, QPaintEvent, QColor, QFont, QKeyEvent,
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QSize, pyqtSignal

from animation_manager import AnimationManager
from state_manager import StateManager, CatState, STATIONARY_STATES
from movement_manager import MovementManager
from config import CAT_DISPLAY_SIZE, STATE_FPS_OVERRIDE, DEFAULT_FPS

log = logging.getLogger("CodingCat.widget")

# Fully transparent colour used to erase the window each frame
_TRANSPARENT = QColor(0, 0, 0, 0)


class CatWidget(QWidget):
    """
    Single transparent frameless window.
    - No child widgets (no QLabel, no layout).
    - paintEvent erases the whole window FIRST, then draws exactly one pixmap.
    - One QTimer at fixed 50 ms (20 Hz master clock).
    - Frame index counter controls animation speed without touching the timer.
    """

    right_clicked = pyqtSignal(QPoint)
    exit_requested = pyqtSignal()

    def __init__(
        self,
        anim_manager: AnimationManager,
        state_manager: StateManager,
        movement_manager: MovementManager,
        display_size: int = CAT_DISPLAY_SIZE,
        fps: int = DEFAULT_FPS,
    ) -> None:
        super().__init__()

        self._anim  = anim_manager
        self._state = state_manager
        self._move  = movement_manager
        self._size  = display_size
        self._fps   = fps

        # current animation
        self._active_state: str        = "idle"
        self._active_flip:  bool       = False
        self._frames:       list[QPixmap] = []
        self._frame_idx:    int        = 0

        # frame-rate governor (master clock = 20 Hz)
        self._tick_ctr:     int = 0
        self._ticks_per_frame: int = self._tpf(fps)

        # drag
        self._drag_offset:  Optional[QPoint] = None
        self._is_dragging:  bool = False

        # reaction text overlay
        self._reaction:     str = ""
        self._react_alpha:  int = 0

        # configure the window
        self._init_window()
        self.setToolTip("Right-click to open menu; Esc or Ctrl+Alt+Q to Exit")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # load idle frames before first paint
        self._switch_frames("idle", False)

        # single timer — never stopped, never restarted
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(50)   # 20 Hz
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        log.info("CatWidget ready  size=%d  fps=%d", display_size, fps)

    # ── public ────────────────────────────────────────────────────

    def set_fps(self, fps: int) -> None:
        self._fps = fps
        self._ticks_per_frame = self._tpf(fps)

    def set_display_size(self, size: int) -> None:
        self._size = size
        self.setFixedSize(size, size)
        self._anim.display_size = size
        self._anim._frames.clear()
        self._anim._flipped.clear()
        self._anim._slice_all()
        self._switch_frames(self._active_state, self._active_flip)

    def set_always_on_top(self, on_top: bool) -> None:
        flags = self.windowFlags()
        if on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def show_reaction(self, text: str) -> None:
        self._reaction   = text
        self._react_alpha = 255
        QTimer.singleShot(1400, self._fade_reaction)

    # ── Qt painting ───────────────────────────────────────────────

    def paintEvent(self, _: QPaintEvent) -> None:
        p = QPainter(self)

        # Step 1 — erase to fully transparent (CRITICAL — prevents ghosting)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.fillRect(self.rect(), _TRANSPARENT)

        # Step 2 — draw current sprite frame (SourceOver on cleared canvas)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if self._frames:
            p.drawPixmap(0, 0, self._size, self._size,
                         self._frames[self._frame_idx])

        # Step 3 — reaction text (optional)
        if self._react_alpha > 0 and self._reaction:
            c = QColor(255, 220, 80, self._react_alpha)
            p.setPen(c)
            p.setFont(QFont("Segoe UI Emoji", 13, QFont.Weight.Bold))
            p.drawText(QRect(0, -20, self._size, 26),
                       Qt.AlignmentFlag.AlignHCenter, self._reaction)

        p.end()

    # ── mouse ────────────────────────────────────────────────────

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.pos()
            self._is_dragging = False
        elif e.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_offset and e.buttons() & Qt.MouseButton.LeftButton:
            if not self._is_dragging:
                if (e.pos() - self._drag_offset).manhattanLength() >= 4:
                    self._is_dragging = True
            if self._is_dragging:
                new_pos = e.globalPosition().toPoint() - self._drag_offset
                self.move(new_pos)
                self._move.set_position(new_pos.x(), new_pos.y())

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            if not self._is_dragging:
                self._on_click()
            self._drag_offset = None
            self._is_dragging = False

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._on_dbl_click()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.exit_requested.emit()
            return
        if (e.modifiers() & Qt.KeyboardModifier.ControlModifier) and (
            e.modifiers() & Qt.KeyboardModifier.AltModifier
        ) and e.key() == Qt.Key.Key_Q:
            self.exit_requested.emit()
            return
        super().keyPressEvent(e)

    def enterEvent(self, _: QEnterEvent) -> None:
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def leaveEvent(self, _) -> None:
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    # ── master tick ───────────────────────────────────────────────

    def _tick(self) -> None:
        # --- resolve state & position ---
        if not self._is_dragging:
            locked         = self._state.state in STATIONARY_STATES
            movement_state = self._move.tick(locked)
            resolved       = self._state.tick(movement_state)

            # move window
            mx, my = self._move.x, self._move.y
            if self.x() != mx or self.y() != my:
                self.move(mx, my)

            # update animation speed
            sfps = STATE_FPS_OVERRIDE.get(resolved.value, self._fps)
            self._ticks_per_frame = self._tpf(sfps)

            # switch frame list when state or direction changes
            flip = self._move.facing_left
            if resolved.value != self._active_state or flip != self._active_flip:
                log.debug("State → %s  flip=%s", resolved.value, flip)
                self._switch_frames(resolved.value, flip)

        # --- advance frame index ---
        self._tick_ctr += 1
        if self._tick_ctr >= self._ticks_per_frame:
            self._tick_ctr = 0
            if self._frames:
                self._frame_idx = (self._frame_idx + 1) % len(self._frames)

        # --- repaint (erases old frame first via paintEvent) ---
        self.update()

    # ── helpers ───────────────────────────────────────────────────

    def _init_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        # WA_TranslucentBackground tells Qt the window surface supports alpha.
        # WA_NoSystemBackground stops Qt from pre-filling with the palette colour.
        # Together they give us a clean transparent canvas every paintEvent.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFixedSize(self._size, self._size)

    def _switch_frames(self, state: str, flip: bool) -> None:
        """Load a new frame list. Always resets index to 0."""
        frames = self._anim.get_frames(state, flip=flip)
        if not frames:
            log.warning("No frames for state=%s — staying on %s", state, self._active_state)
            return
        self._active_state = state
        self._active_flip  = flip
        self._frames       = frames
        self._frame_idx    = 0      # start from frame 0, no bleed from previous list
        self._tick_ctr     = 0

    @staticmethod
    def _tpf(fps: int) -> int:
        """Ticks-per-frame for a 20 Hz master clock."""
        return max(1, round(20 / max(1, fps)))

    def _on_click(self) -> None:
        self.show_reaction(random.choice(["nyaa~", "purr ✨", "meow!", "💕 uwu"]))
        self._state.force_state(CatState.JUMP, duration_ticks=12)

    def _on_dbl_click(self) -> None:
        self.show_reaction("💖 UWU!")
        self._state.force_state(CatState.TASK, duration_ticks=20)

    def _fade_reaction(self) -> None:
        self._react_alpha = max(0, self._react_alpha - 40)
        self.update()
        if self._react_alpha > 0:
            QTimer.singleShot(50, self._fade_reaction)
        else:
            self._reaction = ""
