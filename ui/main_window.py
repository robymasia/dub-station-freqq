"""Main application window for DubStation FreQQ.

Assembles all sections (music sources, spectrum analysers, dub siren,
4-band isolator, reverb, tape echo, dub filter, sampler, master/routing)
into a single professional dark-themed layout inspired by Amp FreQQ v3,
and wires every control to the :class:`AudioEngine` and
:class:`MIDIHandler`.
"""

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QLabel, QPushButton, QComboBox,
    QGridLayout, QVBoxLayout, QHBoxLayout, QDialog, QListWidget,
    QFileDialog, QMessageBox, QCheckBox, QDialogButtonBox, QListWidgetItem,
)

from ui.styles import MAIN_STYLE, COLORS, section_title_style
from ui.widgets import Knob, LedButton, SpectrumAnalyzer, Fader, VUMeter


def _panel(title=None, color=None):
    """Create a styled section panel frame with an optional title."""
    frame = QFrame()
    frame.setObjectName("Panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(8, 6, 8, 8)
    layout.setSpacing(4)
    if title:
        lbl = QLabel(title.upper())
        lbl.setObjectName("SectionTitle")
        if color:
            lbl.setStyleSheet(section_title_style(color))
        layout.addWidget(lbl)
    return frame, layout


def _knob_row(*knobs):
    row = QHBoxLayout()
    row.setSpacing(2)
    row.setContentsMargins(0, 0, 0, 0)
    for k in knobs:
        row.addWidget(k, alignment=Qt.AlignCenter)
    w = QWidget()
    w.setLayout(row)
    return w


# ====================================================================== #
# Device settings dialog
# ====================================================================== #
class DeviceDialog(QDialog):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("Audio Device Settings")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Input device (external line-in or system "
                                "loopback):"))
        self.in_combo = QComboBox()
        self._inputs = engine.list_input_devices()
        if self._inputs:
            for idx, label, loop in self._inputs:
                self.in_combo.addItem(label, (idx, loop))
        else:
            self.in_combo.addItem("<no input devices found>", (None, False))
        layout.addWidget(self.in_combo)

        layout.addWidget(QLabel("Output device:"))
        self.out_combo = QComboBox()
        self._outputs = engine.list_output_devices()
        if self._outputs:
            for idx, label in self._outputs:
                self.out_combo.addItem(label, idx)
        else:
            self.out_combo.addItem("<no output devices found>", None)
        layout.addWidget(self.out_combo)

        info = QLabel("Tip: on Windows choose a [Loopback] entry to process "
                      "the system audio (WASAPI). The engine restarts when "
                      "you apply.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#9a9a9a; font-size:10px;")
        layout.addWidget(info)

        btns = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Close)
        btns.button(QDialogButtonBox.Apply).clicked.connect(self._apply)
        btns.button(QDialogButtonBox.Close).clicked.connect(self.accept)
        layout.addWidget(btns)

    def _apply(self):
        in_data = self.in_combo.currentData()
        out_data = self.out_combo.currentData()
        if in_data is not None:
            idx, loop = in_data
            self.engine.set_input_device(idx, loop)
        self.engine.set_output_device(out_data)
        ok = self.engine.restart()
        if not ok:
            QMessageBox.warning(self, "Audio", "Could not start audio stream:\n"
                                f"{self.engine.last_error}")
        else:
            QMessageBox.information(self, "Audio", "Audio stream running.")


