"""Tape Echo / delay.

A circular-buffer delay line with feedback and a light tape-style soft
saturation in the feedback path to emulate the warmth of an analog tape
echo unit.

Parameters:
    feedback : 0 .. 0.95   amount of signal fed back into the delay line
    rate     : 0.05 .. 1.0 seconds  (delay time)
    mix      : 0 .. 1      dry/wet mix
"""

import threading

import numpy as np

from ._kernels import tape_echo_process


class TapeEcho:
    def __init__(self, samplerate: int = 44100, max_delay: float = 2.0):
        self.samplerate = samplerate
        self._lock = threading.Lock()

        self.max_len = int(samplerate * max_delay)
        self.buffer = np.zeros((self.max_len, 2), dtype=np.float32)
        self.write_idx = 0

        self.feedback = 0.35
        self.rate = 0.35        # seconds
        self.mix = 0.0
        self._delay_samples = int(self.rate * samplerate)

    # ------------------------------------------------------------------ #
    def set_feedback(self, val: float):
        self.feedback = float(np.clip(val, 0.0, 0.95))

    def set_rate(self, seconds: float):
        seconds = float(np.clip(seconds, 0.05, 1.0))
        self.rate = seconds
        with self._lock:
            self._delay_samples = max(1, int(seconds * self.samplerate))

    def set_mix(self, val: float):
        self.mix = float(np.clip(val, 0.0, 1.0))

    @staticmethod
    def _saturate(x: np.ndarray) -> np.ndarray:
        """Soft clipping (tanh) for gentle tape saturation."""
        return np.tanh(x * 1.5) * 0.85

    # ------------------------------------------------------------------ #
    def process(self, x: np.ndarray) -> np.ndarray:
        if self.mix <= 0.0 and self.feedback <= 0.0:
            return x
        if x.ndim == 1:
            x = x[:, None]
        frames, chans = x.shape

        out = x.copy()

        with self._lock:
            x32 = np.ascontiguousarray(x, dtype=np.float32)
            out = np.ascontiguousarray(out, dtype=np.float32)
            self.write_idx = tape_echo_process(
                x32, out, self.buffer, self.write_idx,
                self._delay_samples, self.feedback, self.mix)

        return out

    def clear(self):
        with self._lock:
            self.buffer[:] = 0.0
            self.write_idx = 0
