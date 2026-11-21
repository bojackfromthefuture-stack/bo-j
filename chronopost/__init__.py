"""chronopost: moving information through time.

* ``chronopost.future``: real time-lock encryption (RSW puzzles).
* ``chronopost.past``: simulations of backwards channels (Novikov, Deutsch).
"""

from .future import TimeCapsule, calibrate, open_capsule, seal
from .past import SCENARIOS, ctc_solve, deutsch, novikov

__all__ = ["TimeCapsule", "calibrate", "open_capsule", "seal",
           "SCENARIOS", "ctc_solve", "deutsch", "novikov"]
__version__ = "0.1.0"