# ====================================================================== #
# MIDI dialog
# ====================================================================== #
class MidiDialog(QDialog):
    def __init__(self, midi, parent=None):
        super().__init__(parent)
        self.midi = midi
        self.setWindowTitle("MIDI Settings")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("MIDI input port:"))
        self.combo = QComboBox()
        self._ports = midi.list_ports()
        if self._ports:
            for i, name in enumerate(self._ports):
                self.combo.addItem(name, i)
        else:
            self.combo.addItem("<no MIDI devices found>", None)
        layout.addWidget(self.combo)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#9a9a9a; font-size:10px;")
        layout.addWidget(self.status)

        mapping = QLabel(
            "Default CC map: 1-4 Levels, 5-8 Kills, 9-11 Echo, 12-13 Reverb, "
            "14-15 Filter, 16-17 Siren, 18 Siren On, 19 Master, 20-22 Sources."
            "\nRight-click any knob/button and choose 'MIDI Learn' to remap.")
        mapping.setWordWrap(True)
        mapping.setStyleSheet("color:#9a9a9a; font-size:10px;")
        layout.addWidget(mapping)

        btns = QDialogButtonBox(QDialogButtonBox.Open | QDialogButtonBox.Close)
        btns.button(QDialogButtonBox.Open).setText("Connect")
        btns.button(QDialogButtonBox.Open).clicked.connect(self._connect)
        btns.button(QDialogButtonBox.Close).clicked.connect(self.accept)
        layout.addWidget(btns)

        if not self.midi.available():
            self.status.setText(f"python-rtmidi unavailable: "
                                f"{self.midi.import_error()}")

    def _connect(self):
        idx = self.combo.currentData()
        if idx is None:
            self.status.setText("No MIDI device to connect.")
            return
        if self.midi.open_port(idx):
            self.status.setText(f"Connected: {self.midi.port_name}")
        else:
            self.status.setText(f"Failed: {self.midi.last_error}")


