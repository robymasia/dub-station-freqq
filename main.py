"""DubStation FreQQ — application entry point.

Creates the Qt application, initialises the real-time audio engine and
the MIDI handler, shows the main window and handles a clean shutdown
(stopping audio and closing MIDI ports).

Run with:  python main.py
"""

import sys
import signal
import threading

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from audio_engine import AudioEngine
from midi_handler import MIDIHandler
from ui.main_window import MainWindow

try:
    from dsp._kernels import warmup as _kernel_warmup
except Exception:  # noqa: BLE001
    _kernel_warmup = None


SAMPLERATE = 44100
BLOCKSIZE = 512


def main():
    # High-DPI friendly.
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

    app = QApplication(sys.argv)
    app.setApplicationName("DubStation FreQQ")

    # Pre-compile the numba DSP kernels in the background so the first
    # audio blocks don't glitch while the JIT compiles.
    if _kernel_warmup is not None:
        threading.Thread(target=_kernel_warmup, daemon=True).start()

    # --- Engine + MIDI ------------------------------------------------
    engine = AudioEngine(samplerate=SAMPLERATE, blocksize=BLOCKSIZE)
    midi = MIDIHandler()

    # Try to auto-start audio with the default devices. Failure is not
    # fatal — the user can pick devices from Device Settings.
    started = engine.start()

    window = MainWindow(engine, midi)
    window.show()

    if not engine.available():
        QMessageBox.warning(
            window, "Audio",
            "The 'sounddevice' backend is not available on this system.\n"
            f"Details: {engine.import_error()}\n\n"
            "The interface will run but no audio will be processed. Install "
            "the requirements and a working audio driver, then restart.")
    elif not started:
        QMessageBox.information(
            window, "Audio",
            "Audio did not start with the default devices.\n"
            f"Details: {engine.last_error}\n\n"
            "Open 'Device Settings' to choose an input/output device.")

    # Allow Ctrl+C to quit cleanly from a console.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    exit_code = app.exec()

    # Clean shutdown.
    engine.stop()
    midi.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
