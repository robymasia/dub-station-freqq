"""LED button widget.

A rectangular button with an integrated LED indicator. Can be either a
toggle (latching) or a momentary switch. When ON the LED glows in the
configured colour (default bright yellow #f0c040) with a soft glow.
"""

from PySide6.QtCore import Qt, Signal, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QRadialGradient
from PySide6.QtWidgets import QWidget, QMenu


class LedButton(QWidget):
    toggled = Signal(bool)
    pressed = Signal()
    released = Signal()
    learnRequested = Signal(str)

    def __init__(self, text="", color="#f0c040", momentary=False,
                 target=None, parent=None):
        super().__init__(parent)
        self._text = text
        self._color = QColor(color)
        self._momentary = momentary
        self._state = False
        self._target = target or text.lower().replace(" ", "_")

        self.setMinimumSize(58, 40)
        self.setMaximumHeight(56)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{text} (right-click for MIDI learn)")

    def sizeHint(self):
        return QSize(70, 44)

    def target(self):
        return self._target

    def isChecked(self):
        return self._state

    def setChecked(self, state, emit=True):
        state = bool(state)
        if state != self._state:
            self._state = state
            self.update()
            if emit:
                self.toggled.emit(state)
        else:
            self.update()

    def toggle(self):
        self.setChecked(not self._state)

    # ------------------------------------------------------------------ #
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._momentary:
                self.setChecked(True)
                self.pressed.emit()
            else:
                self.toggle()
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._momentary and event.button() == Qt.LeftButton:
            self.setChecked(False)
            self.released.emit()
            event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        learn = menu.addAction("MIDI Learn")
        action = menu.exec(event.globalPos())
        if action == learn:
            self.learnRequested.emit(self._target)

    # ------------------------------------------------------------------ #
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Button body.
        body = QRectF(2, 2, w - 4, h - 4)
        if self._state:
            p.setBrush(QBrush(QColor("#3a3320")))
            p.setPen(QPen(self._color, 1.5))
        else:
            p.setBrush(QBrush(QColor("#242424")))
            p.setPen(QPen(QColor("#3a3a3a"), 1.5))
        p.drawRoundedRect(body, 5, 5)

        # LED indicator (top-centered small circle).
        led_r = 5
        led_cx = w / 2.0
        led_cy = 12
        if self._state:
            grad = QRadialGradient(led_cx, led_cy, led_r * 2.4)
            grad.setColorAt(0.0, self._color.lighter(140))
            grad.setColorAt(0.5, self._color)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(led_cx - led_r * 2.2, led_cy - led_r * 2.2,
                                 led_r * 4.4, led_r * 4.4))
            p.setBrush(QBrush(self._color.lighter(130)))
            p.drawEllipse(QRectF(led_cx - led_r, led_cy - led_r,
                                 led_r * 2, led_r * 2))
        else:
            p.setBrush(QBrush(QColor("#402d0d")))
            p.setPen(QPen(QColor("#1a1a1a"), 1))
            p.drawEllipse(QRectF(led_cx - led_r, led_cy - led_r,
                                 led_r * 2, led_r * 2))

        # Text.
        p.setPen(QColor("#f0f0f0") if self._state else QColor("#9a9a9a"))
        font = QFont("Segoe UI", 7)
        font.setBold(True)
        p.setFont(font)
        text_rect = QRectF(0, h / 2.0, w, h / 2.0 - 2)
        p.drawText(text_rect, Qt.AlignCenter, self._text.upper())
        p.end()