# ====================================================================== #
# Main window
# ====================================================================== #
class MainWindow(QMainWindow):
    def __init__(self, engine, midi):
        super().__init__()
        self.engine = engine
        self.midi = midi

        self.setWindowTitle("DubStation FreQQ")
        self.setStyleSheet(MAIN_STYLE)
        self.resize(1180, 800)

        # Registry of learnable controls: target -> widget.
        self._controls = {}

        central = QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        root.addWidget(self._build_topbar())

        # Upper row: sources | spectrum | siren.
        upper = QHBoxLayout()
        upper.setSpacing(8)
        upper.addWidget(self._build_sources(), 2)
        upper.addWidget(self._build_spectrum(), 5)
        upper.addWidget(self._build_siren(), 2)
        root.addLayout(upper)

        # Isolator (full width).
        root.addWidget(self._build_isolator())

        # FX row: reverb | echo | filter.
        fx = QHBoxLayout()
        fx.setSpacing(8)
        fx.addWidget(self._build_reverb(), 1)
        fx.addWidget(self._build_echo(), 1)
        fx.addWidget(self._build_filter(), 1)
        root.addLayout(fx)

        # Sampler.
        root.addWidget(self._build_sampler())

        # Master / routing strip.
        root.addWidget(self._build_master())

        # Wire MIDI callbacks.
        self.midi.param_callback = self._on_midi_param
        self.midi.note_callback = self._on_midi_note

        # Refresh timer (~30 fps) for meters / spectrum.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_visuals)
        self.timer.start(33)

    # ------------------------------------------------------------------ #
    # Control registration helper
    # ------------------------------------------------------------------ #
    def _register(self, widget, target):
        self._controls[target] = widget
        if hasattr(widget, "learnRequested"):
            widget.learnRequested.connect(self._begin_learn)

    def _begin_learn(self, target):
        if not self.midi.available():
            QMessageBox.information(self, "MIDI Learn",
                                    "python-rtmidi is not available.")
            return
        if self.midi.midi_in is None:
            QMessageBox.information(
                self, "MIDI Learn",
                "Connect a MIDI device first (MIDI button).")
            return
        self.statusBar().showMessage(
            f"MIDI Learn armed for '{target}': move a control on your "
            f"MIDI device…", 8000)
        self.midi.arm_learn(target, self._learn_done)

    def _learn_done(self, target, cc):
        # Called from MIDI thread — use a simple status update.
        self.statusBar().showMessage(f"Mapped CC{cc} -> {target}", 5000)

    # ------------------------------------------------------------------ #
    # Top bar
    # ------------------------------------------------------------------ #
    def _build_topbar(self):
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(58)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 4, 12, 4)

        logo_box = QVBoxLayout()
        logo_box.setSpacing(0)
        logo = QLabel("DubStation FreQQ")
        logo.setObjectName("Logo")
        sub = QLabel("REAL-TIME DUB STATION")
        sub.setObjectName("LogoSub")
        logo_box.addWidget(logo)
        logo_box.addWidget(sub)
        lay.addLayout(logo_box)

        lay.addStretch(1)

        self.status_lbl = QLabel("● audio: stopped")
        self.status_lbl.setStyleSheet("color:#ff6060; font-size:10px;")
        lay.addWidget(self.status_lbl)
        lay.addSpacing(12)

        dev_btn = QPushButton("Device Settings")
        dev_btn.clicked.connect(self._open_devices)
        midi_btn = QPushButton("MIDI")
        midi_btn.clicked.connect(self._open_midi)
        about_btn = QPushButton("About")
        about_btn.clicked.connect(self._open_about)
        for b in (dev_btn, midi_btn, about_btn):
            lay.addWidget(b)
        return bar

    # ------------------------------------------------------------------ #
    # Music sources
    # ------------------------------------------------------------------ #
    def _build_sources(self):
        panel, lay = _panel("Music Sources", COLORS["sources"])

        knobs = QHBoxLayout()
        knobs.setSpacing(2)
        self.src_knobs = []
        for i in range(3):
            k = Knob(f"SRC{i+1}", 0.0, 2.0, 1.0, color="white",
                     target=f"source{i+1}_gain")
            k.valueChanged.connect(lambda v, idx=i:
                                   self.engine.set_source_gain(idx, v))
            self._register(k, f"source{i+1}_gain")
            self.src_knobs.append(k)
            knobs.addWidget(k)
        auto = Knob("AUTO GAIN", 0.0, 4.0, 1.0, color="yellow",
                    target="auto_gain")
        auto.valueChanged.connect(self.engine.set_auto_gain)
        self._register(auto, "auto_gain")
        knobs.addWidget(auto)
        lay.addLayout(knobs)

        # Source select buttons (A/B style active source).
        sel_row = QHBoxLayout()
        sel_row.setSpacing(4)
        self.src_select = []
        for i in range(3):
            b = LedButton(f"SEL{i+1}", color="#40c040",
                          target=f"select_src{i+1}")
            b.toggled.connect(lambda st, idx=i: self._select_source(idx, st))
            self.src_select.append(b)
            sel_row.addWidget(b)
        self.src_select[0].setChecked(True, emit=False)
        lay.addLayout(sel_row)
        return panel

    def _select_source(self, idx, state):
        if state:
            self.engine.set_active_source(idx)
            for i, b in enumerate(self.src_select):
                if i != idx:
                    b.setChecked(False, emit=False)

    # ------------------------------------------------------------------ #
    # Spectrum analysers
    # ------------------------------------------------------------------ #
    def _build_spectrum(self):
        panel, lay = _panel("Spectrum Analyzers", "#c0c0c0")
        row = QHBoxLayout()
        row.setSpacing(6)
        self.spec_sub = SpectrumAnalyzer(
            "SUB", COLORS["isolator"],
            provider=lambda: self.engine.get_tap("sub"),
            samplerate=self.engine.samplerate)
        self.spec_reverb = SpectrumAnalyzer(
            "REVERB", COLORS["reverb"],
            provider=lambda: self.engine.get_tap("reverb"),
            samplerate=self.engine.samplerate)
        self.spec_echo = SpectrumAnalyzer(
            "ECHO", COLORS["echo"],
            provider=lambda: self.engine.get_tap("echo"),
            samplerate=self.engine.samplerate)
        for s in (self.spec_sub, self.spec_reverb, self.spec_echo):
            row.addWidget(s)
        lay.addLayout(row)
        return panel

    # ------------------------------------------------------------------ #
    # Dub siren
    # ------------------------------------------------------------------ #
    def _build_siren(self):
        panel, lay = _panel("Dub Siren", COLORS["siren"])
        knobs = QHBoxLayout()
        speed = Knob("SPEED", 0.1, 10.0, 2.0, color="cyan",
                     target="siren_speed")
        speed.valueChanged.connect(self.engine.siren.set_speed)
        self._register(speed, "siren_speed")
        pitch = Knob("PITCH", 100.0, 2000.0, 440.0, color="cyan",
                     target="siren_pitch", unit="Hz", log=True)
        pitch.valueChanged.connect(self.engine.siren.set_pitch)
        self._register(pitch, "siren_pitch")
        mix = Knob("MIX", 0.0, 1.0, 0.4, color="cyan",
                   target="siren_mix", unit="%")
        mix.valueChanged.connect(self.engine.siren.set_mix)
        self._register(mix, "siren_mix")
        knobs.addWidget(speed)
        knobs.addWidget(pitch)
        knobs.addWidget(mix)
        lay.addLayout(knobs)

        self.siren_btn = LedButton("SIREN ON/OFF", color="#00ccff",
                                   target="siren_onoff")
        self.siren_btn.toggled.connect(self.engine.siren.set_on)
        self._register(self.siren_btn, "siren_onoff")
        lay.addWidget(self.siren_btn)
        return panel

    # ------------------------------------------------------------------ #
    # 4-band isolator
    # ------------------------------------------------------------------ #
    def _build_isolator(self):
        panel, lay = _panel("4-Band Isolator", COLORS["isolator"])
        grid = QGridLayout()
        grid.setSpacing(6)

        bands = [("SUB", "sub"), ("BASS", "bass"),
                 ("MIDS", "mids"), ("TOPS", "tops")]
        self.kill_btns = {}
        self.iso_knobs = {}
        for col, (label, key) in enumerate(bands):
            kill = LedButton(f"{label} KILL", color="#f0c040",
                             target=f"kill_{key}")
            kill.toggled.connect(lambda st, k=key:
                                 self.engine.isolator.set_kill(k, st))
            self._register(kill, f"kill_{key}")
            self.kill_btns[key] = kill
            grid.addWidget(kill, 0, col)

            knob = Knob(f"{label} LVL", -60.0, 6.0, 0.0, color="yellow",
                        target=f"level_{key}", unit="dB")
            knob.valueChanged.connect(
                lambda v, k=key: self.engine.isolator.set_gain_db(k, v))
            self._register(knob, f"level_{key}")
            # Set initial gain to 0 dB.
            self.engine.isolator.set_gain_db(key, 0.0)
            self.iso_knobs[key] = knob
            grid.addWidget(knob, 1, col, alignment=Qt.AlignCenter)

        lay.addLayout(grid)
        return panel

    # ------------------------------------------------------------------ #
    # Reverb
    # ------------------------------------------------------------------ #
    def _build_reverb(self):
        panel, lay = _panel("Reverb", COLORS["reverb"])
        knobs = QHBoxLayout()
        send = Knob("SEND", 0.0, 1.0, 0.0, color="green",
                    target="reverb_send", unit="%")
        send.valueChanged.connect(self.engine.reverb.set_send)
        self._register(send, "reverb_send")
        decay = Knob("DECAY", 0.0, 1.0, 0.5, color="green",
                     target="reverb_decay", unit="%")
        decay.valueChanged.connect(self.engine.reverb.set_decay)
        self._register(decay, "reverb_decay")
        knobs.addWidget(send)
        knobs.addWidget(decay)
        lay.addLayout(knobs)

        btns = QHBoxLayout()
        bpf = LedButton("BPF", color="#40c040", target="reverb_bpf")
        bpf.toggled.connect(self.engine.reverb.set_bpf)
        self._register(bpf, "reverb_bpf")
        hpf = LedButton("HPF", color="#40c040", target="reverb_hpf")
        hpf.toggled.connect(self.engine.reverb.set_hpf)
        self._register(hpf, "reverb_hpf")
        btns.addWidget(bpf)
        btns.addWidget(hpf)
        lay.addLayout(btns)
        return panel

    # ------------------------------------------------------------------ #
    # Tape echo
    # ------------------------------------------------------------------ #
    def _build_echo(self):
        panel, lay = _panel("Tape Echo", COLORS["echo"])
        knobs = QHBoxLayout()
        fbk = Knob("FBK", 0.0, 0.95, 0.35, color="orange",
                   target="echo_feedback", unit="%")
        fbk.valueChanged.connect(self.engine.echo.set_feedback)
        self._register(fbk, "echo_feedback")
        rate = Knob("RATE", 0.05, 1.0, 0.35, color="orange",
                    target="echo_rate", unit="s")
        rate.valueChanged.connect(self.engine.echo.set_rate)
        self._register(rate, "echo_rate")
        mix = Knob("MIX", 0.0, 1.0, 0.0, color="orange",
                   target="echo_mix", unit="%")
        mix.valueChanged.connect(self.engine.echo.set_mix)
        self._register(mix, "echo_mix")
        knobs.addWidget(fbk)
        knobs.addWidget(rate)
        knobs.addWidget(mix)
        lay.addLayout(knobs)
        lay.addStretch(1)
        return panel

    # ------------------------------------------------------------------ #
    # Dub filter
    # ------------------------------------------------------------------ #
    def _build_filter(self):
        panel, lay = _panel("Dub Filter", COLORS["filter"])
        knobs = QHBoxLayout()
        cut = Knob("CUTOFF", 20.0, 20000.0, 20000.0, color="red",
                   target="filter_cutoff", unit="Hz", log=True)
        cut.valueChanged.connect(self.engine.filter.set_cutoff)
        self._register(cut, "filter_cutoff")
        res = Knob("RES", 0.5, 8.0, 0.707, color="red",
                   target="filter_resonance")
        res.valueChanged.connect(self.engine.filter.set_resonance)
        self._register(res, "filter_resonance")
        knobs.addWidget(cut)
        knobs.addWidget(res)
        lay.addLayout(knobs)

        btns = QHBoxLayout()
        self.filt_lp = LedButton("LP", color="#ff4040", target="filter_lp")
        self.filt_hp = LedButton("HP", color="#ff4040", target="filter_hp")
        self.filt_lp.setChecked(True, emit=False)
        self.filt_lp.toggled.connect(lambda st: self._set_filter_mode("LP", st))
        self.filt_hp.toggled.connect(lambda st: self._set_filter_mode("HP", st))
        self._register(self.filt_lp, "filter_lp")
        self._register(self.filt_hp, "filter_hp")
        btns.addWidget(self.filt_lp)
        btns.addWidget(self.filt_hp)
        lay.addLayout(btns)
        return panel

    def _set_filter_mode(self, mode, state):
        if state:
            self.engine.filter.set_mode(mode)
            if mode == "LP":
                self.filt_hp.setChecked(False, emit=False)
            else:
                self.filt_lp.setChecked(False, emit=False)

    # ------------------------------------------------------------------ #
    # Sampler
    # ------------------------------------------------------------------ #
    def _build_sampler(self):
        panel, lay = _panel("Sampler", "#c0c0c0")
        row = QHBoxLayout()
        row.setSpacing(8)

        self.playlist = QListWidget()
        self.playlist.setFixedHeight(90)
        self.playlist.currentRowChanged.connect(
            self.engine.sampler.set_selected)
        row.addWidget(self.playlist, 3)

        btns = QVBoxLayout()
        btns.setSpacing(4)
        load = QPushButton("LOAD")
        load.clicked.connect(self._load_samples)
        play = QPushButton("PLAY")
        play.setObjectName("Accent")
        play.clicked.connect(self.engine.sampler.play)
        stop = QPushButton("STOP")
        stop.clicked.connect(self.engine.sampler.stop)
        trig = QPushButton("TRIGGER")
        trig.clicked.connect(lambda: self.engine.sampler.trigger())
        for b in (load, play, stop, trig):
            btns.addWidget(b)
        row.addLayout(btns, 1)

        ctrl = QVBoxLayout()
        self.loop_btn = LedButton("LOOP", color="#40c040", target="sampler_loop")
        self.loop_btn.toggled.connect(self.engine.sampler.set_loop)
        vol = Knob("VOLUME", 0.0, 1.0, 0.8, color="white",
                   target="sampler_volume", unit="%")
        vol.valueChanged.connect(self.engine.sampler.set_volume)
        self._register(vol, "sampler_volume")
        ctrl.addWidget(self.loop_btn)
        ctrl.addWidget(vol, alignment=Qt.AlignCenter)
        row.addLayout(ctrl, 1)

        lay.addLayout(row)
        return panel

    def _load_samples(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Load audio samples", os.path.expanduser("~"),
            "Audio Files (*.wav *.mp3 *.flac *.ogg *.aiff);;All Files (*)")
        for f in files:
            if self.engine.sampler.load(f):
                clip = self.engine.sampler.playlist[-1]
                QListWidgetItem(clip.name, self.playlist)
        if self.playlist.count() and self.playlist.currentRow() < 0:
            self.playlist.setCurrentRow(0)

    # ------------------------------------------------------------------ #
    # Master / routing strip
    # ------------------------------------------------------------------ #
    def _build_master(self):
        panel = QFrame()
        panel.setObjectName("Panel")
        lay = QHBoxLayout(panel)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(12)

        # Routing toggles.
        self.echo_on = LedButton("ECHO ON", color="#ff6600", target="rt_echo")
        self.echo_on.setChecked(True, emit=False)
        self.echo_on.toggled.connect(
            lambda st: setattr(self.engine, "echo_enabled", st))
        self.rev_on = LedButton("REV ON", color="#40c040", target="rt_reverb")
        self.rev_on.setChecked(True, emit=False)
        self.rev_on.toggled.connect(
            lambda st: setattr(self.engine, "reverb_enabled", st))
        self.sir_on = LedButton("SIR ON", color="#00ccff", target="rt_siren")
        self.sir_on.setChecked(True, emit=False)
        self.sir_on.toggled.connect(
            lambda st: setattr(self.engine, "siren_enabled", st))
        self.iso_on = LedButton("ISO ON", color="#f0c040", target="rt_iso")
        self.iso_on.setChecked(True, emit=False)
        self.iso_on.toggled.connect(
            lambda st: setattr(self.engine, "isolator_enabled", st))
        self.filt_on = LedButton("FILT ON", color="#ff4040", target="rt_filt")
        self.filt_on.setChecked(True, emit=False)
        self.filt_on.toggled.connect(
            lambda st: setattr(self.engine, "filter_enabled", st))

        for b in (self.iso_on, self.echo_on, self.rev_on,
                  self.filt_on, self.sir_on):
            lay.addWidget(b)

        lay.addStretch(1)

        # Master fader + VU.
        mbox = QVBoxLayout()
        mbox.setSpacing(2)
        mlbl = QLabel("MASTER")
        mlbl.setStyleSheet(section_title_style(COLORS["master"]))
        mbox.addWidget(mlbl)
        self.master_fader = Fader(0.0, 2.0, 1.0, color="#f0c040",
                                  target="master_level")
        self.master_fader.valueChanged.connect(self.engine.set_master_gain)
        self._register(self.master_fader, "master_level")
        mbox.addWidget(self.master_fader)
        lay.addLayout(mbox, 2)

        self.vu = VUMeter(2, orientation=Qt.Horizontal)
        self.vu.setFixedWidth(180)
        lay.addWidget(self.vu)
        return panel

    # ------------------------------------------------------------------ #
    # Visual refresh (30 fps)
    # ------------------------------------------------------------------ #
    def _refresh_visuals(self):
        try:
            self.spec_sub.refresh()
            self.spec_reverb.refresh()
            self.spec_echo.refresh()
            l, r = self.engine.get_meter()
            self.vu.set_levels(l, r)
            if self.engine.running:
                self.status_lbl.setText("● audio: running")
                self.status_lbl.setStyleSheet(
                    "color:#40c040; font-size:10px;")
            else:
                self.status_lbl.setText("● audio: stopped")
                self.status_lbl.setStyleSheet(
                    "color:#ff6060; font-size:10px;")
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ #
    # MIDI callbacks (called from MIDI thread — keep them lightweight)
    # ------------------------------------------------------------------ #
    def _on_midi_param(self, target, value_norm):
        widget = self._controls.get(target)
        if widget is None:
            return
        # Toggles (kill/onoff) — treat >0.5 as pressed.
        if isinstance(widget, LedButton):
            widget.setChecked(value_norm >= 0.5)
        elif hasattr(widget, "setValueNormalized"):
            widget.setValueNormalized(value_norm)

    def _on_midi_note(self, note, velocity, on):
        if on:
            # Note number selects sample index and triggers it.
            idx = note % 128
            if idx < len(self.engine.sampler.playlist):
                self.engine.sampler.trigger(idx)

    # ------------------------------------------------------------------ #
    # Dialogs
    # ------------------------------------------------------------------ #
    def _open_devices(self):
        DeviceDialog(self.engine, self).exec()

    def _open_midi(self):
        MidiDialog(self.midi, self).exec()

    def _open_about(self):
        QMessageBox.about(
            self, "About DubStation FreQQ",
            "<h3>DubStation FreQQ</h3>"
            "<p>Real-time digital dub station inspired by Amp FreQQ v3.</p>"
            "<p>4-band isolator, Freeverb reverb, tape echo, resonant dub "
            "filter, dual-LFO dub siren and a sample player — all controllable "
            "in real time via mouse and MIDI.</p>"
            "<p>Built with PySide6, sounddevice, NumPy/SciPy and "
            "python-rtmidi.</p>")

    # ------------------------------------------------------------------ #
    def closeEvent(self, event):
        try:
            self.timer.stop()
            self.engine.stop()
            self.midi.close()
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(event)
