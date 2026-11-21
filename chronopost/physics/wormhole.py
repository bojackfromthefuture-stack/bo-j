"""A traversable-wormhole time machine (Morris, Thorne & Yurtsever, PRL 1988).

Recipe:
1. Two wormhole mouths A and B sit together; through the throat (taken as
   having negligible length) their clocks are synchronised.
2. Mouth B is taken on a relativistic round trip. Time dilation makes B's
   clock fall behind by Delta = integral of (1 - 1/gamma) dt.
3. Because the throat links *equal proper times*, entering B at lab time t
   puts you out of A at lab time t - Delta.
4. If the mouths now sit a distance D apart with Delta > D/c, a light signal
   A -> B through ordinary space followed by B -> A through the throat comes
   back before it left: a closed timelike curve (CTC).

What the simulation reproduces exactly (special relativity on the mouths'
worldlines), and what it cannot:
* Holding the throat open needs exotic matter with negative energy density,
  breaking the averaged null energy condition. Only tiny, short-lived
  negative energies (the Casimir effect) are known.
* Hawking's chronology protection conjecture: vacuum fluctuations circulating
  through a nearly closed loop may diverge and destroy the wormhole just as
  the CTC forms (Kim & Thorne 1991; Hawking 1992). This is unresolved.
* A wormhole time machine can never reach a time before it was built: the
  earliest reachable lab time is when Delta first exceeds D/c.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from .relativity import C, YEAR, LY, gamma


@dataclass
class WormholeResult:
    lag_s: float                  # Delta: B's clock behind A's
    separation_m: float           # D after the trip
    trip_end_s: float             # lab time the trip ends
    ctc_onset_s: float | None     # lab time the CTC first forms (if ever)

    @property
    def is_time_machine(self) -> bool:
        return self.lag_s * C > self.separation_m

    @property
    def max_lookback_s(self) -> float:
        """How far into the past a light-speed message can reach after a loop."""
        return self.lag_s - self.separation_m / C

    def send_back(self, t_enter_b: float) -> float:
        """Enter mouth B at lab time t, exit A at t - Delta, radio to B. Arrival time at B."""
        return t_enter_b - self.lag_s + self.separation_m / C


def simulate(velocity: Callable[[float], float], duration: float, steps: int = 200_000) -> WormholeResult:
    """Integrate mouth B's worldline for any lab-frame velocity profile v(t).

    Uses the trapezoid rule for both position and proper time, and tracks when
    the CTC condition Delta(t) > |x_B(t)|/c first holds.
    """
    dt = duration / steps
    x, lag, onset = 0.0, 0.0, None
    v_prev = velocity(0.0)
    for k in range(1, steps + 1):
        t = k * dt
        v = velocity(t)
        x += 0.5 * (v + v_prev) * dt
        lag += 0.5 * ((1 - 1 / gamma(v)) + (1 - 1 / gamma(v_prev))) * dt
        v_prev = v
        # Judge the CTC condition only once B is at rest in the lab frame, where
        # "same proper time through the throat" maps cleanly onto lab time.
        if onset is None and v == 0.0 and lag * C > abs(x):
            onset = t
    return WormholeResult(lag, abs(x), duration, onset)


def out_and_park(speed_c: float, out_years: float, park_ly: float) -> Callable[[float], float]:
    """Fly B out at speed_c, turn round, and come back to rest park_ly from A.

    Smooth profile: cruise outbound, then return to the parking distance and stop.
    """
    v = speed_c * C
    t_out = out_years * YEAR
    d_out = v * t_out
    t_back = (d_out - park_ly * LY) / v
    if t_back < 0:
        raise ValueError("parking distance beyond outbound distance")

    def profile(t: float) -> float:
        if t < t_out:
            return v
        if t < t_out + t_back:
            return -v
        return 0.0

    profile.total = t_out + t_back  # type: ignore[attr-defined]
    return profile


def analytic_lag(speed_c: float, moving_time_s: float) -> float:
    """Closed form for constant-speed legs: Delta = T (1 - sqrt(1 - b^2))."""
    return moving_time_s * (1 - math.sqrt(1 - speed_c**2))
