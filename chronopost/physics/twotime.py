"""Two time dimensions, and time that loops: does cause and effect survive?

The short answer is "it depends on what else is true". This module checks
each part numerically.

1. **No past and future.** With one time dimension, the timelike directions
   split into two disconnected pieces, the future cone and the past cone. No
   continuous change of an observer can turn one into the other. With two
   time dimensions, they form *one* connected piece: rotating in the
   (t1, t2) plane carries "forward" smoothly into "backward". So there is no
   invariant arrow, and a circle in that plane is a closed timelike curve.

2. **Is the future predictable?** The wave equation with two times,
   u_t1t1 + u_t2t2 = u_xx, is *ultrahyperbolic*. Given data on t1 = 0, the
   Fourier mode e^{i(kx + q t2)} grows like e^{sqrt(q^2 - k^2) t1} when
   |q| > |k|. Ever finer, tinier disturbances blow up ever faster
   (Hadamard): the future does not depend continuously on the present.
   This is the instability behind Tegmark's 1997 argument.
   **But** Craig & Weinstein (2009) showed the problem *is* well-posed if
   the data satisfy a nonlocal constraint that removes the |q| > |k| modes.
   Cause and effect survive, but "causes" can no longer be chosen freely and
   locally: data here must be correlated with data elsewhere in t2.

3. **Time that loops.** Put the evolution on a circle of time T. A history
   is consistent only if it comes back to itself:
   * Linear systems: only states in ker(e^{AT} - I) are allowed. An
     oscillator can exist only if omega*T is a multiple of 2*pi, so
     frequencies (and, with hbar, energies E = n h / T) are quantised.
     A damped system has only the trivial history: nature allows nothing.
   * Continuous systems: Brouwer's fixed-point theorem guarantees at least
     one consistent history. This is how the "billiard-ball paradox"
     resolves (Echeverria, Klinkhammer & Thorne 1991): the ball strikes
     its younger self a *glancing* blow, just enough to still enter the
     time machine. Paradoxes need discontinuous rules, like the yes/no
     grandfather in ``chronopost.past``.

4. **Bars's two-time physics** (I. Bars, 1998 on): spacetime with signature
   (d, 2) plus a gauge symmetry, Sp(2,R), that removes the extra time and
   extra space dimension. Ordinary 1-time physics appears as its
   "shadows". Causality is kept because the second time is gauge, not
   physical. (Described here, not simulated.)
"""

from __future__ import annotations

import cmath
import math
import random
from dataclasses import dataclass
from typing import Callable, Sequence


# ---------------------------------------------------- 1. time orientation ---

def norm2(v: Sequence[float], time_dims: int) -> float:
    return sum(c * c for c in v[:time_dims]) - sum(c * c for c in v[time_dims:])


def timelike_components(time_dims: int, space_dims: int = 1, samples: int = 3000,
                        seed: int = 0) -> int:
    """Count connected pieces of the set of unit timelike vectors (norm2 = 1).

    Samples the hyperboloid, links points closer than a small radius
    (union-find), and counts clusters. Expected: 2 for one time dimension
    (future + past), 1 for two or more.
    """
    rng = random.Random(seed)
    d = time_dims + space_dims
    pts = []
    for _ in range(samples):
        # spatial part bounded so the sample stays compact; time part on a sphere of radius sqrt(1+|x|^2)
        x = [rng.uniform(-1, 1) for _ in range(space_dims)]
        tdir = [rng.gauss(0, 1) for _ in range(time_dims)]
        tn = math.sqrt(sum(c * c for c in tdir)) or 1.0
        r = math.sqrt(1 + sum(c * c for c in x))
        pts.append([r * c / tn for c in tdir] + x)
    parent = list(range(samples))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    radius = 0.35 if d <= 3 else 0.6
    # sort by first coordinate so the neighbour search is cheap
    order = sorted(range(samples), key=lambda i: pts[i][0])
    for a_idx, i in enumerate(order):
        for j in order[a_idx + 1:]:
            if pts[j][0] - pts[i][0] > radius:
                break
            if math.dist(pts[i], pts[j]) < radius:
                parent[find(i)] = find(j)
    return len({find(i) for i in range(samples)})


def reverse_time_continuously(time_dims: int, steps: int = 1000) -> bool:
    """Is there a path of timelike directions from 'forward' (+t1) to 'backward' (-t1)?

    With two times, rotate in the (t1, t2) plane: every vector on the way has
    norm2 = 1. With one time, any timelike path keeps t1 != 0, so by the
    intermediate value theorem t1 can never change sign.
    """
    if time_dims < 2:
        return False
    for k in range(steps + 1):
        th = math.pi * k / steps
        v = [math.cos(th), math.sin(th)] + [0.0] * (time_dims - 2) + [0.0]
        if norm2(v, time_dims) <= 0:
            return False
    return True


