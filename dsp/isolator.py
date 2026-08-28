"""4-Band Isolator.

Splits the incoming signal into four frequency bands using 4th order
Butterworth filters (implemented as second-order-sections for numerical
stability) and lets the user kill or attenuate/boost each band
independently.

Bands:
    SUB  : low-pass  < 80 Hz
    BASS : band-pass   80 - 250 Hz
    MIDS : band-pass  250 - 4000 Hz
    TOPS : high-pass > 4000 Hz

The isolator is fully thread-safe: filter states are kept per instance
and parameter updates (kill / level) are simple atomic attribute writes
that are read by the audio callback.
"""

import threading

import numpy as np
from scipy import signal


class Isolator:
    """4-band isolator with per band kill switch and level control."""

    #: Crossover frequencies (Hz)
    SUB_HI = 80.0
    BASS_LO = 80.0
    BASS_HI = 250.0
    MIDS_LO = 250.0
    MIDS_HI = 4000.0
    TOPS_LO = 4000.0

    def __init__(self, samplerate: int = 44100, order: int = 4):
        self.samplerate = samplerate
        self.order = order
        self._lock = threading.Lock()

        # Per-band linear gain (1.0 == 0 dB). Range mapped from -inf..+6 dB.
        self.gain = {"sub": 1.0, "bass": 1.0, "mids": 1.0, "tops": 1.0}
        # Kill switches: True -> band is muted.
        self.kill = {"sub": False, "bass": False, "mids": False, "tops": False}

        self._design_filters()
        self._init_states()

    # ------------------------------------------------------------------ #
    # Filter design / state management
    # ------------------------------------------------------------------ #
    def _design_filters(self):
        """Design the crossover filter network.

        BUGFIX: the previous implementation built four *independent*
        Butterworth filters (low-pass / band-pass / band-pass / high-pass)
        and summed their outputs. Because two overlapping band-pass
        filters are ~180 deg out of phase at their shared crossover, the
        summed output cancelled almost completely at the BASS/MIDS
        crossover (a ~-40 dB notch at 250 Hz) even with every band at 0 dB.
        The isolator therefore coloured the signal heavily instead of
        being transparent when nothing was killed, and killing one band
        changed the level of the neighbouring bands instead of removing a
        single band cleanly.

        The bands are now split with a **Linkwitz-Riley** crossover network
        (the de-facto standard for DJ isolators). A Linkwitz-Riley section
        is a Butterworth section applied twice (``H(z)**2``); the adjacent
        low-pass and high-pass of a crossover are then perfectly in phase,
        so they sum flat (no notch) while each band still rolls off
        steeply. Killing a band now removes exactly that band without
        boosting its neighbours.

        The tree is::

            sub  = LR_LP(80)
            hi80 = LR_HP(80)
                bass = LR_LP(250, hi80)
                hi250 = LR_HP(250, hi80)
                    mids = LR_LP(4000, hi250)
                    tops = LR_HP(4000, hi250)

        A Linkwitz-Riley section is realised by stacking the same
        second-order Butterworth SOS twice, so a single ``sosfilt`` call
        (with a single delay-state) evaluates ``H(z)**2``.
        """
        nyq = self.samplerate / 2.0

        # Guard against invalid frequencies for very low sample rates.
        def _norm(f):
            return min(max(f / nyq, 1e-4), 0.999)

        # Second-order Butterworth prototype -> Linkwitz-Riley (4th order)
        # obtained by cascading (stacking) the section with itself.
        def _lr(freq, btype):
            sos = signal.butter(2, _norm(freq), btype=btype, output="sos")
            return np.vstack([sos, sos])

        self._sos = {
            "lp80": _lr(self.SUB_HI, "lowpass"),
            "hp80": _lr(self.SUB_HI, "highpass"),
            "lp250": _lr(self.BASS_HI, "lowpass"),
            "hp250": _lr(self.BASS_HI, "highpass"),
            "lp4000": _lr(self.MIDS_HI, "lowpass"),
            "hp4000": _lr(self.MIDS_HI, "highpass"),
        }
        # Ordered list of the four bands the UI exposes.
        self._bands = ("sub", "bass", "mids", "tops")

    def _init_states(self):
        """Initialise per-crossover filter delay states (stereo)."""
        self._zi = {}
        for name, sos in self._sos.items():
            # One independent filter state per channel (L, R).
            zi = signal.sosfilt_zi(sos)
            self._zi[name] = [zi.copy(), zi.copy()]

    # ------------------------------------------------------------------ #
    # Parameter setters (thread-safe atomic writes)
    # ------------------------------------------------------------------ #
    def set_gain_db(self, band: str, db: float):
        """Set band level in dB (-60 dB treated as -inf, max +6 dB)."""
        band = band.lower()
        if band not in self.gain:
            return
        if db <= -60.0:
            lin = 0.0
        else:
            lin = float(10.0 ** (min(db, 6.0) / 20.0))
        self.gain[band] = lin

    def set_gain_linear(self, band: str, lin: float):
        band = band.lower()
        if band in self.gain:
            self.gain[band] = float(max(0.0, lin))

    def set_kill(self, band: str, state: bool):
        band = band.lower()
        if band in self.kill:
            self.kill[band] = bool(state)

    def toggle_kill(self, band: str):
        band = band.lower()
        if band in self.kill:
            self.kill[band] = not self.kill[band]
            return self.kill[band]
        return False

    def reset_states(self):
        with self._lock:
            self._init_states()

    # ------------------------------------------------------------------ #
    # Processing
    # ------------------------------------------------------------------ #
    def process(self, x: np.ndarray) -> np.ndarray:
        """Process a stereo block.

        Parameters
        ----------
        x : np.ndarray, shape (frames, 2), float32

        Returns
        -------
        np.ndarray, shape (frames, 2), float32
        """
        if x.ndim == 1:
            x = x[:, None]
        frames, chans = x.shape

        out = np.zeros_like(x)

        with self._lock:
            for ch in range(chans):
                xc = x[:, ch]
                zi = self._zi

                # Linkwitz-Riley crossover tree (see _design_filters).
                sub, zi["lp80"][ch] = signal.sosfilt(
                    self._sos["lp80"], xc, zi=zi["lp80"][ch])
                hi80, zi["hp80"][ch] = signal.sosfilt(
                    self._sos["hp80"], xc, zi=zi["hp80"][ch])

                bass, zi["lp250"][ch] = signal.sosfilt(
                    self._sos["lp250"], hi80, zi=zi["lp250"][ch])
                hi250, zi["hp250"][ch] = signal.sosfilt(
                    self._sos["hp250"], hi80, zi=zi["hp250"][ch])

                mids, zi["lp4000"][ch] = signal.sosfilt(
                    self._sos["lp4000"], hi250, zi=zi["lp4000"][ch])
                tops, zi["hp4000"][ch] = signal.sosfilt(
                    self._sos["hp4000"], hi250, zi=zi["hp4000"][ch])

                bands = {"sub": sub, "bass": bass, "mids": mids, "tops": tops}

                acc = np.zeros(frames, dtype=np.float64)
                for band in self._bands:
                    if self.kill[band]:
                        continue
                    g = self.gain[band]
                    if g == 0.0:
                        continue
                    acc += bands[band] * g

                out[:, ch] = acc.astype(out.dtype)

        return out
