"""Dimensions: why 3+1, and what extra space or time dimensions would do.

1. Orbits in n spatial dimensions (Ehrenfest 1917). Gauss's law gives a
   gravitational force F ~ 1/r^(n-1). A circular orbit under F ~ 1/r^p is
   stable only if p < 3, so only n < 4: planets (and, quantum mechanically,
   atoms) are stable only in n <= 3. Simulated by direct integration.

2. Compact extra dimensions (Kaluza-Klein). Momentum around a circle of
   radius R is quantised, p = k hbar / R, so a 5-D particle looks like a tower
   of 4-D masses m_k c^2 = k hbar c / R. Colliders see no tower up to a few
   TeV, which bounds R to below about 1e-19 m.

3. Extra *time* dimensions. With metric signature (2 time, n space), a circle
   in the (t1, t2) plane has a timelike tangent everywhere: it is a closed
   timelike curve that needs no exotic matter at all. With one time
   dimension, no closed curve can stay timelike, because t would have to rise
   all the way round. This is the geometric reason physics with two times
   loses causality and predictability (Tegmark 1997).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Sequence

HBAR_C_MEV_FM = 197.326_980_4  # MeV * fm


# -------------------------------------------------------- n-dim orbits ---

@dataclass
class OrbitResult:
    spatial_dims: int
    r_min: float
    r_max: float
    fate: str  # "bound", "drifting", "collapsed", "escaped"

    @property
    def stable(self) -> bool:
        return self.fate == "bound"


def orbit(spatial_dims: int, perturbation: float = 0.02, periods: float = 20,
          steps_per_period: int = 4000) -> OrbitResult:
    """Kick a circular orbit by ``perturbation`` (fractional speed change) and integrate.

    Units: GM = 1, r0 = 1. Force magnitude r^-(n-1) (log potential for n = 2).
    A central force keeps the motion in a plane, so 2-D integration is exact
    for any n. Velocity Verlet, which conserves energy well over long runs.
    """
    n = spatial_dims
    if n < 2:
        raise ValueError("need at least 2 spatial dimensions for an orbit")
    p = n - 1
    accel = lambda x, y: (-x / math.hypot(x, y) ** (p + 1), -y / math.hypot(x, y) ** (p + 1))
    v0 = 1.0 * (1 + perturbation)  # circular speed at r=1 is 1 for every p
    x, y, vx, vy = 1.0, 0.0, 0.0, v0
    dt = 2 * math.pi / steps_per_period
    ax, ay = accel(x, y)
    rmin = rmax = 1.0
    for _ in range(int(periods * steps_per_period)):
        vx += 0.5 * dt * ax; vy += 0.5 * dt * ay
        x += dt * vx; y += dt * vy
        r = math.hypot(x, y)
        if r < 0.05:
            return OrbitResult(n, r, rmax, "collapsed")
        if r > 50:
            return OrbitResult(n, rmin, r, "escaped")
        ax, ay = accel(x, y)
        vx += 0.5 * dt * ax; vy += 0.5 * dt * ay
        rmin, rmax = min(rmin, r), max(rmax, r)
    # Survived the run, but a 2% kick that grows r by 50%+ is not a stable orbit.
    return OrbitResult(n, rmin, rmax, "bound" if rmax / rmin < 1.5 else "drifting")


def radial_frequency_squared(spatial_dims: int) -> float:
    """Small-oscillation frequency^2 about a circular orbit (GM = r0 = 1): 3 - p = 4 - n.
    Positive means stable, zero marginal, negative unstable."""
    return 4 - spatial_dims


# -------------------------------------------------------- Kaluza-Klein ---

def kk_tower(radius_m: float, levels: int = 5) -> list[float]:
    """Masses (GeV/c^2) of the first Kaluza-Klein modes for a circle of radius R."""
    r_fm = radius_m * 1e15
    return [k * HBAR_C_MEV_FM / r_fm / 1000 for k in range(1, levels + 1)]


def radius_for_mass(mass_gev: float) -> float:
    """Circle radius (m) whose first KK mode has the given mass."""
    return HBAR_C_MEV_FM / (mass_gev * 1000) * 1e-15


# ------------------------------------------------------- time dimensions ---

Vector = Sequence[float]


def norm2(v: Vector, time_dims: int) -> float:
    """Squared length with signature (+ x time_dims, - x rest). >0 means timelike."""
    return sum(c * c for c in v[:time_dims]) - sum(c * c for c in v[time_dims:])


def is_closed_timelike(curve: Callable[[float], Vector], time_dims: int,
                       samples: int = 2000) -> bool:
    """Does the closed curve s in [0, 1) -> point have a timelike tangent everywhere?"""
    h = 1.0 / samples
    for k in range(samples):
        s = k * h
        a, b = curve(s), curve((s + h) % 1.0)
        tangent = [bj - aj for aj, bj in zip(a, b)]
        if norm2(tangent, time_dims) <= 0:
            return False
    return True


def time_circle(dims: int = 4) -> Callable[[float], Vector]:
    """A unit circle in the plane of coordinates 0 and 1 (both time, if there are two)."""
    return lambda s: [math.cos(2 * math.pi * s), math.sin(2 * math.pi * s)] + [0.0] * (dims - 2)