# ----------------------------------------------- 2. ultrahyperbolic waves ---

@dataclass
class UltraResult:
    modes: int
    amplification: float     # ||u(t1)|| / ||u(0)|| for random data
    worst_mode_growth: float


def ultrahyperbolic(modes: int, t1: float = 1.0, constrained: bool = False,
                    seed: int = 0) -> UltraResult:
    """Evolve random data u(0, x, t2), u_t1(0) = 0, under u_t1t1 + u_t2t2 = u_xx.

    Periodic box of side 2*pi, so k and q are integers in [-modes/2, modes/2).
    Each Fourier mode evolves exactly: cos(sqrt(k^2 - q^2) t1) when |k| >= |q|,
    cosh(sqrt(q^2 - k^2) t1) otherwise. ``constrained`` applies the
    Craig-Weinstein restriction: drop every |q| > |k| mode from the data.
    """
    rng = random.Random(seed)
    half = modes // 2
    e0 = e1 = 0.0
    worst = 1.0
    for k in range(-half, half):
        for q in range(-half, half):
            if constrained and q * q > k * k:
                continue
            a = rng.gauss(0, 1)
            lam2 = k * k - q * q
            g = math.cos(math.sqrt(lam2) * t1) if lam2 >= 0 else math.cosh(math.sqrt(-lam2) * t1)
            e0 += a * a
            e1 += (a * g) ** 2
            worst = max(worst, abs(g))
    return UltraResult(modes, math.sqrt(e1 / e0), worst)


# ---------------------------------------------------------- 3. time loops ---

Matrix = list[list[complex]]


def _eig2(A: Sequence[Sequence[float]]) -> tuple[complex, complex]:
    a, b = A[0]
    c, d = A[1]
    tr, det = a + d, a * d - b * c
    disc = cmath.sqrt(tr * tr / 4 - det)
    return tr / 2 + disc, tr / 2 - disc


def loop_consistent_dimension(A: Sequence[Sequence[float]], T: float, tol: float = 1e-9) -> int:
    """For dx/dt = A x on a time loop of length T (A is 2x2): how many independent
    self-consistent histories exist? Equals the number of eigenvalues lam with
    e^{lam T} = 1 (A assumed diagonalisable)."""
    return sum(1 for lam in _eig2(A) if abs(cmath.exp(lam * T) - 1) < tol)


def oscillator(omega: float, damping: float = 0.0) -> list[list[float]]:
    """x'' + 2*damping*x' + omega^2 x = 0 as a first-order system."""
    return [[0.0, 1.0], [-omega * omega, -2 * damping]]


def allowed_frequencies(T: float, count: int = 5) -> list[float]:
    """On a time loop of length T only omega_n = 2 pi n / T survive (E_n = n h / T)."""
    return [2 * math.pi * n / T for n in range(1, count + 1)]


def consistent_histories(f: Callable[[float], float], lo: float = 0.0, hi: float = 1.0,
                         grid: int = 2000, tol: float = 1e-12) -> list[float]:
    """All fixed points x = f(x) of a loop map on [lo, hi] (sign changes + bisection).

    Brouwer: if f is continuous and maps [lo, hi] into itself, the list is
    never empty.
    """
    g = lambda x: f(x) - x
    xs = [lo + (hi - lo) * i / grid for i in range(grid + 1)]
    roots = []
    for a, b in zip(xs, xs[1:]):
        ga, gb = g(a), g(b)
        if ga == 0:
            roots.append(a)
            continue
        if ga * gb < 0:
            while b - a > tol:
                m = (a + b) / 2
                if g(a) * g(m) <= 0:
                    b = m
                else:
                    a = m
            roots.append((a + b) / 2)
    if g(hi) == 0:
        roots.append(hi)
    # A sign change can also be a jump (a discontinuous rule): keep only true fixed points.
    return [r for r in roots if abs(g(r)) < 1e-6]


def billiard_ball(strength: float = 1.0) -> Callable[[float], float]:
    """Polchinski's paradox, made continuous.

    x in [0, 1] = how squarely the ball enters the wormhole mouth (1 = dead
    centre). It comes out in the past and hits its younger self with a blow
    proportional to x, knocking it off course: the new entry squareness is
    1 - strength * x. The yes/no version has no solution; this one always has.
    """
    return lambda x: 1 - strength * x


def wobbly_billiard() -> Callable[[float], float]:
    """A loop map with several consistent histories (Echeverria-Klinkhammer-Thorne
    found infinitely many for some initial data: the loop does not pick one)."""
    return lambda x: 0.5 + 0.45 * math.cos(9 * x)


def grandfather_step() -> Callable[[float], float]:
    """Discontinuous rule: if you enter at all (x > 0.5), you knock yourself fully away."""
    return lambda x: 0.0 if x > 0.5 else 1.0
