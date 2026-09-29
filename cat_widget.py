"""
Mewly - Cat Widget

One frameless, translucent window with no child widgets.  paintEvent clears
the surface and draws exactly one cached sprite frame (plus an optional
speech bubble / hearts), which avoids ghosting on Windows.

Timing: ONE timer drives everything (movement, animation, overlay fades).
Its interval adapts: ~60 Hz while walking or while an overlay fades, otherwise
it sleeps until the next animation frame is due (e.g. 500 ms while asleep).

Ownership:
- AnimationPlayer decides which frame is shown (single authority).
- CatBehavior decides which animation should play (priority rules).
- MovementManager moves the window only when a walk was requested.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QCursor, QEnterEvent, QFont, QGuiApplication, QKeyEvent,
    QMouseEvent, QMoveEvent, QPainter, QPaintEvent, QPainterPath,
)
from PyQt6.QtWidgets import QApplication, QWidget

from animation_controller import AnimationPlayer
from animation_manager import AnimationManager
from config import (
    BUBBLE_HEIGHT_RATIO, CAT_DISPLAY_SIZE, CLICK_REACTIONS, DEFAULT_FPS,
    MAX_IDLE_TICK_MS, MOVE_TICK_MS, WALK_SPEED_PX_PER_SEC, WALK_STEP_PX,
)
from movement_manager import MovementManager
from positioning import zone_of, zone_target
from state_manager import CatBehavior, CatState

log = logging.getLogger("Mewly.widget")

_BUBBLE_MS = 1600          # speech bubble lifetime
_BUBBLE_FADE_MS = 400      # ...of which the last part fades out
_HEARTS_MS = 1300
_DRAG_THRESHOLD = 4


def _now_ms() -> float:
    return time.monotonic() * 1000.0


class CatWidget(QWidget):
    right_clicked = pyqtSignal(QPoint)
    exit_requested = pyqtSignal()
    user_interacted = pyqtSignal()        # click on the cat counts as user activity
    manual_mode_changed = pyqtSignal(bool)  # True = user controls the position

    def __init__(
        self,
        anim_manager: AnimationManager,
        behavior: CatBehavior,
        movement_manager: MovementManager,
        display_size: int = CAT_DISPLAY_SIZE,
        fps: int = DEFAULT_FPS,
    ) -> None:
        super().__init__()
        self._anim = anim_manager
        self._behavior = behavior
        self._move = movement_manager
        self._player = AnimationPlayer(speed=fps / DEFAULT_FPS)
        self._on_top: Optional[bool] = None

        # input
        self._press_pos: Optional[QPoint] = None
        self._drag_offset: Optional[QPoint] = None
        self._dragging = False
        self._drag_button = Qt.MouseButton.NoButton
        self._suppress_release = False
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._on_single_click)
        self._click_count = 0

        # positioning mode: automatic (default) or manual (user-controlled)
        self._manual = False
        self._auto_hold = False        # left-drag placement: keep it until the next state change

        # overlays
        self._bubble_text = ""
        self._bubble_start = -1e9
        self._hearts_start = -1e9

        self._init_window()
        self._apply_size()

        now = _now_ms()
        self._last_tick = now
        self._player.play(self._behavior.animation(), now)

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)
        self._schedule(now)
        log.info("CatWidget ready  size=%d  fps=%d", display_size, fps)

    # ── public ────────────────────────────────────────────────────

    def set_fps(self, fps: int) -> None:
        self._player.set_speed(fps / DEFAULT_FPS)

    def set_display_size(self, size: int) -> None:
        if size == self._anim.display_size:
            return
        # Keep the cat's feet where they are while the window changes size.
        feet = QPoint(self.x() + self.width() // 2, self.y() + self.height())
        self._anim.set_display_size(size)
        self._apply_size()
        self.move_to(feet.x() - self.width() // 2, feet.y() - self.height())
        self.update()

    def set_always_on_top(self, on_top: bool) -> None:
        if on_top == self._on_top:
            return
        self._on_top = on_top
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on_top)
        if visible:            # setWindowFlag hides the window
            self.show()

    def move_to(self, x: int, y: int) -> None:
        self._move.set_position(x, y)
        self.move(x, y)

    def show_reaction(self, text: str) -> None:
        self._bubble_text = text
        self._bubble_start = _now_ms()
        self._kick()

    def show_hearts(self) -> None:
        self._hearts_start = _now_ms()
        self._kick()

    def walk_to_edge(self, where: str) -> None:
        """Right-click menu "Walk to…": a manual placement."""
        self.set_manual(True, announce=False)
        lo, hi = self._move.bounds()
        self._start_walk(zone_target(where, lo, hi))

    # ── automatic / manual positioning ────────────────────────────

    @property
    def is_manual(self) -> bool:
        return self._manual

    @property
    def auto_hold(self) -> bool:
        return self._auto_hold

    def clear_auto_hold(self) -> None:
        self._auto_hold = False

    def set_manual(self, manual: bool, announce: bool = True) -> None:
        if manual == self._manual:
            return
        self._manual = manual
        self._auto_hold = False
        if manual and self._move.is_walking:      # an automatic walk must not continue
            self._move.stop()
            self._behavior.set_walking(False)
        if announce:
            self.show_reaction("🖐 Manual" if manual else "🐾 Auto-move")
        self.manual_mode_changed.emit(manual)

    def pause_auto_walk(self) -> None:
        """Stop an automatic walk (the user went away); manual walks finish."""
        if not self._manual and self._move.is_walking:
            self._move.stop()
            self._behavior.set_walking(False)

    def auto_move(self, zone: str) -> bool:
        """Automatic mode: walk to *zone* ("left"/"center"/"right") if not already there."""
        if self._manual or self._dragging:
            return False
        lo, hi = self._move.bounds()
        target = zone_target(zone, lo, hi)
        if self._move.is_walking:
            if abs(self._move.target_x - target) < 1:
                return False
        elif zone_of(self._move.x, lo, hi) == zone:
            return False                          # already in the right place
        self._start_walk(target)
        return True

    def on_animation_changed(self, name: str) -> None:
        """CatBehavior callback: the desired animation changed."""
        if self._player.play(name, _now_ms()):
            self.update()
        self._kick()

    # ── painting ──────────────────────────────────────────────────

    def paintEvent(self, _: QPaintEvent) -> None:
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        strip, idx = self._player.frame
        flip = self._player.flippable and not self._move.facing_left
        p.drawPixmap(0, self._bubble_h, self._anim.pixmap(strip, idx, flip))

        now = _now_ms()
        self._paint_hearts(p, now)
        self._paint_bubble(p, now)
        p.end()

    def _paint_bubble(self, p: QPainter, now: float) -> None:
        age = now - self._bubble_start
        if not self._bubble_text or age >= _BUBBLE_MS:
            return
        alpha = 1.0 if age < _BUBBLE_MS - _BUBBLE_FADE_MS else (_BUBBLE_MS - age) / _BUBBLE_FADE_MS
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        font = QFont("Segoe UI", max(7, round(self._bubble_h * 0.42)), QFont.Weight.Bold)
        p.setFont(font)
        fm = p.fontMetrics()
        tw = min(self.width() - 4, fm.horizontalAdvance(self._bubble_text) + 12)
        th = min(self._bubble_h - 2, fm.height() + 4)
        rect = QRectF((self.width() - tw) / 2, 1, tw, th)
        path = QPainterPath()
        path.addRoundedRect(rect, th / 2, th / 2)
        p.setOpacity(alpha)
        p.fillPath(path, QBrush(QColor(30, 30, 46, 210)))
        p.setPen(QColor(255, 224, 120))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                   fm.elidedText(self._bubble_text, Qt.TextElideMode.ElideRight, int(tw) - 8))
        p.setOpacity(1.0)

    def _paint_hearts(self, p: QPainter, now: float) -> None:
        age = now - self._hearts_start
        if age >= _HEARTS_MS or age < 0:
            return
        t = age / _HEARTS_MS
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        size = max(8, round(self.height() * 0.13))
        p.setFont(QFont("Segoe UI Symbol", size))
        p.setPen(QColor(255, 105, 150))
        rise = t * self.height() * 0.45
        base_y = self._bubble_h + self.height() * 0.35
        # Three hearts at fixed positions and staggered starts (deterministic).
        for i, fx in enumerate((0.30, 0.52, 0.72)):
            lt = t - i * 0.12
            if lt <= 0:
                continue
            p.setOpacity(max(0.0, 1.0 - lt))
            p.drawText(QPointF(self.width() * fx - size / 2, base_y - rise + i * 4), "♥")
        p.setOpacity(1.0)

    # ── mouse / keyboard ─────────────────────────────────────────

    def mousePressEvent(self, e: QMouseEvent) -> None:
        # Left: click / drag as before.  Right: click = menu, drag = manual placement.
        if e.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self._press_pos = e.globalPosition().toPoint()
            self._drag_offset = e.position().toPoint()
            self._dragging = False
            self._drag_button = e.button()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._press_pos is None or not (e.buttons() & self._drag_button):
            return
        gpos = e.globalPosition().toPoint()
        if not self._dragging and (gpos - self._press_pos).manhattanLength() >= _DRAG_THRESHOLD:
            self._dragging = True
            self._click_timer.stop()
            if self._move.is_walking:          # the user took control
                self._move.stop()
                self._behavior.set_walking(False)
        if self._dragging:
            new = gpos - self._drag_offset
            self.move_to(new.x(), new.y())

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() != self._drag_button:
            return
        was_dragging = self._dragging
        self._press_pos = None
        self._dragging = False
        self._drag_button = Qt.MouseButton.NoButton
        if e.button() == Qt.MouseButton.RightButton:
            if was_dragging:
                self.set_manual(True)             # right-drag: the user places the cat
                self._after_drop()
            else:
                self.right_clicked.emit(e.globalPosition().toPoint())
            return
        if was_dragging:
            if not self._manual:
                self._auto_hold = True            # keep this spot until the next state change
            self._after_drop()
        elif self._suppress_release:
            self._suppress_release = False
        else:
            # Wait for a possible second click before reacting.
            self._click_timer.start(QApplication.doubleClickInterval())

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._click_timer.stop()
        self._suppress_release = True
        self._press_pos = None
        # The double-click replaces the second press; route its release here.
        self._drag_button = Qt.MouseButton.LeftButton
        was_asleep = self._behavior.base == CatState.SLEEP
        self.user_interacted.emit()
        if not was_asleep:
            self._behavior.trigger("heart")
            self.show_hearts()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        key = e.key()
        mods = e.modifiers()
        if key == Qt.Key.Key_Escape or (
            mods & Qt.KeyboardModifier.ControlModifier
            and mods & Qt.KeyboardModifier.AltModifier
            and key == Qt.Key.Key_Q
        ):
            self.exit_requested.emit()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.set_manual(True, announce=False)
            step = WALK_STEP_PX * self._scale()
            base = self._move.x
            self._start_walk(base - step if key == Qt.Key.Key_Left else base + step)
            return
        super().keyPressEvent(e)

    def enterEvent(self, _: QEnterEvent) -> None:
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def leaveEvent(self, _) -> None:
        self.unsetCursor()

    def moveEvent(self, e: QMoveEvent) -> None:
        # Moving onto a monitor with a different scale factor: rebuild sprites.
        self._anim.set_device_pixel_ratio(self.devicePixelRatioF())
        super().moveEvent(e)

    def showEvent(self, e) -> None:
        self._anim.set_device_pixel_ratio(self.devicePixelRatioF())
        super().showEvent(e)
        self._kick()

    # ── master tick ───────────────────────────────────────────────

    def _tick(self) -> None:
        try:
            self._advance(_now_ms())
        except Exception:
            log.exception("tick failed")
        finally:
            self._schedule(_now_ms())         # the single timer must never die

    def _advance(self, now: float) -> None:
        dt = (now - self._last_tick) / 1000.0
        self._last_tick = now
        dirty = False

        # 1. movement (paused during one-shots and while dragging)
        if self._move.is_walking and not self._dragging and not self._behavior.movement_paused:
            if self._move.update(dt):
                if (self.x(), self.y()) != (self._move.x, self._move.y):
                    self.move(self._move.x, self._move.y)
            if not self._move.is_walking:
                self._behavior.set_walking(False)

        # 2. animation
        changed, finished = self._player.update(now)
        dirty |= changed
        if finished:
            self._behavior.oneshot_finished(finished)   # may call on_animation_changed

        # 3. overlays
        if self._overlay_active(now) or self._overlay_active(now - 50):
            dirty = True

        if dirty:
            self.update()

    def _schedule(self, now: float) -> None:
        if self._move.is_walking or self._overlay_active(now):
            interval = MOVE_TICK_MS
        else:
            nxt = self._player.ms_until_next(now)
            interval = int(min(MAX_IDLE_TICK_MS, max(MOVE_TICK_MS, nxt + 1)))
        self._timer.start(interval)

    def _kick(self) -> None:
        """Re-evaluate soon (after an external change)."""
        if not self._timer.isActive() or self._timer.remainingTime() > MOVE_TICK_MS:
            self._timer.start(MOVE_TICK_MS)

    def _overlay_active(self, now: float) -> bool:
        return now - self._bubble_start < _BUBBLE_MS or 0 <= now - self._hearts_start < _HEARTS_MS

    # ── helpers ───────────────────────────────────────────────────

    def _init_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setToolTip("Click: meow · Double-click: ♥ · Drag: move · "
                        "Right-drag: place (manual) · Right-click: menu")

    def _apply_size(self) -> None:
        self._bubble_h = max(14, round(self._anim.sprite_height * BUBBLE_HEIGHT_RATIO))
        w, h = self._anim.sprite_width, self._anim.sprite_height + self._bubble_h
        self.setFixedSize(w, h)
        self._move.set_size(w, h)

    def _scale(self) -> float:
        return self._anim.display_size / CAT_DISPLAY_SIZE

    def _start_walk(self, target_x: float) -> None:
        if not self._move.is_walking:
            # The previous tick may be up to MAX_IDLE_TICK_MS old; don't let the
            # first step of the walk cover that whole interval (visible lurch).
            self._last_tick = _now_ms()
        self._move.walk_to(target_x, WALK_SPEED_PX_PER_SEC * self._scale())
        self._behavior.set_walking(self._move.is_walking)
        self._kick()

    def _after_drop(self) -> None:
        self._move.set_position(self.x(), self.y())
        center = QPoint(self.x() + self.width() // 2, self.y() + self.height() // 2)
        if QGuiApplication.screenAt(center) is None:
            # Dropped into a gap between monitors: snap onto the nearest valid spot.
            lo, hi = self._move.bounds()
            self._move.set_position(min(max(self.x(), lo), hi), self.y())
        self._move.clamp_vertical()
        self.move(self._move.x, self._move.y)
        back = self._move.out_of_bounds_x()
        if back is not None:
            self._start_walk(back)            # partly off-screen: walk back in

    def _on_single_click(self) -> None:
        was_asleep = self._behavior.base == CatState.SLEEP
        self.user_interacted.emit()           # may wake the cat (plays "wake")
        if was_asleep:
            return
        if self._behavior.trigger("jump"):
            self.show_reaction(CLICK_REACTIONS[self._click_count % len(CLICK_REACTIONS)])
            self._click_count += 1
