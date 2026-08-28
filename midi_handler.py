"""MIDI input handling for DubStation FreQQ.

Uses python-rtmidi to receive Control Change (CC) and Note messages and
maps them to engine parameters. Also implements a simple *MIDI Learn*
mechanism: arm learn for a named target, move a controller, and the next
incoming CC is bound to that target.

The default CC map follows the specification in the project brief.
"""

import threading

try:
    import rtmidi
except Exception as exc:  # pragma: no cover
    rtmidi = None
    _RTMIDI_IMPORT_ERROR = exc
else:
    _RTMIDI_IMPORT_ERROR = None


# Default CC -> target name mapping (see project spec).
DEFAULT_CC_MAP = {
    1: "level_sub",
    2: "level_bass",
    3: "level_mids",
    4: "level_tops",
    5: "kill_sub",
    6: "kill_bass",
    7: "kill_mids",
    8: "kill_tops",
    9: "echo_feedback",
    10: "echo_rate",
    11: "echo_mix",
    12: "reverb_send",
    13: "reverb_decay",
    14: "filter_cutoff",
    15: "filter_resonance",
    16: "siren_speed",
    17: "siren_pitch",
    18: "siren_onoff",
    19: "master_level",
    20: "source1_gain",
    21: "source2_gain",
    22: "source3_gain",
}


class MIDIHandler:
    """Wraps an rtmidi input port and dispatches mapped messages."""

    def __init__(self):
        self._lock = threading.Lock()
        self.midi_in = None
        self.port_name = None
        self.last_error = None

        # cc -> target ; and reverse for learn feedback.
        self.cc_map = dict(DEFAULT_CC_MAP)

        # Learn state.
        self._learn_target = None
        self._learn_callback = None

        # Callbacks registered by the app:
        #   param_callback(target: str, value_norm: float)
        #   note_callback(note: int, velocity: int, on: bool)
        self.param_callback = None
        self.note_callback = None

    # ------------------------------------------------------------------ #
    @staticmethod
    def available() -> bool:
        return rtmidi is not None

    @staticmethod
    def import_error():
        return _RTMIDI_IMPORT_ERROR

    def list_ports(self):
        if rtmidi is None:
            return []
        try:
            mi = rtmidi.MidiIn()
            ports = mi.get_ports()
            mi.delete()
            return ports
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            return []

    # ------------------------------------------------------------------ #
    def open_port(self, index: int) -> bool:
        if rtmidi is None:
            self.last_error = f"python-rtmidi unavailable: {_RTMIDI_IMPORT_ERROR}"
            return False
        self.close()
        try:
            self.midi_in = rtmidi.MidiIn()
            ports = self.midi_in.get_ports()
            if not ports or index >= len(ports):
                self.last_error = "No MIDI input ports available."
                self.midi_in.delete()
                self.midi_in = None
                return False
            self.midi_in.open_port(index)
            self.port_name = ports[index]
            self.midi_in.set_callback(self._on_message)
            self.last_error = None
            print(f"[MIDIHandler] Opened MIDI port: {self.port_name}")
            return True
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            print(f"[MIDIHandler] Failed to open port: {exc}")
            return False

    def close(self):
        if self.midi_in is not None:
            try:
                self.midi_in.close_port()
                self.midi_in.delete()
            except Exception:  # noqa: BLE001
                pass
        self.midi_in = None
        self.port_name = None

    # ------------------------------------------------------------------ #
    # MIDI Learn
    # ------------------------------------------------------------------ #
    def arm_learn(self, target: str, done_callback=None):
        """Arm MIDI learn for `target`. Next CC will be bound to it."""
        with self._lock:
            self._learn_target = target
            self._learn_callback = done_callback

    def cancel_learn(self):
        with self._lock:
            self._learn_target = None
            self._learn_callback = None

    def unbind(self, target: str):
        with self._lock:
            for cc, tgt in list(self.cc_map.items()):
                if tgt == target:
                    del self.cc_map[cc]

    # ------------------------------------------------------------------ #
    # Message dispatch
    # ------------------------------------------------------------------ #
    def _on_message(self, event, data=None):
        message, _delta = event
        if not message:
            return
        status = message[0] & 0xF0

        # Control Change.
        if status == 0xB0 and len(message) >= 3:
            cc = message[1]
            value = message[2]
            self._handle_cc(cc, value)

        # Note On / Off.
        elif status == 0x90 and len(message) >= 3:
            note, vel = message[1], message[2]
            if vel > 0:
                if self.note_callback:
                    self.note_callback(note, vel, True)
            else:
                if self.note_callback:
                    self.note_callback(note, vel, False)
        elif status == 0x80 and len(message) >= 3:
            note, vel = message[1], message[2]
            if self.note_callback:
                self.note_callback(note, vel, False)

    def _handle_cc(self, cc: int, value: int):
        # MIDI learn takes priority.
        with self._lock:
            learn_target = self._learn_target
            learn_cb = self._learn_callback

        if learn_target is not None:
            with self._lock:
                # Remove any previous binding of this target.
                for c, tgt in list(self.cc_map.items()):
                    if tgt == learn_target:
                        del self.cc_map[c]
                self.cc_map[cc] = learn_target
                self._learn_target = None
                self._learn_callback = None
            if learn_cb:
                learn_cb(learn_target, cc)
            return

        target = self.cc_map.get(cc)
        if target and self.param_callback:
            self.param_callback(target, value / 127.0)
