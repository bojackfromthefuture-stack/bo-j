"""Reversals and entropy: William James Sidis, *The Animate and the Inanimate* (1925).

Sidis argued, from the reversibility of mechanics, that:

  A. the second law of thermodynamics is statistical, not absolute;
  B. an infinite universe must contain regions where it runs *in reverse*,
     where energy concentrates and time's arrow points the other way;
  C. life, the "animate", is such a reversal at work in our region;
  D. reversed regions would *absorb* light rather than emit it, so they would
     look dark (later read as anticipating black holes or dark matter);
  E. the universe has no heat death; it alternates without end.

Each claim is tested here against modern statistical physics:

  A. Right (Boltzmann; Loschmidt's paradox). ``kac_ring``: perfectly
     reversible dynamics whose coarse-grained entropy still rises, then falls
     back exactly when the motion is reversed (a Loschmidt echo).
  B. Partly right. Entropy-decreasing fluctuations are real and measured
     (fluctuation theorem, Evans & Searles 1994; optical-trap experiments
     2002), but their probability falls as e^{-Delta S / k}
     (``fluctuation_theorem``). Schulman (1999) showed that low-entropy
     conditions at *both* ends of time produce a region with a reversed
     arrow (``two_boundary_urn``): the closest modern version of Sidis's idea.
  C. Wrong as stated. Life lowers its own entropy by exporting more:
     Schrodinger's "negative entropy" (1944) and Prigogine's dissipative
     structures. A Maxwell-demon "animate" sorter has to record
     information, and erasing it costs at least kT ln 2 per bit (Landauer
     1961; ``maxwell_demon``). Earth exports ~6e14 W/K (``earth_budget``).
  D. Inverted. Black holes do absorb everything, but they have the *largest*
     entropy of any object (Bekenstein-Hawking); they obey a generalised
     second law instead of reversing it (``black_hole``).
  E. Open. Observation points to a low-entropy Big Bang (the "past
     hypothesis"). Poincare recurrences exist in bounded systems
     (``kac_ring`` recurs exactly), but cosmological recurrence times are
     around e^(10^122).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

K_B = 1.380_649e-23
HBAR = 1.054_571_817e-34
G = 6.674_30e-11
C = 299_792_458.0
M_SUN = 1.988_47e30
SIGMA_SB = 5.670_374_419e-8


def _h(p: float) -> float:
    """Binary entropy in nats."""
    return 0.0 if p in (0.0, 1.0) else -(p * math.log(p) + (1 - p) * math.log(1 - p))


# ---------------------------------------------------- A. Kac ring + echo ---

@dataclass
class KacRun:
    entropy: list[float]       # coarse-grained entropy per site (max ln 2), per step
    returned_exactly: bool     # did the reversed run restore the initial state?
    recurrence_step: int | None


def kac_ring(sites: int = 2000, marker_fraction: float = 0.1, forward: int = 150,
             reverse_error: float = 0.0, seed: int = 1) -> KacRun:
    """Mark Kac's ring: deterministic, reversible, recurrent, yet entropy rises.

    Balls on a ring all start white. Each step every ball moves one site
    clockwise and flips colour when it crosses a marked edge. After ``forward``
    steps the motion is reversed (counter-clockwise). With ``reverse_error`` > 0
    a fraction of markers is moved before reversing, an imperfect reversal.
    """
    rng = random.Random(seed)
    marked = [rng.random() < marker_fraction for _ in range(sites)]
    balls = [0] * sites          # 0 white, 1 black
    start = balls[:]

    def entropy():
        return _h(sum(balls) / sites)

    def step(direction):
        nonlocal balls
        new = [0] * sites
        if direction > 0:        # ball at i crosses edge i to reach i+1
            for i in range(sites):
                new[(i + 1) % sites] = balls[i] ^ marked[i]
        else:                    # ball at i crosses edge i-1 to reach i-1
            for i in range(sites):
                new[i - 1] = balls[i] ^ marked[i - 1]
        balls = new

    S = [entropy()]
    for _ in range(forward):
        step(+1)
        S.append(entropy())
    if reverse_error:
        for i in range(sites):
            if rng.random() < reverse_error:
                marked[i] = not marked[i]
    for _ in range(forward):
        step(-1)
        S.append(entropy())
    returned = balls == start

    # Poincare recurrence: each ball meets every marker once per lap; after one or
    # two laps the flip count is even and the state repeats. Check it directly.
    balls = start[:]
    rec = None
    for t in range(1, 2 * sites + 1):
        step(+1)
        if balls == start:
            rec = t
            break
    return KacRun(S, returned, rec)


# ----------------------------------------- B. fluctuation theorem (exact) ---

@dataclass
class FluctuationResult:
    steps: int
    p_entropy_decrease: float               # P(sigma < 0)
    ratio_checks: list[tuple[float, float]]  # (sigma, ln[P(sigma)/P(-sigma)]): should be equal


def fluctuation_theorem(steps: int, p: float = 0.6) -> FluctuationResult:
    """A particle dragged through a heat bath: biased random walk, right with prob p.

    Each step produces entropy +-ln(p/q) (in units of k). Exactly,
    P(sigma) / P(-sigma) = e^{sigma}. Reversed (entropy-decreasing) histories
    are allowed, but become exponentially rare as the system is watched longer.
    """
    q = 1 - p
    unit = math.log(p / q)
    logC = lambda n, k: math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    probs = {}
    for r in range(steps + 1):                   # r steps right
        x = 2 * r - steps
        probs[x] = math.exp(logC(steps, r) + r * math.log(p) + (steps - r) * math.log(q))
    dec = sum(pr for x, pr in probs.items() if x < 0)
    checks = [(x * unit, math.log(probs[x] / probs[-x])) for x in sorted(probs) if 0 < x <= 6]
    return FluctuationResult(steps, dec, checks)


def reversal_probability(delta_s_over_k: float) -> float:
    """Relative odds of a spontaneous entropy decrease of Delta S: ~ e^{-Delta S / k}."""
    return math.exp(-delta_s_over_k) if delta_s_over_k < 745 else 0.0


# ---------------------------------- B'. Schulman: two-time boundary values ---

@dataclass
class TwoBoundaryResult:
    entropy_forward_only: list[float]   # mean ln C(N, n), low entropy at t = 0 only
    entropy_two_boundary: list[float]   # also low entropy imposed at t = T


def two_boundary_urn(balls: int = 40, duration: int = 120) -> TwoBoundaryResult:
    """Ehrenfest urn: each step one random ball jumps to the other urn.

    Exact computation over all states (no sampling). With all balls in one
    urn at t = 0, entropy rises and stays high. Condition also on all balls
    being in one urn at t = T: entropy rises, peaks, and *falls* towards T.
    An observer in the second half sees entropy decrease, a reversed arrow
    set by a future boundary condition.
    """
    N, T = balls, duration + (duration % 2)   # parity: returning to N needs even T

    def step(v):
        out = [0.0] * (N + 1)
        for n, pr in enumerate(v):
            if pr:
                if n > 0:
                    out[n - 1] += pr * n / N
                if n < N:
                    out[n + 1] += pr * (N - n) / N
        return out

    def back(v):  # v_t(n) = P(reach N at T | n at t)
        out = [0.0] * (N + 1)
        for n in range(N + 1):
            s = 0.0
            if n > 0:
                s += n / N * v[n - 1]
            if n < N:
                s += (N - n) / N * v[n + 1]
            out[n] = s
        return out

    logC = [math.lgamma(N + 1) - math.lgamma(n + 1) - math.lgamma(N - n + 1) for n in range(N + 1)]
    fwd = [[0.0] * (N + 1)]
    fwd[0][N] = 1.0
    for _ in range(T):
        fwd.append(step(fwd[-1]))
    bwd = [[0.0] * (N + 1) for _ in range(T + 1)]
    bwd[T][N] = 1.0
    for t in range(T - 1, -1, -1):
        bwd[t] = back(bwd[t + 1])

    only, both = [], []
    for t in range(T + 1):
        only.append(sum(p * s for p, s in zip(fwd[t], logC)))
        w = [f * b for f, b in zip(fwd[t], bwd[t])]
        z = sum(w)
        both.append(sum(x * s for x, s in zip(w, logC)) / z)
    return TwoBoundaryResult(only, both)


# --------------------------------------------- C. Maxwell's demon & Landauer ---

@dataclass
class DemonResult:
    gas_entropy_drop_bits: float     # how much the demon lowered the gas entropy
    memory_bits: float               # information it had to record (Shannon)
    erasure_cost_bits: float         # Landauer: >= memory bits of entropy to reset
    net_entropy_change_bits: float   # erasure - gas drop: >= 0 means no violation

    @property
    def second_law_holds(self) -> bool:
        return self.net_entropy_change_bits >= -1e-9


def maxwell_demon(molecules: int = 60, runs: int = 30, seed: int = 2) -> DemonResult:
    """A demon (Sidis's "animate" sorter) herds a gas into one box.

    Each moment a random molecule approaches the door. The demon looks to
    see which side it is on (one measurement) and opens the door only for
    left-to-right moves, until every molecule is on the right. Its record
    has Shannon content sum H2(n_left/N), averaged over runs. Landauer:
    resetting that memory produces at least that much entropy.
    """
    rng = random.Random(seed)
    N = molecules
    drop = math.log2(math.comb(N, N // 2))   # from the half-and-half macrostate to all-right
    mem_total = 0.0
    for _ in range(runs):
        n_left = N // 2
        mem = 0.0
        while n_left:
            p = n_left / N
            mem += _h(p) / math.log(2)
            if rng.random() < p:     # molecule is on the left: let it through
                n_left -= 1
        mem_total += mem
    mem_bits = mem_total / runs
    return DemonResult(drop, mem_bits, mem_bits, mem_bits - drop)


# ------------------------------------------------------ C'. life and Earth ---

@dataclass
class EntropyBudget:
    absorbed_w: float
    entropy_in_w_per_k: float
    entropy_out_w_per_k: float

    @property
    def export_w_per_k(self) -> float:
        return self.entropy_out_w_per_k - self.entropy_in_w_per_k


def earth_budget(solar_constant: float = 1361.0, albedo: float = 0.30,
                 t_sun: float = 5772.0, t_earth: float = 255.0) -> EntropyBudget:
    """Earth takes in few hot photons and sends out many cold ones.

    Blackbody radiation carries entropy (4/3) P / T. This export is what
    lets life and weather build order here. (Treating sunlight at T_sun
    ignores its dilution, which slightly underestimates incoming entropy.)
    """
    R = 6.371e6
    P = solar_constant * math.pi * R * R * (1 - albedo)
    return EntropyBudget(P, 4 / 3 * P / t_sun, 4 / 3 * P / t_earth)


def human_entropy_production(metabolic_w: float = 100.0, t_env: float = 293.0) -> float:
    """W/K a resting human releases as heat into the room (ignores food and CO2 terms)."""
    return metabolic_w / t_env


# ---------------------------------------------------- D. Sidis's dark stars ---

@dataclass
class BlackHole:
    mass_kg: float
    radius_m: float
    entropy_over_k: float
    hawking_temperature_k: float
    evaporation_years: float


def black_hole(mass_suns: float = 1.0) -> BlackHole:
    """Bekenstein-Hawking: S = k c^3 A / (4 G hbar), T = hbar c^3 / (8 pi G M k)."""
    M = mass_suns * M_SUN
    rs = 2 * G * M / C**2
    S = 4 * math.pi * G * M * M / (HBAR * C)
    T = HBAR * C**3 / (8 * math.pi * G * M * K_B)
    t_evap = 5120 * math.pi * G**2 * M**3 / (HBAR * C**4) / (365.25 * 86400)
    return BlackHole(M, rs, S, T, t_evap)


def sun_entropy_over_k() -> float:
    """Rough entropy of the Sun as an ideal gas of ~1e57 particles: ~ 10-30 k each."""
    particles = M_SUN / 1.67e-27 * 1.2   # protons plus electrons, roughly
    return particles * 20
