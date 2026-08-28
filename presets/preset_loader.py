# Preset loader per dub-station-freqq
# 
# Utilizzo:
#   from presets.preset_loader import PresetLoader
#   loader = PresetLoader(engine)
#   loader.apply_preset("dub_classic")

from presets.dub_classic import DUB_CLASSIC_PRESET, DUB_PRESETS_BY_BPM, calculate_delay_time


class PresetLoader:
    """Classe per caricare e applicare preset all'audio engine."""
    
    def __init__(self, audio_engine):
        """Inizializza il loader con un riferimento all'audio engine."""
        self.engine = audio_engine
    
    def apply_preset(self, preset_name="dub_classic", bpm=80):
        """
        Applica un preset all'audio engine.
        
        Args:
            preset_name: Nome del preset (attualmente solo "dub_classic")
            bpm: BPM per calcolare delay time sincronizzato
        """
        if preset_name == "dub_classic":
            self._apply_dub_classic(bpm)
        else:
            raise ValueError(f"Preset '{preset_name}' non trovato")
    
    def _apply_dub_classic(self, bpm):
        """Applica il preset dub classic all'engine."""
        preset = DUB_CLASSIC_PRESET
        
        # Calcola delay time sincronizzato al BPM
        delay_time = calculate_delay_time(bpm, preset["tape_echo"]["note_division"])
        
        # Applica Tape Echo
        if hasattr(self.engine, 'tape_echo'):
            self.engine.tape_echo.set_delay_time(delay_time)
            self.engine.tape_echo.set_feedback(preset["tape_echo"]["feedback"])
            self.engine.tape_echo.set_wet_mix(preset["tape_echo"]["wet_mix"])
            self.engine.tape_echo.set_dry_mix(preset["tape_echo"]["dry_mix"])
            self.engine.tape_echo.set_saturation(preset["tape_echo"]["saturation"])
        
        # Applica Reverb
        if hasattr(self.engine, 'reverb'):
            # Reverb usa: set_send (wet), set_decay, set_damp
            self.engine.reverb.set_decay(preset["reverb"]["decay_time"])
            self.engine.reverb.set_send(preset["reverb"]["wet_mix"])
            self.engine.reverb.set_damp(preset["reverb"]["damping"])
        
        # Applica Dub Filter
        if hasattr(self.engine, 'dub_filter'):
            self.engine.dub_filter.set_cutoff_range(
                preset["dub_filter"]["cutoff_min"],
                preset["dub_filter"]["cutoff_max"]
            )
            self.engine.dub_filter.set_resonance(preset["dub_filter"]["resonance"])
        
        # Applica Master
        if hasattr(self.engine, 'master'):
            self.engine.master.set_output_gain(preset["master"]["output_gain"])
            self.engine.master.set_limiter_threshold(preset["master"]["limiter_threshold"])
        
        print(f"✅ Preset 'dub_classic' applicato @ {bpm} BPM")
        print(f"   Delay: {delay_time*1000:.1f}ms ({preset['tape_echo']['note_division']})")
        print(f"   Reverb: {preset['reverb']['decay_time']}s decay, send {preset['reverb']['wet_mix']*100:.0f}%")
    
    def get_preset_info(self, preset_name="dub_classic"):
        """Restituisce informazioni sul preset."""
        if preset_name == "dub_classic":
            return {
                "name": "Dub Classic",
                "description": "Parametri ottimizzati per roots/steppers dub",
                "bpm_range": "70-85",
                "characteristics": [
                    "Delay 1/4 note sincronizzato",
                    "Feedback 50% per echi lunghi",
                    "Reverb send 25% con decay 0.5",
                    "Filter resonance 50% per sweep",
                    "Master gain con headroom"
                ]
            }
        return None


# Funzione utility per caricare preset rapidi per BPM specifici
def get_dub_preset_for_bpm(bpm):
    """
    Restituisce un preset dub ottimizzato per un BPM specifico.
    
    Args:
        bpm: BPM del brano (70-85 consigliato)
    
    Returns:
        Dict con parametri ottimizzati
    """
    if bpm in DUB_PRESETS_BY_BPM:
        return DUB_PRESETS_BY_BPM[bpm]
    
    # Fallback: calcola per BPM arbitrario
    return {
        "delay_time": calculate_delay_time(bpm, "1/4"),
        "feedback": 0.50 if bpm <= 80 else 0.45,
        "wet_mix": 0.40 if bpm <= 80 else 0.35
    }
