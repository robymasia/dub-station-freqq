"""DSP package for DubStation FreQQ.

Contains all real-time digital signal processing modules used in the
audio processing chain: 4-band isolator, reverb, tape echo, resonant
dub filter, dub siren and the sample player.
"""

from .isolator import Isolator
from .reverb import Reverb
from .tape_echo import TapeEcho
from .dub_filter import DubFilter
from .siren import Siren
from .sampler import Sampler

__all__ = [
    "Isolator",
    "Reverb",
    "TapeEcho",
    "DubFilter",
    "Siren",
    "Sampler",
]
