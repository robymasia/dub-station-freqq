"""Horizontal / vertical fader widget.

A styled slider used for the master level (and reusable elsewhere). It
wraps drawing in QPainter for a professional mixer look and emits
`valueChanged(float)` in the configured range.
"""

from PySide6.QtCore import Qt, Signal, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QLinearGradient
from PySide6.QtWidgets import QWidget, QMenu


class Fader(QWidget):
    valueChanged = Signal(float)
    learnRequested = Signal(str)

    def __init__(self, minimum=0.0, maximum=1.0, default=0.8,
                 color="#f0c040", orientation=Qt.Horizontal,
                 target="master_level", parent=None):
        super().__init__(parent)
        self._min = float(minimum)
        self._max = float(maximum)
        self._default = float(default)
        self._value = float(default)
        self._color = QColor(color)
        self._orient = orientation
        self._target = target
        self._dragging = False

        if orientation == Qt.Horizontal:
            self.setMinimumSize(160, 28)
        else:
            self.setMinimumSize(28, 140)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self):
        return QSize(200, 28) if self._orient == Qt.Horizontal else QSize(28, 160)

    def target(self):
        return self._target

    def value(self):
        return self._value

    def setValue(self, val, emit=True):
        val = max(self._min, min(self._max, float(val)))
        self._value = val
        self.update()
        if emit:
            self.valueChanged.emit(val)

    def setValueNormalized(self, norm, emit=True):
        norm = max(0.0, min(1.0, norm))
        self.setValue(self._min + norm * (self._max - self._min), emit)

    def _normalized(self):
        if self._max == self._min:
            return 0.0
        return (self._value - self._min) / (self._max - self._min)

    # ------------------------------------------------------------------ #
    def _value_from_pos(self, pos):
        if self._orient == Qt.Horizontal:
            norm = (pos.x() - 6) / max(1, (self.width() - 12))
        else:
            norm = 1.0 - (pos.y() - 6) / max(1, (self.height() - 12))
        self.setValueNormalized(norm)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._value_from_pos(event.position())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._value_from_pos(event.position())
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self.setValue(self._default)
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        learn = menu.addAction("MIDI Learn")
        if menu.exec(event.globalPos()) == learn:
            self.learnRequested.emit(self._target)

    # ------------------------------------------------------------------ #
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        norm = self._normalized()

        if self._orient == Qt.Horizontal:
            track = QRectF(6, h / 2 - 3, w - 12, 6)
            p.setBrush(QBrush(QColor("#1a1a1a")))
            p.setPen(QPen(QColor("#333333"), 1))
            p.drawRoundedRect(track, 3, 3)

            fill = QRectF(6, h / 2 - 3, (w - 12) * norm, 6)
            grad = QLinearGradient(6, 0, w - 6, 0)
            grad.setColorAt(0.0, self._color.darker(150))
            grad.setColorAt(1.0, self._color)
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(fill, 3, 3)

            hx = 6 + (w - 12) * norm
            handle = QRectF(hx - 5, h / 2 - 10, 10, 20)
            p.setBrush(QBrush(QColor("#d8d8d8")))
            p.setPen(QPen(QColor("#000000"), 1))
            p.drawRoundedRect(handle, 3, 3)
        else:
            track = QRectF(w / 2 - 3, 6, 6, h - 12)
            p.setBrush(QBrush(QColor("#1a1a1a")))
            p.setPen(QPen(QColor("#333333"), 1))
            p.drawRoundedRect(track, 3, 3)

            fh = (h - 12) * norm
            fill = QRectF(w / 2 - 3, 6 + (h - 12) - fh, 6, fh)
            p.setBrush(QBrush(self._color))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(fill, 3, 3)

            hy = 6 + (h - 12) * (1.0 - norm)
            handle = QRectF(w / 2 - 10, hy - 5, 20, 10)
            p.setBrush(QBrush(QColor("#d8d8d8")))
            p.setPen(QPen(QColor("#000000"), 1))
            p.drawRoundedRect(handle, 3, 3)
        p.end()
