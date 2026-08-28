"""Real-time audio engine for DubStation FreQQ.

Wraps a `sounddevice` duplex/stream and runs the full DSP chain in the
audio callback:

    input -> isolator -> reverb -> echo -> filter -> siren mix
          -> sampler mix -> master gain -> output

The engine is designed to be robust:
    * gracefully handles the absence of any audio device (headless dev
      machines, CI, etc.) without crashing;
    * supports selecting the input device (external line-in) and, on
      Windows, a WASAPI *loopback* device to capture the system audio;
    * exposes a small ring buffer of the latest output samples for the
      spectrum analysers / VU meter (lock-light, single producer).

All heavy DSP objects live in :mod:`dsp`.
"""

import threading

import numpy as np

try:
    import sounddevice as sd
except Exception as exc:  # pragma: no cover
    sd = None
    _SD_IMPORT_ERROR = exc
else:
    _SD_IMPORT_ERROR = None

from dsp import Isolator, Reverb, TapeEcho, DubFilter, Siren, Sampler


class AudioEngine:
    """Full-duplex real-time DSP engine."""

    def __init__(self, samplerate: int = 44100, blocksize: int = 512,
                 channels: int = 2):
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.channels = channels

        self._lock = threading.Lock()
        self.stream = None
        self.running = False
        self.last_error = None

        # Selected devices (indexes into sd.query_devices()).
        self.input_device = None
        self.output_device = None
        self.use_loopback = False

        # ---- DSP chain -------------------------------------------------
        self.isolator = Isolator(samplerate)
        self.reverb = Reverb(samplerate)
        self.echo = TapeEcho(samplerate)
        self.filter = DubFilter(samplerate)
        self.siren = Siren(samplerate)
        self.sampler = Sampler(samplerate)

        # ---- Master + routing toggles ---------------------------------
        self.master_gain = 1.0
        self.echo_enabled = True
        self.reverb_enabled = True
        self.siren_enabled = True
        self.isolator_enabled = True
        self.filter_enabled = True

        # Music source gains (SRC1/2/3) and auto gain.
        self.source_gain = [1.0, 1.0, 1.0]
        self.active_source = 0
        self.auto_gain = 1.0

        # ---- Metering / analysis --------------------------------------
        self._meter_peak = np.zeros(2, dtype=np.float32)
        self._scope_lock = threading.Lock()
        self._scope_buffer = np.zeros(4096, dtype=np.float32)
        # Per-tap buffers for the 3 spectrum analysers.
        self._tap_sub = np.zeros(2048, dtype=np.float32)
        self._tap_reverb = np.zeros(2048, dtype=np.float32)
        self._tap_echo = np.zeros(2048, dtype=np.float32)

    # ------------------------------------------------------------------ #
    # Device discovery
    # ------------------------------------------------------------------ #
    @staticmethod
    def available() -> bool:
        return sd is not None

    @staticmethod
    def import_error():
        return _SD_IMPORT_ERROR

    def list_input_devices(self):
        """Return list of (index, label, is_loopback) for input devices."""
        devices = []
        if sd is None:
            return devices
        try:
            hostapis = sd.query_hostapis()
            for i, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    api = hostapis[dev["hostapi"]]["name"]
                    devices.append((i, f"{dev['name']} [{api}]", False))
            # WASAPI loopback: expose output devices as loopback inputs.
            for i, dev in enumerate(sd.query_devices()):
                api = hostapis[dev["hostapi"]]["name"]
                if "WASAPI" in api and dev.get("max_output_channels", 0) > 0:
                    devices.append(
                        (i, f"[Loopback] {dev['name']} [{api}]", True))
        except Exception as exc:  # noqa: BLE001
            print(f"[AudioEngine] Could not query input devices: {exc}")
        return devices

    def list_output_devices(self):
        devices = []
        if sd is None:
            return devices
        try:
            hostapis = sd.query_hostapis()
            for i, dev in enumerate(sd.query_devices()):
                if dev.get("max_output_channels", 0) > 0:
                    api = hostapis[dev["hostapi"]]["name"]
                    devices.append((i, f"{dev['name']} [{api}]"))
        except Exception as exc:  # noqa: BLE001
            print(f"[AudioEngine] Could not query output devices: {exc}")
        return devices

    def set_input_device(self, index, loopback=False):
        self.input_device = index
        self.use_loopback = loopback

    def set_output_device(self, index):
        self.output_device = index

    # ------------------------------------------------------------------ #
    # Parameter setters
    # ------------------------------------------------------------------ #
    def set_master_gain(self, val: float):
        self.master_gain = float(np.clip(val, 0.0, 2.0))

    def set_source_gain(self, idx: int, val: float):
        if 0 <= idx < 3:
            self.source_gain[idx] = float(np.clip(val, 0.0, 2.0))

    def set_active_source(self, idx: int):
        if 0 <= idx < 3:
            self.active_source = idx

    def set_auto_gain(self, val: float):
        self.auto_gain = float(np.clip(val, 0.0, 4.0))

    # ------------------------------------------------------------------ #
    # Stream lifecycle
    # ------------------------------------------------------------------ #
    def start(self):
        """Open and start the audio stream. Returns True on success."""
        if sd is None:
            self.last_error = f"sounddevice unavailable: {_SD_IMPORT_ERROR}"
            print(f"[AudioEngine] {self.last_error}")
            return False
        if self.running:
            return True

        extra = None
        in_dev = self.input_device
        try:
            if self.use_loopback and hasattr(sd, "WasapiSettings"):
                # WASAPI loopback capture of an output device.
                extra = sd.WasapiSettings(loopback=True)
        except Exception:  # noqa: BLE001
            extra = None

        try:
            self.stream = sd.Stream(
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                dtype="float32",
                channels=self.channels,
                device=(in_dev, self.output_device),
                callback=self._callback,
                extra_settings=extra,
                latency="low",
            )
            self.stream.start()
            self.running = True
            self.last_error = None
            print("[AudioEngine] Stream started.")
            return True
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            self.stream = None
            print(f"[AudioEngine] Failed to start stream: {exc}")
            return False

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as exc:  # noqa: BLE001
                print(f"[AudioEngine] Error stopping stream: {exc}")
        self.stream = None
        self.running = False
        print("[AudioEngine] Stream stopped.")

    def restart(self):
        self.stop()
        return self.start()

    # ------------------------------------------------------------------ #
    # Audio callback — runs on the real-time thread
    # ------------------------------------------------------------------ #
    def _callback(self, indata, outdata, frames, time_info, status):
        if status:
            # Underruns/overruns — print but keep going.
            pass

        try:
            x = np.asarray(indata, dtype=np.float32)
            if x.ndim == 1:
                x = x[:, None]
            if x.shape[1] < 2:
                x = np.column_stack([x[:, 0], x[:, 0]])

            # Apply active source gain + auto gain.
            src_g = self.source_gain[self.active_source] * self.auto_gain
            x = x * src_g

            # --- DSP chain -------------------------------------------
            if self.isolator_enabled:
                x = self.isolator.process(x)

            # Tap for SUB spectrum (post-isolator low content).
            self._push_tap(self._tap_sub, x)

            if self.reverb_enabled:
                x = self.reverb.process(x)
            self._push_tap(self._tap_reverb, x)

            if self.echo_enabled:
                x = self.echo.process(x)
            self._push_tap(self._tap_echo, x)

            if self.filter_enabled:
                x = self.filter.process(x)

            if self.siren_enabled:
                x = self.siren.process(x)

            # Mix sampler output.
            samp = self.sampler.render(frames)
            if samp is not None and samp.shape[0] == frames:
                x[:, 0] += samp[:, 0]
                x[:, 1] += samp[:, 1]

            # Master gain + soft limiter.
            x *= self.master_gain
            np.clip(x, -1.0, 1.0, out=x)

            # Metering + scope.
            self._update_meter(x)
            self._push_scope(x)

            # Write to output (match output channel count).
            out_ch = outdata.shape[1] if outdata.ndim > 1 else 1
            if out_ch >= 2:
                outdata[:, 0] = x[:, 0]
                outdata[:, 1] = x[:, 1]
                for ch in range(2, out_ch):
                    outdata[:, ch] = x[:, 0]
            else:
                outdata[:, 0] = x.mean(axis=1)
        except Exception as exc:  # noqa: BLE001
            # Never raise from the audio thread — output silence.
            outdata.fill(0.0)
            self.last_error = f"callback error: {exc}"

    # ------------------------------------------------------------------ #
    # Metering helpers
    # ------------------------------------------------------------------ #
    def _update_meter(self, x):
        peak = np.abs(x).max(axis=0)
        # Simple peak-hold with decay.
        self._meter_peak = np.maximum(self._meter_peak * 0.85, peak)

    def get_meter(self):
        return float(self._meter_peak[0]), float(self._meter_peak[1])

    def _push_scope(self, x):
        mono = x.mean(axis=1)
        with self._scope_lock:
            n = mono.shape[0]
            self._scope_buffer = np.roll(self._scope_buffer, -n)
            self._scope_buffer[-n:] = mono

    def _push_tap(self, buf, x):
        mono = x.mean(axis=1)
        n = mono.shape[0]
        if n >= buf.shape[0]:
            buf[:] = mono[-buf.shape[0]:]
        else:
            buf[:-n] = buf[n:]
            buf[-n:] = mono

    def get_scope(self):
        with self._scope_lock:
            return self._scope_buffer.copy()

    def get_tap(self, name: str):
        return {
            "sub": self._tap_sub,
            "reverb": self._tap_reverb,
            "echo": self._tap_echo,
        }.get(name, self._scope_buffer).copy()
