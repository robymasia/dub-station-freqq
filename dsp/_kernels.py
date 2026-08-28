"""Numba-accelerated DSP kernels with pure-Python/NumPy fallbacks.

The reverb comb/all-pass filters, the tape-echo delay line and the TPT
state-variable filter all contain per-sample feedback loops that cannot
be vectorised. On CPython these loops are far too slow for real-time
audio, so we JIT-compile them with :mod:`numba` when it is available.

If numba is *not* installed the code still runs correctly (identical
results) using the plain Python implementations — just slower. Every
kernel therefore has two definitions selected at import time.

All kernels are pure functions operating on contiguous ``float32``/``float64``
NumPy arrays and returning the updated running-state so the caller can
persist it between blocks.
"""

import numpy as np

try:
    from numba import njit
    HAVE_NUMBA = True
except Exception:  # pragma: no cover
    HAVE_NUMBA = False

    def njit(*args, **kwargs):
        """No-op decorator fallback when numba is unavailable."""
        def _wrap(fn):
            return fn
        if args and callable(args[0]):
            return args[0]
        return _wrap


# ---------------------------------------------------------------------- #
# Freeverb comb filter (one-pole damping in the feedback loop)
# ---------------------------------------------------------------------- #
@njit(cache=True, fastmath=True)
def comb_process(inp, buffer, index, filterstore, feedback, damp1, damp2):
    n = inp.shape[0]
    out = np.empty(n, dtype=np.float32)
    size = buffer.shape[0]
    idx = index
    fs = filterstore
    for i in range(n):
        y = buffer[idx]
        fs = (y * damp2) + (fs * damp1)
        buffer[idx] = inp[i] + fs * feedback
        out[i] = y
        idx += 1
        if idx >= size:
            idx = 0
    return out, idx, fs


# ---------------------------------------------------------------------- #
# Freeverb all-pass filter
# ---------------------------------------------------------------------- #
@njit(cache=True, fastmath=True)
def allpass_process(inp, buffer, index, feedback):
    n = inp.shape[0]
    out = np.empty(n, dtype=np.float32)
    size = buffer.shape[0]
    idx = index
    for i in range(n):
        bufout = buffer[idx]
        y = -inp[i] + bufout
        buffer[idx] = inp[i] + bufout * feedback
        out[i] = y
        idx += 1
        if idx >= size:
            idx = 0
    return out, idx


# ---------------------------------------------------------------------- #
# Tape echo delay line (stereo) with tanh saturation in feedback
# ---------------------------------------------------------------------- #
@njit(cache=True, fastmath=True)
def tape_echo_process(x, out, buffer, write_idx, delay, feedback, mix):
    frames = x.shape[0]
    chans = x.shape[1]
    maxlen = buffer.shape[0]
    widx = write_idx
    nch = 2 if chans >= 2 else chans
    for i in range(frames):
        ridx = widx - delay
        if ridx < 0:
            ridx += maxlen
        for ch in range(nch):
            delayed = buffer[ridx, ch]
            new_val = x[i, ch] + delayed * feedback
            # tanh soft-clip tape saturation
            buffer[widx, ch] = np.tanh(new_val * 1.5) * 0.85
            out[i, ch] = x[i, ch] * (1.0 - mix) + delayed * mix
        widx += 1
        if widx >= maxlen:
            widx = 0
    return widx


# ---------------------------------------------------------------------- #
# TPT state-variable filter (per channel)
# ---------------------------------------------------------------------- #
@njit(cache=True, fastmath=True)
def tpt_process(col, out, ic1eq, ic2eq, a1, a2, a3, k, lp_mode):
    n = col.shape[0]
    ic1 = ic1eq
    ic2 = ic2eq
    for i in range(n):
        v0 = col[i]
        v3 = v0 - ic2
        v1 = a1 * ic1 + a2 * v3
        v2 = ic2 + a2 * ic1 + a3 * v3
        ic1 = 2.0 * v1 - ic1
        ic2 = 2.0 * v2 - ic2
        if lp_mode:
            out[i] = v2
        else:
            out[i] = v0 - k * v1 - v2
    return ic1, ic2


def warmup():
    """Trigger numba compilation up-front so the first audio block does
    not incur the JIT latency (called from a background thread)."""
    if not HAVE_NUMBA:
        return
    try:
        buf = np.zeros(64, dtype=np.float32)
        inp = np.zeros(32, dtype=np.float32)
        comb_process(inp, buf, 0, 0.0, 0.5, 0.5, 0.5)
        allpass_process(inp, buf, 0, 0.5)
        x = np.zeros((32, 2), dtype=np.float32)
        out = np.zeros((32, 2), dtype=np.float32)
        sbuf = np.zeros((128, 2), dtype=np.float32)
        tape_echo_process(x, out, sbuf, 0, 16, 0.4, 0.4)
        col = np.zeros(32, dtype=np.float32)
        oc = np.zeros(32, dtype=np.float32)
        tpt_process(col, oc, 0.0, 0.0, 0.1, 0.1, 0.1, 1.0, True)
    except Exception:  # pragma: no cover
        pass
