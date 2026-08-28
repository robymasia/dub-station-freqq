"""Resonant Dub Filter.

A state-variable / TPT (Topology Preserving Transform) filter after
Zavalishin / Andrew Simper. TPT filters are unconditionally stable even
when the cutoff is modulated at audio rate which makes them ideal for a
performance oriented dub filter that is swept aggressively.

Parameters:
    cutoff    : 20 .. 20000 Hz (log scale controlled from the UI)
    resonance : 0.5 .. 8.0  (Q)
    mode      : "LP" (low-pass) or "HP" (high-pass)
"""

import threading

import numpy as np

from ._kernels import tpt_process


class DubFilter:
    def __init__(self, samplerate: int = 44100):
        self.samplerate = samplerate
        self._lock = threading.Lock()

        self._cutoff = 20000.0
        self._res = 0.707
        self.mode = "LP"
        self.enabled = True

        # TPT state variables per channel (integrator states).
        self._ic1eq = [0.0, 0.0]
        self._ic2eq = [0.0, 0.0]

        self._update_coeffs()

    # ------------------------------------------------------------------ #
    def _update_coeffs(self):
        # g = tan(pi * fc / fs); k = 1/Q
        fc = float(np.clip(self._cutoff, 20.0, self.samplerate * 0.49))
        self._g = float(np.tan(np.pi * fc / self.samplerate))
        self._k = float(1.0 / max(0.5, self._res))
        self._a1 = 1.0 / (1.0 + self._g * (self._g + self._k))
        self._a2 = self._g * self._a1
        self._a3 = self._g * self._a2

    def set_cutoff(self, hz: float):
        self._cutoff = float(np.clip(hz, 20.0, 20000.0))
        with self._lock:
            self._update_coeffs()

    def set_resonance(self, q: float):
        self._res = float(np.clip(q, 0.5, 8.0))
        with self._lock:
            self._update_coeffs()

    def set_mode(self, mode: str):
        m = str(mode).upper()
        if m in ("LP", "HP"):
            self.mode = m

    def set_enabled(self, state: bool):
        self.enabled = bool(state)

    def reset(self):
        with self._lock:
            self._ic1eq = [0.0, 0.0]
            self._ic2eq = [0.0, 0.0]

    # ------------------------------------------------------------------ #
    def process(self, x: np.ndarray) -> np.ndarray:
        if not self.enabled:
            return x
        if x.ndim == 1:
            x = x[:, None]
        frames, chans = x.shape
        out = np.empty_like(x)

        with self._lock:
            a1, a2, a3, k = self._a1, self._a2, self._a3, self._k
            lp_mode = self.mode == "LP"
            for ch in range(min(chans, 2)):
                col = np.ascontiguousarray(x[:, ch], dtype=np.float32)
                res = np.empty(frames, dtype=np.float32)
                self._ic1eq[ch], self._ic2eq[ch] = tpt_process(
                    col, res, self._ic1eq[ch], self._ic2eq[ch],
                    a1, a2, a3, k, lp_mode)
                out[:, ch] = res

            # Mirror mono to any extra channels.
            for ch in range(2, chans):
                out[:, ch] = out[:, 0]

        return out
