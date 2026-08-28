"""Dub Siren.

A classic dub siren: a sine oscillator whose pitch is modulated by one
LFO and whose amplitude (tremolo) is modulated by a second LFO.

    LFO1 -> pitch modulation (vibrato / sweep)
    LFO2 -> amplitude modulation (tremolo)

Parameters:
    speed : master LFO rate multiplier (scales both LFO rates)
    pitch : base oscillator frequency (100 .. 2000 Hz)
    on    : enable / disable the siren
    mix   : level of the siren mixed into the main signal
"""

import threading

import numpy as np


class Siren:
    def __init__(self, samplerate: int = 44100):
        self.samplerate = samplerate
        self._lock = threading.Lock()

        self.on = False
        self.pitch = 440.0     # base frequency (Hz)
        self.speed = 1.0       # master LFO speed multiplier
        self.mix = 0.4

        # Independent LFO rates (Hz).
        self.lfo1_rate = 2.0   # pitch modulation
        self.lfo2_rate = 5.0   # amplitude modulation (tremolo)
        self.lfo1_depth = 0.5  # pitch mod depth (relative)
        self.lfo2_depth = 0.5  # tremolo depth

        # Running phases.
        self._osc_phase = 0.0
        self._lfo1_phase = 0.0
        self._lfo2_phase = 0.0

    # ------------------------------------------------------------------ #
    def set_on(self, state: bool):
        self.on = bool(state)

    def toggle(self):
        self.on = not self.on
        return self.on

    def set_pitch(self, hz: float):
        self.pitch = float(np.clip(hz, 100.0, 2000.0))

    def set_speed(self, val: float):
        # val expressed in Hz-ish master rate 0.1 .. 10
        self.speed = float(np.clip(val, 0.1, 10.0))

    def set_mix(self, val: float):
        self.mix = float(np.clip(val, 0.0, 1.0))

    def set_lfo1_rate(self, hz: float):
        self.lfo1_rate = float(np.clip(hz, 0.1, 10.0))

    def set_lfo2_rate(self, hz: float):
        self.lfo2_rate = float(np.clip(hz, 0.1, 10.0))

    # ------------------------------------------------------------------ #
    def render(self, frames: int) -> np.ndarray:
        """Render `frames` samples of the siren (mono, float32)."""
        if not self.on:
            return np.zeros(frames, dtype=np.float32)

        with self._lock:
            sr = self.samplerate
            n = np.arange(frames, dtype=np.float64)

            # LFO1 -> pitch modulation.
            l1_inc = 2.0 * np.pi * (self.lfo1_rate * self.speed) / sr
            lfo1 = np.sin(self._lfo1_phase + l1_inc * n)
            self._lfo1_phase = (self._lfo1_phase + l1_inc * frames) % (2 * np.pi)

            # LFO2 -> amplitude (tremolo).
            l2_inc = 2.0 * np.pi * (self.lfo2_rate * self.speed) / sr
            lfo2 = np.sin(self._lfo2_phase + l2_inc * n)
            self._lfo2_phase = (self._lfo2_phase + l2_inc * frames) % (2 * np.pi)

            # Instantaneous frequency of main oscillator.
            inst_freq = self.pitch * (1.0 + self.lfo1_depth * lfo1)
            phase_inc = 2.0 * np.pi * inst_freq / sr
            phases = self._osc_phase + np.cumsum(phase_inc)
            self._osc_phase = float(phases[-1] % (2 * np.pi))

            osc = np.sin(phases)

            # Amplitude modulation (tremolo).
            amp = (1.0 - self.lfo2_depth) + self.lfo2_depth * (0.5 * (lfo2 + 1.0))
            out = (osc * amp).astype(np.float32)

        return out

    def process(self, x: np.ndarray) -> np.ndarray:
        """Mix the siren into a stereo signal block."""
        if not self.on or self.mix <= 0.0:
            return x
        if x.ndim == 1:
            x = x[:, None]
        frames, chans = x.shape
        sir = self.render(frames) * self.mix
        out = x.copy()
        for ch in range(chans):
            out[:, ch] += sir
        return out
