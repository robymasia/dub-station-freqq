"""VU meter widget (stereo).

Displays two horizontal (or vertical) level bars with the classic
green / yellow / red segmentation and a peak-hold indicator. Levels are
pushed in as linear 0..1 peak values via :meth:`set_levels`.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class VUMeter(QWidget):
    def __init__(self, channels=2, orientation=Qt.Horizontal, parent=None):
        super().__init__(parent)
        self._channels = channels
        self._orient = orientation
        self._levels = [0.0] * channels
        self._peaks = [0.0] * channels
        if orientation == Qt.Horizontal:
            self.setMinimumSize(120, 22)
        else:
            self.setMinimumSize(22, 120)

    def set_levels(self, *levels):
        for i, lv in enumerate(levels[:self._channels]):
            lv = max(0.0, min(1.0, float(lv)))
            self._levels[i] = lv
            if lv > self._peaks[i]:
                self._peaks[i] = lv
            else:
                self._peaks[i] = max(self._peaks[i] - 0.015, 0.0)
        self.update()

    def _seg_color(self, frac):
        if frac > 0.85:
            return QColor("#ff3030")
        if frac > 0.65:
            return QColor("#f0c040")
        return QColor("#40c040")

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#0a0a0a"))
        p.setPen(QPen(QColor("#222222"), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        n = self._channels
        n_seg = 20

        if self._orient == Qt.Horizontal:
            ch_h = (h - 4) / n
            seg_w = (w - 6) / n_seg
            for ch in range(n):
                y = 2 + ch * ch_h
                level = self._levels[ch]
                peak = self._peaks[ch]
                for s in range(n_seg):
                    frac = (s + 1) / n_seg
                    x = 3 + s * seg_w
                    lit = frac <= level
                    col = self._seg_color(frac)
                    if not lit:
                        col = col.darker(320)
                    p.fillRect(QRectF(x, y + 1, seg_w - 1.5, ch_h - 2), col)
                # peak marker
                ps = int(peak * n_seg)
                if ps > 0:
                    x = 3 + min(ps, n_seg - 1) * seg_w
                    p.fillRect(QRectF(x, y + 1, seg_w - 1.5, ch_h - 2),
                               QColor("#ffffff"))
        else:
            ch_w = (w - 4) / n
            seg_h = (h - 6) / n_seg
            for ch in range(n):
                x = 2 + ch * ch_w
                level = self._levels[ch]
                for s in range(n_seg):
                    frac = (s + 1) / n_seg
                    y = h - 3 - (s + 1) * seg_h
                    lit = frac <= level
                    col = self._seg_color(frac)
                    if not lit:
                        col = col.darker(320)
                    p.fillRect(QRectF(x + 1, y, ch_w - 2, seg_h - 1.5), col)
        p.end()
