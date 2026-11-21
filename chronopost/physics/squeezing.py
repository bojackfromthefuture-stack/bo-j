"""Squeezed light: reshaping quantum uncertainty, and what it can and cannot do.

A light wave has two quadratures, amplitude X1 and phase X2 (the cosine and
sine parts of the field). Quantum mechanics sets dX1 * dX2 >= 1/4, with
X = (a + a^dagger)/2, so the vacuum has variance 1/4 in both. A *squeezed*
state (made in a nonlinear crystal by parametric down-conversion) has
variance e^{-2r}/4 in one quadrature and e^{+2r}/4 in the other. The
product stays at the minimum, but the noise in one quadrature is pushed
below the vacuum level.

Where it is real:
* LIGO and Virgo inject squeezed vacuum. Since 2023 LIGO uses
  *frequency-dependent* squeezing (a 300 m filter cavity rotates the squeeze
  angle with frequency), with up to ~6 dB less noise. Record: 15 dB
  (Vahlbruch et al., PRL 2016).
* ``interferometer_noise`` reproduces the physics (Kimble, Levin, Matsko,
  Thorne & Vyatchanin, PRD 2001). Fixed-angle squeezing cuts shot noise but
  raises radiation-pressure noise. Rotating the angle cuts both, and can
  beat the standard quantum limit.

What it does *not* do: send information faster than light or into the past.
Two-mode squeezing makes Einstein-Podolsky-Rosen entanglement
(``two_mode``): Alice's measurement sharpens what she can *infer* about Bob,
but Bob's own statistics stay exactly the same whatever Alice does
(no-signalling). The correlations are only usable once a classical message
reaches him at light speed or slower.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

VACUUM = 0.25


# -------------------------------------------------------- single mode ---

def db(r: float) -> float:
    """Squeezing in decibels: 10 log10(e^{2r})."""
    return 10 * math.log10(math.exp(2 * r))


def r_from_db(decibels: float) -> float:
    return decibels * math.log(10) / 20


def variances(r: float) -> tuple[float, float]:
    """(squeezed, anti-squeezed) quadrature variances."""
    return VACUUM * math.exp(-2 * r), VACUUM * math.exp(2 * r)


def quadrature_variance(r: float, angle: float) -> float:
    """Variance of the quadrature at ``angle`` from the squeezed axis."""
    vs, va = variances(r)
    return vs * math.cos(angle) ** 2 + va * math.sin(angle) ** 2


def photon_distribution(r: float, nmax: int = 60) -> list[float]:
    """Squeezed vacuum photon-number probabilities: photons come only in pairs.

    P(2n) = C(2n, n) (tanh^2 r / 4)^n / cosh r,  P(odd) = 0,  <n> = sinh^2 r.
    """
    out = [0.0] * (nmax + 1)
    out[0] = 1 / math.cosh(r)
    x = math.tanh(r) ** 2 / 4
    for n in range(1, nmax // 2 + 1):
        # C(2n, n) / C(2n-2, n-1) = (2n)(2n-1) / n^2
        out[2 * n] = out[2 * n - 2] * x * (2 * n) * (2 * n - 1) / (n * n)
    return out


@dataclass
class Measured:
    squeezed_db: float        # below vacuum (positive = better than vacuum)
    antisqueezed_db: float


def with_losses(r: float, efficiency: float, phase_jitter_rad: float = 0.0) -> Measured:
    """What a detector actually sees.

    Loss mixes in vacuum: V -> eta V + (1 - eta)/4. Phase jitter of rms theta
    mixes in some anti-squeezing: V -> V_s cos^2 + V_a sin^2 (small-angle average).
    This is why 15 dB took 30 years: however much squeezing is generated, measuring
    15 dB needs total efficiency above 0.97 (and phase jitter of a few mrad at most).
    """
    vs, va = variances(r)
    c2, s2 = math.cos(phase_jitter_rad) ** 2, math.sin(phase_jitter_rad) ** 2
    vs, va = vs * c2 + va * s2, va * c2 + vs * s2
    vs = efficiency * vs + (1 - efficiency) * VACUUM
    va = efficiency * va + (1 - efficiency) * VACUUM
    return Measured(-10 * math.log10(vs / VACUUM), 10 * math.log10(va / VACUUM))


def homodyne_samples(r: float, angle: float, count: int, seed: int = 0) -> list[float]:
    """Simulated balanced-homodyne readings of one quadrature (Gaussian statistics)."""
    rng = random.Random(seed)
    sd = math.sqrt(quadrature_variance(r, angle))
    return [rng.gauss(0.0, sd) for _ in range(count)]


# -------------------------------------------- gravitational-wave detector ---

def coupling_k(freq_hz: float, power_ratio: float = 1.0, bandwidth_hz: float = 100.0) -> float:
    """Optomechanical coupling K(Omega) = 2 (I/I_SQL) gamma^4 / (Omega^2 (gamma^2 + Omega^2))."""
    g, w = bandwidth_hz, freq_hz
    return 2 * power_ratio * g**4 / (w * w * (g * g + w * w))


def interferometer_noise(freq_hz: float, r: float = 0.0, squeeze_angle: float | None = None,
                         frequency_dependent: bool = False, **k_args) -> float:
    """Quantum noise S_h / S_SQL of a conventional interferometer (KLMTV 2001).

    S/S_SQL = (1 + K^2) / (2K) * [cosh 2r - cos(2(lam + Phi)) sinh 2r],  Phi = arccot K.
    Vacuum (r = 0): (1/K + K)/2 >= 1, touching the SQL only where K = 1.
    Fixed angle lam = -pi/2: good at high frequency, worse at low.
    Frequency-dependent lam = -Phi(Omega): e^{-2r} everywhere, below the SQL.
    """
    K = coupling_k(freq_hz, **k_args)
    phi = math.atan2(1.0, K)  # arccot K
    if frequency_dependent:
        lam = -phi
    else:
        lam = -math.pi / 2 if squeeze_angle is None else squeeze_angle
    return (1 + K * K) / (2 * K) * (math.cosh(2 * r) - math.cos(2 * (lam + phi)) * math.sinh(2 * r))


# ------------------------------------------- two-mode squeezing: EPR ---

@dataclass
class TwoModeResult:
    bob_variance_alice_idle: float
    bob_variance_alice_measures_x: float     # rebuilt from Alice's outcomes + Bob's conditional states
    bob_variance_alice_measures_p: float
    conditional_variance: float              # Var(X_B | X_A): what Bob gets *after* Alice's message
    epr_product: float                       # Reid: Var(X_B|X_A) Var(P_B|P_A) < 1/16 means EPR paradox
    duan_sum: float                          # Var(X_A - X_B) + Var(P_A + P_B) < 1 means entangled


def two_mode(r: float, samples: int = 200_000, seed: int = 0) -> TwoModeResult:
    """Two-mode squeezed vacuum shared by Alice and Bob; Bob measures X_B.

    Var(X_A) = Var(X_B) = v = cosh(2r)/4, Cov(X_A, X_B) = c = sinh(2r)/4,
    Cov(P_A, P_B) = -c, and X_B is uncorrelated with P_A.

    If Alice measures X_A and gets x, Bob's state *collapses* to a narrow
    Gaussian, mean (c/v) x and variance v - c^2/v. But Bob doesn't know x.
    Averaged over Alice's outcomes, his statistics are rebuilt here by Monte
    Carlo (outcome first, then his conditional state) and come out the same
    as if she had done nothing, or measured P_A instead. That is
    no-signalling: the narrowing is real, but only usable with her message.
    """
    rng = random.Random(seed)
    v, c = math.cosh(2 * r) / 4, math.sinh(2 * r) / 4
    cond = v - c * c / v

    def var(xs):
        m = sum(xs) / len(xs)
        return sum((x - m) ** 2 for x in xs) / len(xs)

    idle = [rng.gauss(0, math.sqrt(v)) for _ in range(samples)]
    after_x = []
    for _ in range(samples):
        xa = rng.gauss(0, math.sqrt(v))                      # Alice's outcome
        after_x.append(rng.gauss(c / v * xa, math.sqrt(cond)))  # Bob's conditional state
    after_p = []
    for _ in range(samples):
        rng.gauss(0, math.sqrt(v))                           # Alice's P_A outcome: uncorrelated with X_B
        after_p.append(rng.gauss(0, math.sqrt(v)))
    # Duan: Var(X_A - X_B) = 2v - 2c, Var(P_A + P_B) = 2v - 2c  ->  sum = e^{-2r}
    duan = 4 * (v - c)
    return TwoModeResult(var(idle), var(after_x), var(after_p), cond, cond * cond, duan)
