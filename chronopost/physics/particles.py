"""Matter -> energy -> matter: relativistic kinematics of annihilation and pair creation.

Natural units: energies and momenta in MeV (c = 1).

* Annihilation:   e+ e-  -> gamma gamma    (matter -> energy)
* Breit-Wheeler:  gamma gamma -> e+ e-     (energy -> matter; first seen in
  2021 at RHIC's STAR experiment)
* Bethe-Heitler:  gamma + nucleus -> e+ e- + nucleus (routine in every
  gamma-ray detector)

Every step conserves four-momentum *exactly*: rest mass is not "used up",
the invariant mass sqrt(s) is carried across the whole cycle. Photons can
only make a pair if sqrt(s) >= 2 m_e: at least 1.022 MeV in the centre of
momentum frame.

Feynman-Stueckelberg: in quantum field theory a positron moving forward in
time is mathematically the same as an electron moving *backward* in time.
``worldline_reading`` takes a pair-creation / annihilation history and
rewrites it as one electron zig-zagging through time. This is a real
symmetry (CPT) but it carries no usable message to the past: the
"backwards" stretch is fixed by forward-in-time boundary conditions, and the
no-communication results of QFT (microcausality) still hold.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

M_E = 0.510_998_950          # MeV, electron mass
R_E = 2.817_940_326_2e-15    # m, classical electron radius
SIGMA_T = 8 * math.pi / 3 * R_E**2  # Thomson cross section, m^2


@dataclass(frozen=True)
class P4:
    E: float
    px: float = 0.0
    py: float = 0.0
    pz: float = 0.0

    def __add__(self, o: "P4") -> "P4":
        return P4(self.E + o.E, self.px + o.px, self.py + o.py, self.pz + o.pz)

    def __sub__(self, o: "P4") -> "P4":
        return P4(self.E - o.E, self.px - o.px, self.py - o.py, self.pz - o.pz)

    @property
    def p(self) -> float:
        return math.sqrt(self.px**2 + self.py**2 + self.pz**2)

    @property
    def m2(self) -> float:
        return self.E**2 - self.p**2

    @property
    def mass(self) -> float:
        return math.sqrt(max(self.m2, 0.0))

    def beta(self) -> tuple[float, float, float]:
        return (self.px / self.E, self.py / self.E, self.pz / self.E)

    def boost(self, b: tuple[float, float, float]) -> "P4":
        """Lorentz boost by velocity vector b (|b| < 1): lab <- frame moving at b."""
        bx, by, bz = b
        b2 = bx * bx + by * by + bz * bz
        if b2 == 0:
            return self
        g = 1 / math.sqrt(1 - b2)
        bp = bx * self.px + by * self.py + bz * self.pz
        k = (g - 1) * bp / b2 + g * self.E
        return P4(g * (self.E + bp), self.px + k * bx, self.py + k * by, self.pz + k * bz)

    @staticmethod
    def at_rest(m: float) -> "P4":
        return P4(m)

    @staticmethod
    def moving(m: float, kinetic: float, direction=(0.0, 0.0, 1.0)) -> "P4":
        E = m + kinetic
        p = math.sqrt(E * E - m * m)
        n = math.sqrt(sum(d * d for d in direction))
        return P4(E, *(p * d / n for d in direction))


def _random_direction(rng: random.Random) -> tuple[float, float, float]:
    cz = rng.uniform(-1, 1)
    phi = rng.uniform(0, 2 * math.pi)
    sz = math.sqrt(1 - cz * cz)
    return (sz * math.cos(phi), sz * math.sin(phi), cz)


def two_body(total: P4, m1: float, m2: float, rng: random.Random) -> tuple[P4, P4]:
    """Split a system into two particles, isotropic in its rest frame, then boost to lab.

    Angular distributions of the real processes are not isotropic at high
    energy, but kinematics (energies, momenta, conservation) are exact.
    """
    s = total.m2
    M = math.sqrt(s)
    if M < m1 + m2 - 1e-12:
        raise ValueError(f"below threshold: sqrt(s) = {M:.6f} MeV < {m1 + m2:.6f} MeV")
    p = math.sqrt(max((s - (m1 + m2) ** 2) * (s - (m1 - m2) ** 2), 0.0)) / (2 * M)
    d = _random_direction(rng)
    a = P4(math.sqrt(p * p + m1 * m1), *(p * x for x in d))
    b = P4(math.sqrt(p * p + m2 * m2), *(-p * x for x in d))
    beta = total.beta()
    return a.boost(beta), b.boost(beta)


def annihilate(positron: P4, electron: P4, rng: random.Random) -> tuple[P4, P4]:
    """e+ e- -> 2 gamma."""
    return two_body(positron + electron, 0.0, 0.0, rng)


def breit_wheeler(g1: P4, g2: P4, rng: random.Random) -> tuple[P4, P4]:
    """gamma gamma -> e+ e-."""
    return two_body(g1 + g2, M_E, M_E, rng)


def breit_wheeler_threshold(e1: float, e2: float, angle: float) -> bool:
    """s = 2 E1 E2 (1 - cos(theta)) >= (2 m_e)^2."""
    return 2 * e1 * e2 * (1 - math.cos(angle)) >= (2 * M_E) ** 2


def bethe_heitler_threshold(nucleus_mass_mev: float) -> float:
    """Photon energy needed to make a pair off a nucleus at rest: 2 m_e (1 + m_e / M)."""
    return 2 * M_E * (1 + M_E / nucleus_mass_mev)


# ---------------------------------------------------------- cross sections ---

def sigma_breit_wheeler(s: float) -> float:
    """Breit-Wheeler cross section (m^2) at invariant mass^2 s (MeV^2)."""
    if s <= 4 * M_E**2:
        return 0.0
    b = math.sqrt(1 - 4 * M_E**2 / s)
    return (math.pi * R_E**2 / 2) * (1 - b * b) * (
        (3 - b**4) * math.log((1 + b) / (1 - b)) - 2 * b * (2 - b * b))


def sigma_dirac(positron_gamma: float) -> float:
    """Dirac (1930) annihilation cross section (m^2), positron of Lorentz factor gamma on e- at rest."""
    g = positron_gamma
    if g <= 1:
        raise ValueError("gamma must exceed 1")
    r = math.sqrt(g * g - 1)
    return math.pi * R_E**2 / (g + 1) * (
        (g * g + 4 * g + 1) / (g * g - 1) * math.log(g + r) - (g + 3) / r)


# ------------------------------------------------------------- the cycle ---

@dataclass
class CycleStep:
    process: str
    inputs: list[P4]
    outputs: list[P4]

    @property
    def conservation_error(self) -> float:
        a = sum(self.inputs, P4(0.0))
        b = sum(self.outputs, P4(0.0))
        d = a - b
        return max(abs(d.E), abs(d.px), abs(d.py), abs(d.pz))


def matter_energy_matter(kinetic_mev: float = 5.0, seed: int = 1) -> list[CycleStep]:
    """Collide e+ and e- head-on, annihilate to photons, collide those photons to
    make a new pair, and annihilate again: matter -> energy -> matter -> energy.

    In vacuum the two photons from one annihilation have exactly the invariant
    mass of the original pair, so re-colliding them is always above
    threshold. Here they are re-collided directly.
    """
    rng = random.Random(seed)
    ep = P4.moving(M_E, kinetic_mev, (0, 0, 1))
    em = P4.moving(M_E, kinetic_mev, (0, 0, -1))
    steps = []
    g1, g2 = annihilate(ep, em, rng)
    steps.append(CycleStep("e+ e- -> gamma gamma", [ep, em], [g1, g2]))
    ep2, em2 = breit_wheeler(g1, g2, rng)
    steps.append(CycleStep("gamma gamma -> e+ e-", [g1, g2], [ep2, em2]))
    g3, g4 = annihilate(ep2, em2, rng)
    steps.append(CycleStep("e+ e- -> gamma gamma", [ep2, em2], [g3, g4]))
    return steps


# ------------------------------------------------ Feynman-Stueckelberg ---

@dataclass
class Segment:
    particle: str          # as observed: "e-", "e+"
    t_start: float
    t_end: float
    x_start: float
    x_end: float

    def as_electron(self) -> "Segment":
        """Re-read a positron as an electron running the same path backwards in time."""
        if self.particle == "e+":
            return Segment("e- (backwards in time)", self.t_end, self.t_start, self.x_end, self.x_start)
        return self


def worldline_reading(t_create: float = 0.0, t_annihilate: float = 10.0,
                      x_create: float = 0.0, x_annihilate: float = 4.0) -> list[Segment]:
    """Pair creation at P, annihilation of the positron with another electron at Q.

    Observed (forward time): electron 1 comes in and reaches Q; a pair appears
    at P; the positron travels P -> Q and annihilates with electron 1; electron
    2 leaves P. Re-read as one electron: in, back in time Q -> P, then out.
    """
    observed = [
        Segment("e-", t_create - 5, t_annihilate, x_annihilate - 3, x_annihilate),
        Segment("e+", t_create, t_annihilate, x_create, x_annihilate),
        Segment("e-", t_create, t_create + 15, x_create, x_create - 3),
    ]
    return [s.as_electron() for s in observed]
