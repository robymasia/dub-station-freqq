# Parametri ottimizzati per musica dub classica (roots/steppers)
# BPM target: 70-85
# 
# Utilizzo:
#   from presets.dub_classic import DUB_CLASSIC_PRESET
#   engine.load_preset(DUB_CLASSIC_PRESET)

DUB_CLASSIC_PRESET = {
    "tape_echo": {
        "delay_time": 0.375,      # 375ms (1/4 @ 80 BPM)
        "feedback": 0.50,         # 50% - echi che decadono gradualmente
        "wet_mix": 0.40,          # 40% - presente ma non dominante
        "dry_mix": 0.60,
        "saturation": 0.35,       # Calore analogico moderato
        "sync_to_bpm": True,
        "note_division": "1/4"    # Sincronizzato al tempo
    },
    "reverb": {
        "decay_time": 3.0,        # 3 secondi - coda lunga ma controllata
        "wet_mix": 0.25,          # 25% - più discreto del delay
        "dry_mix": 0.75,
        "pre_delay": 0.03,        # 30ms - separa dry/wet
        "damping": 0.6,           # Moderato - non troppo brillante
        "room_size": 0.8          # Spazio ampio
    },
    "isolator": {
        "kill_mode": "linkwitz_riley",  # Già corretto nella PR #1
        "bands": ["SUB", "BASS", "MIDS", "TOPS"],
        "crossover_freqs": [180, 500, 2500]  # Hz
    },
    "dub_filter": {
        "cutoff_min": 200,        # Hz
        "cutoff_max": 8000,       # Hz
        "resonance": 0.5,         # 50% - enfasi dub tipica
        "filter_type": "lowpass"  # LP per sweep classici
    },
    "master": {
        "output_gain": 0.85,      # Headroom per evitare clipping
        "limiter_threshold": -3.0 # dB
    }
}

# Funzione helper per calcolare delay time in base al BPM
def calculate_delay_time(bpm, note_division="1/4"):
    """Calcola il tempo di delay in secondi per una data divisione ritmica."""
    beat_duration = 60.0 / bpm
    divisions = {
        "1/1": 1.0,
        "1/2": 0.5,
        "1/4": 0.25,
        "1/8": 0.125,
        "1/16": 0.0625,
        "1/4d": 0.375,  # 1/4 dotted
        "1/8d": 0.1875, # 1/8 dotted
    }
    return beat_duration * divisions.get(note_division, 0.25)

# Esempio: per BPM diversi
DUB_PRESETS_BY_BPM = {
    70: {"delay_time": calculate_delay_time(70, "1/4"), "feedback": 0.50, "wet_mix": 0.40},
    75: {"delay_time": calculate_delay_time(75, "1/4"), "feedback": 0.50, "wet_mix": 0.40},
    80: {"delay_time": calculate_delay_time(80, "1/4"), "feedback": 0.50, "wet_mix": 0.40},
    85: {"delay_time": calculate_delay_time(85, "1/4"), "feedback": 0.45, "wet_mix": 0.35},
}
