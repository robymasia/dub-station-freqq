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
import argparse

# Import dal progetto
from audio_engine import AudioEngine
from midi_handler import MIDIHandler
from ui.main_window import MainWindow
from presets import PresetLoader, DUB_CLASSIC_PRESET


def parse_args():
    """Parse command line arguments."""
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
    
    # Initialize audio engine
    print("🔧 Inizializzazione audio engine...")
    engine = AudioEngine()
    
    # Initialize MIDI handler
    print("🎹 Inizializzazione MIDI...")
    midi = MIDIHandler()
    
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
    
    # Create and run main window (passa engine E midi)
    app = MainWindow(engine, midi=midi)
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Arrivederci!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Errore: {e}")
        sys.exit(1)
