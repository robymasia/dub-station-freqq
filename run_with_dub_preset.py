#!/usr/bin/env python3
"""
Dub Station Freqq - Avvio con preset Dub Classic

Questo script avvia l'applicazione con i parametri ottimizzati per il dub
già¡¡ applicati automaticamente. Usalo invece di main.py per avere subito
il sound dub classico (roots/steppers, BPM 70-85).

Utilizzo:
    python run_with_dub_preset.py

Oppure con BPM personalizzato:
    python run_with_dub_preset.py --bpm 75
"""

import sys
import signal
import threading

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from audio_engine import AudioEngine
from midi_handler import MIDIHandler
from ui.main_window import MainWindow
from presets import PresetLoader, DUB_CLASSIC_PRESET

try:
    from dsp._kernels import warmup as _kernel_warmup
except Exception:
    _kernel_warmup = None

SAMPLERATE = 44100
BLOCKSIZE = 512


def parse_args():
    """Parse command line arguments."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Dub Station Freqq con preset Dub Classic"
    )
    parser.add_argument(
        "--bpm",
        type=int,
        default=80,
        help="BPM del brano (default: 80, consigliato: 70-85)"
    )
    parser.add_argument(
        "--preset",
        type=str,
        default="dub_classic",
        help="Nome del preset (default: dub_classic)"
    )
    return parser.parse_args()


def main():
    """Main application entry point with dub preset."""
    args = parse_args()
    
    print("🎵 Dub Station Freqq - Dub Classic Preset")
    print(f"   BPM: {args.bpm}")
    print(f"   Preset: {args.preset}")
    print("-" * 40)
    
    # High-DPI friendly
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    
    app = QApplication(sys.argv)
    app.setApplicationName("DubStation FreQQ")
    
    # Pre-compile DSP kernels
    if _kernel_warmup is not None:
        threading.Thread(target=_kernel_warmup, daemon=True).start()
    
    # Initialize audio engine
    print("🔧 Inizializzazione audio engine...")
    engine = AudioEngine(samplerate=SAMPLERATE, blocksize=BLOCKSIZE)
    
    # Initialize MIDI handler
    print("🎹 Inizializzazione MIDI...")
    midi = MIDIHandler()
    
    # Start audio
    started = engine.start()
    
    # Apply dub classic preset
    print("🎚️ Applicazione preset dub classic...")
    loader = PresetLoader(engine)
    loader.apply_preset(args.preset, bpm=args.bpm)
    
    # Show preset info
    preset_info = loader.get_preset_info(args.preset)
    if preset_info:
        print(f"\n📋 {preset_info['name']}")
        print(f"   {preset_info['description']}")
        print(f"   BPM range: {preset_info['bpm_range']}")
        print("\n   Caratteristiche:")
        for char in preset_info['characteristics']:
            print(f"   • {char}")
    
    print("-" * 40)
    print("✅ Pronto! Avvio interfaccia...\n")
    
    # Create main window
    window = MainWindow(engine, midi)
    
    # Show audio status messages
    if not engine.available():
        QMessageBox.warning(
            window, "Audio",
            f"The 'sounddevice' backend is not available.\nDetails: {engine.import_error()}\n\n"
            "Install requirements and audio driver, then restart.")
    elif not started:
        QMessageBox.information(
            window, "Audio",
            f"Audio did not start with default devices.\nDetails: {engine.last_error}\n\n"
            "Open 'Device Settings' to choose input/output.")
    
    window.show()
    
    # Allow Ctrl+C to quit
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    exit_code = app.exec()
    
    # Clean shutdown
    engine.stop()
    midi.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
