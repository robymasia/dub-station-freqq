"""Sample player.

Loads WAV / MP3 (and other formats supported by soundfile / librosa),
keeps a playlist and lets the user trigger one-shot or looping playback
with an independent volume. Playback is rendered block-by-block from the
audio callback so it stays perfectly in sync with the engine.
"""

import os
import threading

import numpy as np

try:
    import soundfile as sf
except Exception:  # pragma: no cover
    sf = None

try:
    import librosa
except Exception:  # pragma: no cover
    librosa = None


class SampleClip:
    """A single loaded audio sample resampled to the engine sample-rate."""

    def __init__(self, path: str, data: np.ndarray, samplerate: int):
        self.path = path
        self.name = os.path.basename(path)
        self.data = data          # shape (frames, 2) float32
        self.samplerate = samplerate

    @property
    def frames(self) -> int:
        return self.data.shape[0]


class Sampler:
    def __init__(self, samplerate: int = 44100):
        self.samplerate = samplerate
        self._lock = threading.Lock()

        self.playlist = []          # list[SampleClip]
        self.selected = 0           # currently highlighted index
        self.volume = 0.8
        self.loop = False

        # Playback state.
        self._playing = False
        self._play_index = -1       # which clip is playing
        self._pos = 0               # read position within clip

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    def load(self, path: str) -> bool:
        """Load an audio file and append it to the playlist."""
        try:
            data, sr = self._read_file(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[Sampler] Failed to load '{path}': {exc}")
            return False

        # Resample if necessary.
        if sr != self.samplerate:
            data = self._resample(data, sr, self.samplerate)

        # Ensure stereo float32 shape (frames, 2).
        data = self._to_stereo(data)

        clip = SampleClip(path, data, self.samplerate)
        with self._lock:
            self.playlist.append(clip)
        return True

    def _read_file(self, path):
        if sf is not None:
            try:
                data, sr = sf.read(path, dtype="float32", always_2d=True)
                return data, sr
            except Exception:
                pass
        if librosa is not None:
            data, sr = librosa.load(path, sr=None, mono=False)
            if data.ndim == 1:
                data = data[None, :]
            return data.T.astype(np.float32), sr
        raise RuntimeError("No audio backend available (soundfile/librosa).")

    @staticmethod
    def _resample(data, sr_in, sr_out):
        if librosa is not None:
            # librosa expects (channels, samples) or mono.
            arr = data.T if data.ndim == 2 else data
            res = librosa.resample(arr, orig_sr=sr_in, target_sr=sr_out)
            return res.T if res.ndim == 2 else res
        # Fallback: linear interpolation.
        ratio = sr_out / sr_in
        n_out = int(round(data.shape[0] * ratio))
        idx = np.linspace(0, data.shape[0] - 1, n_out)
        if data.ndim == 1:
            return np.interp(idx, np.arange(data.shape[0]), data).astype(np.float32)
        out = np.zeros((n_out, data.shape[1]), dtype=np.float32)
        for ch in range(data.shape[1]):
            out[:, ch] = np.interp(idx, np.arange(data.shape[0]), data[:, ch])
        return out

    @staticmethod
    def _to_stereo(data):
        if data.ndim == 1:
            data = np.column_stack([data, data])
        elif data.shape[1] == 1:
            data = np.column_stack([data[:, 0], data[:, 0]])
        elif data.shape[1] > 2:
            data = data[:, :2]
        return np.ascontiguousarray(data, dtype=np.float32)

    def remove(self, index: int):
        with self._lock:
            if 0 <= index < len(self.playlist):
                self.playlist.pop(index)
                if self._play_index == index:
                    self._playing = False
                    self._play_index = -1

    def clear(self):
        with self._lock:
            self.playlist.clear()
            self._playing = False
            self._play_index = -1

    # ------------------------------------------------------------------ #
    # Transport
    # ------------------------------------------------------------------ #
    def set_selected(self, index: int):
        with self._lock:
            if 0 <= index < len(self.playlist):
                self.selected = index

    def scroll(self, delta: int):
        with self._lock:
            if self.playlist:
                self.selected = int(np.clip(self.selected + delta, 0,
                                            len(self.playlist) - 1))

    def set_volume(self, val: float):
        self.volume = float(np.clip(val, 0.0, 1.0))

    def set_loop(self, state: bool):
        self.loop = bool(state)

    def trigger(self, index: int = None):
        """Start playback of `index` (or the selected clip)."""
        with self._lock:
            if index is None:
                index = self.selected
            if 0 <= index < len(self.playlist):
                self._play_index = index
                self._pos = 0
                self._playing = True

    def play(self):
        self.trigger(self.selected)

    def stop(self):
        with self._lock:
            self._playing = False
            self._pos = 0

    @property
    def is_playing(self) -> bool:
        return self._playing

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def render(self, frames: int) -> np.ndarray:
        """Render `frames` samples of the currently playing clip (stereo)."""
        out = np.zeros((frames, 2), dtype=np.float32)
        with self._lock:
            if not self._playing or self._play_index < 0:
                return out
            if self._play_index >= len(self.playlist):
                self._playing = False
                return out

            clip = self.playlist[self._play_index]
            data = clip.data
            total = clip.frames
            pos = self._pos
            vol = self.volume
            written = 0

            while written < frames:
                remaining_out = frames - written
                remaining_clip = total - pos
                n = min(remaining_out, remaining_clip)
                out[written:written + n] += data[pos:pos + n] * vol
                pos += n
                written += n
                if pos >= total:
                    if self.loop:
                        pos = 0
                    else:
                        self._playing = False
                        break
            self._pos = pos
        return out
