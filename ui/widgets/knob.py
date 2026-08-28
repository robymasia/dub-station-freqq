"""Custom rotary knob widget (QPainter based).

Features:
    * dark circular body with a coloured value arc and a pointer;
    * vertical click-drag to change the value;
    * double-click resets to the default value;
    * label underneath showing the name and current value;
    * configurable colour (green / cyan / orange / red / yellow);
    * emits `valueChanged(float)` with the value in the [min, max] range;
    * supports right-click for a "MIDI Learn" context action (handled by
      the parent through the `learnRequested` signal).
"""

import math

from PySide6.QtCore import Qt, Signal, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PySide6.QtWidgets import QWidget, QMenu


COLOR_PRESETS = {
    "green": "#40c040",
    "cyan": "#00ccff",
    "orange": "#ff6600",
    "red": "#ff4040",
    "yellow": "#f0c040",
    "white": "#e0e0e0",
}


class Knob(QWidget):
    valueChanged = Signal(float)
    learnRequested = Signal(str)   # emits the knob's target id

    def __init__(self, name="", minimum=0.0, maximum=1.0, default=0.0,
                 color="cyan", target=None, unit="", log=False, parent=None):
        super().__init__(parent)
        self._name = name
        self._min = float(minimum)
        self._max = float(maximum)
        self._default = float(default)
        self._value = float(default)
        self._color = COLOR_PRESETS.get(color, color)
        self._target = target or name.lower().replace(" ", "_")
        self._unit = unit
        self._log = log

        self._dragging = False
        self._last_y = 0

        self.setMinimumSize(64, 84)
        self.setMaximumSize(96, 110)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setToolTip(f"{name} (drag to adjust, double-click resets,"
                        f" right-click for MIDI learn)")

    # ------------------------------------------------------------------ #
    def sizeHint(self):
        return QSize(72, 92)

    def target(self):
        return self._target

    def value(self):
        return self._value

    def setValue(self, val, emit=True):
        val = max(self._min, min(self._max, float(val)))
        if val != self._value:
            self._value = val
            self.update()
            if emit:
                self.valueChanged.emit(val)
        else:
            self._value = val
            self.update()

    def setValueNormalized(self, norm, emit=True):
        """Set from a 0..1 normalized value (used by MIDI CC)."""
        norm = max(0.0, min(1.0, norm))
        if self._log:
            lo = math.log10(max(1e-6, self._min))
            hi = math.log10(self._max)
            val = 10 ** (lo + norm * (hi - lo))
        else:
            val = self._min + norm * (self._max - self._min)
        self.setValue(val, emit=emit)

    def _normalized(self):
        if self._log:
            lo = math.log10(max(1e-6, self._min))
            hi = math.log10(self._max)
            return (math.log10(max(1e-6, self._value)) - lo) / (hi - lo)
        if self._max == self._min:
            return 0.0
        return (self._value - self._min) / (self._max - self._min)

    # ------------------------------------------------------------------ #
    # Interaction
    # ------------------------------------------------------------------ #
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._last_y = event.position().y()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            dy = self._last_y - event.position().y()
            self._last_y = event.position().y()
            span = self._max - self._min
            # Fine control with Shift.
            speed = 0.0025 if (event.modifiers() & Qt.ShiftModifier) else 0.01
            if self._log:
                norm = self._normalized() + dy * speed
                self.setValueNormalized(norm)
            else:
                self.setValue(self._value + dy * span * speed)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self.setValue(self._default)
        event.accept()

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120.0
        span = self._max - self._min
        if self._log:
            self.setValueNormalized(self._normalized() + steps * 0.03)
        else:
            self.setValue(self._value + steps * span * 0.03)
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        learn = menu.addAction("MIDI Learn")
        reset = menu.addAction("Reset to default")
        action = menu.exec(event.globalPos())
        if action == learn:
            self.learnRequested.emit(self._target)
        elif action == reset:
            self.setValue(self._default)

    # ------------------------------------------------------------------ #
    # Painting
    # ------------------------------------------------------------------ #
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        knob_d = min(w, 56)
        cx = w / 2.0
        cy = 8 + knob_d / 2.0
        radius = knob_d / 2.0

        # Arc geometry: 270 degrees, gap at the bottom.
        start_angle = 225.0     # degrees (Qt: 0 = 3 o'clock, CCW positive)
        span = -270.0
        norm = self._normalized()

        rect = QRectF(cx - radius, cy - radius, knob_d, knob_d)

        # Track arc (background).
        pen = QPen(QColor("#3a3a3a"), 4)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, int(start_angle * 16), int(span * 16))

        # Value arc.
        pen = QPen(QColor(self._color), 4)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, int(start_angle * 16), int(span * norm * 16))

        # Knob body.
        p.setPen(QPen(QColor("#111111"), 1))
        p.setBrush(QBrush(QColor("#2b2b2b")))
        body_r = radius - 6
        p.drawEllipse(QRectF(cx - body_r, cy - body_r, body_r * 2, body_r * 2))

        # Pointer.
        angle_deg = start_angle + span * norm
        angle_rad = math.radians(angle_deg)
        px = cx + math.cos(angle_rad) * (body_r - 3)
        py = cy - math.sin(angle_rad) * (body_r - 3)
        pen = QPen(QColor(self._color), 3)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(int(cx), int(cy), int(px), int(py))

        # Labels.
        p.setPen(QColor("#c8c8c8"))
        font = QFont("Segoe UI", 7)
        font.setBold(True)
        p.setFont(font)
        name_rect = QRectF(0, cy + radius - 2, w, 14)
        p.drawText(name_rect, Qt.AlignCenter, self._name.upper())

        p.setPen(QColor(self._color))
        font2 = QFont("Consolas", 7)
        p.setFont(font2)
        val_rect = QRectF(0, cy + radius + 11, w, 14)
        p.drawText(val_rect, Qt.AlignCenter, self._format_value())

        p.end()

    def _format_value(self):
        v = self._value
        if self._unit == "Hz":
            if v >= 1000:
                return f"{v/1000:.1f}k"
            return f"{v:.0f}Hz"
        if self._unit == "dB":
            return f"{v:+.1f}"
        if self._unit == "%":
            return f"{v*100:.0f}%"
        if self._unit == "s":
            return f"{v*1000:.0f}ms"
        if abs(v) >= 100:
            return f"{v:.0f}"
        return f"{v:.2f}"
