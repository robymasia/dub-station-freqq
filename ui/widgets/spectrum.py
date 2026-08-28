"""Real-time spectrum analyser widget.

Computes an FFT of a supplied mono sample buffer (via a provider
callback) and draws coloured frequency bars on a black background. The
widget refreshes at ~30 fps using a QTimer owned by the parent (the
parent calls :meth:`update_data`), or it can pull data itself if given a
`provider` callable.
"""

import numpy as np

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QFont, QPen
from PySide6.QtWidgets import QWidget


class SpectrumAnalyzer(QWidget):
    def __init__(self, title="", color="#00ccff", n_bars=28,
                 provider=None, samplerate=44100, parent=None):
        super().__init__(parent)
        self._title = title
        self._color = QColor(color)
        self._n_bars = n_bars
        self._provider = provider
        self._samplerate = samplerate

        self._bar_vals = np.zeros(n_bars, dtype=np.float32)
        self._peak_vals = np.zeros(n_bars, dtype=np.float32)

        self.setMinimumSize(150, 90)

    def set_provider(self, provider):
        self._provider = provider

    # ------------------------------------------------------------------ #
    def refresh(self):
        """Pull new samples from the provider and recompute the FFT."""
        if self._provider is None:
            return
        try:
            samples = self._provider()
        except Exception:  # noqa: BLE001
            return
        if samples is None or len(samples) < 64:
            return
        self.update_data(samples)

    def update_data(self, samples: np.ndarray):
        samples = np.asarray(samples, dtype=np.float32)
        n = len(samples)
        # Windowed FFT.
        window = np.hanning(n)
        spec = np.abs(np.fft.rfft(samples * window))
        freqs = np.fft.rfftfreq(n, 1.0 / self._samplerate)

        # Logarithmic frequency band grouping.
        f_min, f_max = 30.0, self._samplerate / 2.0
        edges = np.logspace(np.log10(f_min), np.log10(f_max),
                            self._n_bars + 1)
        vals = np.zeros(self._n_bars, dtype=np.float32)
        for i in range(self._n_bars):
            mask = (freqs >= edges[i]) & (freqs < edges[i + 1])
            if np.any(mask):
                vals[i] = spec[mask].mean()

        # Convert to dB-ish scale, normalise.
        vals = 20.0 * np.log10(vals + 1e-6)
        vals = np.clip((vals + 60.0) / 60.0, 0.0, 1.0)

        # Smoothing (attack fast, release slow).
        for i in range(self._n_bars):
            if vals[i] > self._bar_vals[i]:
                self._bar_vals[i] = vals[i]
            else:
                self._bar_vals[i] *= 0.80
                self._bar_vals[i] = max(self._bar_vals[i], vals[i])
            if self._bar_vals[i] > self._peak_vals[i]:
                self._peak_vals[i] = self._bar_vals[i]
            else:
                self._peak_vals[i] = max(self._peak_vals[i] - 0.02, 0.0)
        self.update()

    # ------------------------------------------------------------------ #
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()

        # Background.
        p.fillRect(self.rect(), QColor("#0a0a0a"))
        p.setPen(QPen(QColor("#222222"), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        # Title.
        p.setPen(QColor(self._color))
        font = QFont("Segoe UI", 7)
        font.setBold(True)
        p.setFont(font)
        p.drawText(QRectF(4, 2, w - 8, 12), Qt.AlignLeft, self._title.upper())

        top = 16
        plot_h = h - top - 4
        bar_area = w - 8
        bar_w = bar_area / self._n_bars

        grad = QLinearGradient(0, top + plot_h, 0, top)
        grad.setColorAt(0.0, self._color.darker(160))
        grad.setColorAt(0.6, self._color)
        grad.setColorAt(1.0, self._color.lighter(150))

        for i in range(self._n_bars):
            val = self._bar_vals[i]
            bh = val * plot_h
            x = 4 + i * bar_w
            p.fillRect(QRectF(x, top + plot_h - bh, bar_w - 1.5, bh), grad)
            # Peak marker.
            pv = self._peak_vals[i]
            py = top + plot_h - pv * plot_h
            p.fillRect(QRectF(x, py, bar_w - 1.5, 1.5),
                       self._color.lighter(160))
        p.end()
