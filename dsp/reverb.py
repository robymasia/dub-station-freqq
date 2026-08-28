"""Freeverb style reverb.

A simplified implementation of Jezar's Freeverb algorithm:
    * 8 parallel comb filters (with internal low-pass damping) per channel
    * 4 series all-pass filters per channel

Parameters exposed:
    send  : dry/wet mix (0..1)
    decay : room size / feedback amount (0..1)
    bpf   : enable a band-pass style pre-filter (HPF + LPF) on the wet path
    hpf   : enable a high-pass pre-filter on the wet path
"""

import threading

import numpy as np
from scipy import signal

from ._kernels import comb_process, allpass_process

# Freeverb tuning constants (samples @ 44.1 kHz). Slight stereo spread added.
_COMB_TUNING = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617]
_ALLPASS_TUNING = [556, 441, 341, 225]
_STEREO_SPREAD = 23

# Canonical Freeverb output make-up gain applied to the wet signal.
# BUGFIX: the wet path only had the 0.015 input "fixedgain" but was missing
# Jezar's output "scalewet" (3.0). Without it the reverb tail came out about
# 10 dB too quiet (~-28 dB below the dry signal even at SEND = 1.0), so the
# effect sounded like it was barely doing anything / "not working".
_SCALE_WET = 3.0


class _Comb:
    """Comb filter with a one-pole low-pass in the feedback loop (damping)."""

    def __init__(self, size: int):
        self.buffer = np.zeros(size, dtype=np.float32)
        self.size = size
        self.index = 0
        self.filterstore = 0.0
        self.feedback = 0.5
        self.damp1 = 0.5
        self.damp2 = 0.5

    def set_damp(self, val: float):
        self.damp1 = val
        self.damp2 = 1.0 - val

    def process(self, inp: np.ndarray) -> np.ndarray:
        out, self.index, self.filterstore = comb_process(
            inp, self.buffer, self.index, self.filterstore,
            self.feedback, self.damp1, self.damp2)
        return out


class _Allpass:
    def __init__(self, size: int):
        self.buffer = np.zeros(size, dtype=np.float32)
        self.size = size
        self.index = 0
        self.feedback = 0.5

    def process(self, inp: np.ndarray) -> np.ndarray:
        out, self.index = allpass_process(
            inp, self.buffer, self.index, self.feedback)
        return out


class Reverb:
    """Stereo Freeverb reverb."""

    def __init__(self, samplerate: int = 44100):
        self.samplerate = samplerate
        self._lock = threading.Lock()

        self.send = 0.0      # dry/wet
        self.decay = 0.5     # room size
        self.damp = 0.5
        self.width = 1.0
        self.bpf = False
        self.hpf = False

        scale = samplerate / 44100.0
        self._combs = [[], []]
        self._allpasses = [[], []]
        for ch in range(2):
            spread = 0 if ch == 0 else _STEREO_SPREAD
            for t in _COMB_TUNING:
                self._combs[ch].append(_Comb(max(1, int((t + spread) * scale))))
            for t in _ALLPASS_TUNING:
                ap = _Allpass(max(1, int((t + spread) * scale)))
                ap.feedback = 0.5
                self._allpasses[ch].append(ap)

        self._update_internal()

        # Pre-filter (band-pass / high-pass on wet path).
        self._design_prefilters()
        self._zi_pre = [signal.sosfilt_zi(self._sos_bpf).copy() for _ in range(2)]
        self._zi_hpf = [signal.sosfilt_zi(self._sos_hpf).copy() for _ in range(2)]

    def _design_prefilters(self):
        nyq = self.samplerate / 2.0
        self._sos_bpf = signal.butter(
            2, [200.0 / nyq, 5000.0 / nyq], btype="bandpass", output="sos")
        self._sos_hpf = signal.butter(
            2, 300.0 / nyq, btype="highpass", output="sos")

    def _update_internal(self):
        # Map decay (0..1) to freeverb roomsize/feedback range.
        roomsize = self.decay * 0.28 + 0.7
        for ch in range(2):
            for c in self._combs[ch]:
                c.feedback = roomsize
                c.set_damp(self.damp)

    # ------------------------------------------------------------------ #
    def set_send(self, val: float):
        self.send = float(np.clip(val, 0.0, 1.0))

    def set_decay(self, val: float):
        self.decay = float(np.clip(val, 0.0, 1.0))
        with self._lock:
            self._update_internal()

    def set_damp(self, val: float):
        self.damp = float(np.clip(val, 0.0, 1.0))
        with self._lock:
            self._update_internal()

    def set_bpf(self, state: bool):
        self.bpf = bool(state)

    def set_hpf(self, state: bool):
        self.hpf = bool(state)

    # ------------------------------------------------------------------ #
    def process(self, x: np.ndarray) -> np.ndarray:
        if self.send <= 0.0:
            return x
        if x.ndim == 1:
            x = x[:, None]
        frames, chans = x.shape

        wet = np.zeros((frames, 2), dtype=np.float32)

        with self._lock:
            # Mono sum feeds the reverb tank (classic freeverb input).
            mono = x.mean(axis=1).astype(np.float32) * 0.015

            for ch in range(2):
                acc = np.zeros(frames, dtype=np.float32)
                for c in self._combs[ch]:
                    acc += c.process(mono)
                for ap in self._allpasses[ch]:
                    acc = ap.process(acc)
                # Apply the Freeverb output make-up gain (see _SCALE_WET).
                wet[:, ch] = acc * _SCALE_WET

            # Optional pre/post filtering on the wet signal.
            if self.hpf:
                for ch in range(2):
                    wet[:, ch], self._zi_hpf[ch] = signal.sosfilt(
                        self._sos_hpf, wet[:, ch], zi=self._zi_hpf[ch])
            if self.bpf:
                for ch in range(2):
                    wet[:, ch], self._zi_pre[ch] = signal.sosfilt(
                        self._sos_bpf, wet[:, ch], zi=self._zi_pre[ch])

        # Mix. Broadcast wet to match input channel count.
        out = x.copy()
        if chans == 1:
            out[:, 0] = x[:, 0] * (1.0 - self.send) + wet[:, 0] * self.send
        else:
            out[:, 0] = x[:, 0] * (1.0 - self.send) + wet[:, 0] * self.send
            out[:, 1] = x[:, 1] * (1.0 - self.send) + wet[:, 1] * self.send
        return out
