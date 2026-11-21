"""Waves: how fast information really travels, and whether waves can run backwards.

1. **Phase, group and front velocity.** In a dispersive medium the phase
   velocity can exceed c (plasmas, waveguides) and the group velocity can
   exceed c or even go *negative* (Wang, Kuzmich & Dogariu, Nature 2000:
   the peak of a pulse leaves a gain cell before it enters). None of this
   carries information faster than light: the *front* of a signal, the first
   instant it differs from zero, always moves at exactly c (Sommerfeld &
   Brillouin 1914). ``propagate`` solves Maxwell's equations in a causal
   medium exactly (in frequency space) and shows both effects at once.

2. **Time reversal.** The wave equation is time-symmetric. Record a wave on a
   closed surface, play the recording backwards, and the wave reconverges
   on its source: Fink's time-reversal mirrors (used in medical ultrasound
   and underwater acoustics). ``time_reversal_cavity`` does this through a
   random scattering medium. Add loss and the refocusing degrades: damping
   is where the arrow of time enters.

3. **Advanced waves.** Maxwell's equations allow *retarded* waves (emitted
   after the source acts) and *advanced* waves (converging on the source
   before it acts). Wheeler-Feynman absorber theory (1945) keeps both: a
   perfectly absorbing universe answers each source with half-retarded minus
   half-advanced radiation, which cancels every advanced (backwards-in-time)
   wave and leaves pure retarded radiation. ``absorber_theory`` checks this.

4. **Gravitational waves** carry information at c too: GW170817 and its
   gamma-ray burst arrived 1.7 s apart after 130 million years, so the two
   speeds agree to about 1 part in 10^15.

Units for 1-3: c = 1, dimensionless time and length.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass
from typing import Callable, Sequence

C = 299_792_458.0
G = 6.674_30e-11
M_SUN = 1.988_47e30
MPC = 3.085_677_581e22

# ------------------------------------------------------------------- FFT ---


def fft(a: Sequence[complex], inverse: bool = False) -> list[complex]:
    """Iterative radix-2 FFT. Forward: X_k = sum x_n e^{-2 pi i k n / N}."""
    n = len(a)
    if n & (n - 1):
        raise ValueError("length must be a power of two")
    x = list(map(complex, a))
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            x[i], x[j] = x[j], x[i]
    sign = 1 if inverse else -1
    size = 2
    while size <= n:
        w_step = cmath.exp(sign * 2j * math.pi / size)
        half = size // 2
        for start in range(0, n, size):
            w = 1 + 0j
            for k in range(start, start + half):
                u, v = x[k], x[k + half] * w
                x[k], x[k + half] = u + v, u - v
                w *= w_step
        size *= 2
    if inverse:
        x = [v / n for v in x]
    return x


def _freqs(n: int, dt: float) -> list[float]:
    return [2 * math.pi * (k if k < n // 2 else k - n) / (n * dt) for k in range(n)]


# ------------------------------------------------------------ dispersion ---

Susceptibility = Callable[[float], complex]


def plasma_velocities(omega: float, omega_p: float) -> tuple[float, float]:
    """Phase and group velocity (units of c) for omega^2 = omega_p^2 + c^2 k^2.
    The phase velocity is > c and the group velocity < c; their product is c^2."""
    if omega <= omega_p:
        raise ValueError("below the plasma frequency the wave is evanescent")
    r = math.sqrt(1 - (omega_p / omega) ** 2)
    return 1 / r, r


def lorentz(omega0: float, gamma: float, strength: float) -> Susceptibility:
    """Causal Lorentz-oscillator susceptibility (physics convention e^{-i omega t}).
    strength > 0: an absorption line. strength < 0: a gain line (inverted population)."""
    return lambda w: strength / (omega0**2 - w * w - 1j * gamma * w)


def gain_doublet(center: float, split: float, gamma: float, strength: float) -> Susceptibility:
    """Two gain lines at center +/- split: between them, low loss and steep anomalous
    dispersion, as in the Wang-Kuzmich-Dogariu caesium experiment."""
    a = lorentz(center - split, gamma, -strength)
    b = lorentz(center + split, gamma, -strength)
    return lambda w: a(w) + b(w)


def refractive_index(chi: Susceptibility, w: float) -> complex:
    return cmath.sqrt(1 + chi(w))


def group_index(chi: Susceptibility, w: float, h: float = 1e-5) -> float:
    """n_g = n + omega dn/domega; group velocity = c / n_g. Negative n_g is allowed."""
    n = lambda x: refractive_index(chi, x).real
    return n(w) + w * (n(w + h) - n(w - h)) / (2 * h)


def propagate(signal: Sequence[float], dt: float, chi: Susceptibility, length: float) -> list[float]:
    """Exact propagation of a real field through a slab of ``length`` (c = 1).

    Each frequency picks up exp(i n(omega) omega L). Reflections at the slab faces
    are ignored (index-matched), which does not affect causality. The result
    includes the vacuum delay L, so compare with ``signal`` shifted by L.
    """
    X = fft(signal)
    out = []
    for w, x in zip(_freqs(len(X), dt), X):
        if w == 0:
            out.append(x)
            continue
        aw = abs(w)
        h = cmath.exp(1j * refractive_index(chi, aw) * aw * length)
        # FFT bins use e^{+i omega t}; physics uses e^{-i omega t}: conjugate for omega > 0.
        out.append(x * (h.conjugate() if w > 0 else h))
    return [v.real for v in fft(out, inverse=True)]


def envelope(signal: Sequence[float]) -> list[float]:
    """|analytic signal|: the pulse envelope."""
    X = fft(signal)
    n = len(X)
    Y = [X[0]] + [2 * X[k] for k in range(1, n // 2)] + [X[n // 2]] + [0j] * (n // 2 - 1)
    return [abs(v) for v in fft(Y, inverse=True)]


def _smooth_step(x: float) -> float:
    """0 for x <= 0, 1 for x >= 1, infinitely differentiable in between."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    f = lambda y: math.exp(-1 / y)
    return f(x) / (f(x) + f(1 - x))


@dataclass
class PulseResult:
    group_index: float
    peak_advance: float          # how much earlier the peak exits than in vacuum (>0: "faster than c")
    peak_exits_before_entering: bool
    leak_before_light: float     # max |output| before t_on + L/c, relative to peak (should be ~0)
    signal_just_after_light: float  # max |output| in the 3 time units after t_on + L/c
    group_velocity_front: float  # where the front *would* exit, relative to t_on, if it moved at v_g
    gain_at_peak: float


def superluminal_pulse(*, carrier: float = 10.0, split: float = 0.5, gamma: float = 0.4,
                       strength: float = 5.5, width: float = 12.0, length: float = 0.45,
                       n: int = 8192, dt: float = 0.05, ramp: float = 3.0) -> PulseResult:
    """Send a Gaussian pulse that is exactly zero before t_on through a gain doublet.

    The switch-on is a C-infinity ramp of duration ``ramp``: strictly zero
    before t_on, yet smooth enough that the sampled grid represents it
    faithfully. (A hard step would ring before t_on on any finite grid, a
    numerical artefact that looks like a causality violation.)

    The smooth peak comes out early (negative group velocity), but nothing at all
    comes out until t_on + L: the front moves at c. The early peak is "reshaped"
    out of the leading edge, which already contained all its information.
    """
    chi = gain_doublet(carrier, split, gamma, strength)
    t = [k * dt for k in range(n)]
    t_peak = n * dt / 2
    t_on = t_peak - 3.5 * width
    sig = [_smooth_step((tk - t_on) / ramp) * math.exp(-((tk - t_peak) / width) ** 2 / 2)
           * math.cos(carrier * (tk - t_peak)) for tk in t]
    out = propagate(sig, dt, chi, length)

    env_in, env_out = envelope(sig), envelope(out)
    i_in = max(range(n), key=env_in.__getitem__)
    i_out = max(range(n), key=env_out.__getitem__)
    advance = (t[i_in] + length) - t[i_out]   # vacuum arrival minus actual arrival

    peak = max(abs(v) for v in out)
    light = t_on + length
    before = max(abs(out[k]) for k in range(n) if t[k] < light - 1e-9) / peak
    after = max(abs(out[k]) for k in range(n) if light <= t[k] < light + 3) / peak
    ng = group_index(chi, carrier)
    return PulseResult(ng, advance, t[i_out] < t[i_in], before, after, ng * length,
                       env_out[i_out] / env_in[i_in])


# ---------------------------------------------------------- time reversal ---

@dataclass
class ReversalResult:
    fidelity: float        # correlation of refocused field with the original pulse (1 = perfect)
    amplitude: float       # refocused peak / original peak
    focus_error: int       # grid cells between refocus peak and source


def _step(u: list[float], u_prev: list[float], r2: list[float], damp: list[float]) -> list[float]:
    """Leapfrog step of u_tt = c(x)^2 u_xx - 2 damp u_t, fixed ends.
    With damp = 0 it is exactly time-reversible (swap u and u_prev)."""
    n = len(u)
    nxt = [0.0] * n
    for i in range(1, n - 1):
        lap = u[i + 1] - 2 * u[i] + u[i - 1]
        d = damp[i]
        nxt[i] = (2 * u[i] - (1 - d) * u_prev[i] + r2[i] * lap) / (1 + d)
    return nxt


def time_reversal_cavity(*, cells: int = 400, steps: int = 1500, scatterers: int = 20,
                         contrast: float = 0.6, damping: float = 0.0, mirror: str = "both",
                         seed: int = 3) -> ReversalResult:
    """Fink's time-reversal cavity on a 1-D string with random wave speeds.

    Forward: a pulse at rest in the middle splits, scatters many times, and
    leaves through two "mirror" points into absorbing sponges. Those points
    record u(t). Reverse: start from silence, drive the mirror points with
    the recordings played backwards, and see what forms at the source.

    The leapfrog scheme is exactly time-reversible and, in 1-D, a driven
    point cuts the inside off from the outside. So with no damping and both
    mirrors, the pulse comes back almost perfectly (only the wave still
    trapped inside at the end is lost). With one mirror ("left"/"right"),
    or with ``damping`` inside, it does not: loss is where the arrow of time
    enters.

    ``contrast`` is the slowest patch speed (1 = no scattering). Strong
    contrast traps waves for a long time (1-D Anderson localization): the
    energy still inside when recording stops is lost from the playback.
    """
    import random
    lo = contrast
    rng = random.Random(seed)
    a, b = cells // 6, cells - cells // 6      # mirror positions
    src = cells // 2
    r2 = [1.0] * cells                         # (c dt / dx)^2; Courant number 1 in background
    for _ in range(scatterers):                # random slower patches between the mirrors
        k = rng.randrange(a + 5, b - 8)
        for j in range(k, k + 3):
            r2[j] = rng.uniform(lo, 0.95) ** 2
    damp = [damping if a < i < b else 0.5 * (max(a - i, i - b, 0) / (cells // 6)) ** 2
            for i in range(cells)]

    def run(u, u_prev, drive=None, record=False):
        rec = {a: [], b: []}
        for n_ in range(steps):
            nxt = _step(u, u_prev, r2, damp)
            for pt, series in (drive or {}).items():
                nxt[pt] = series[n_]
            u_prev, u = u, nxt
            if record:
                for pt in rec:
                    rec[pt].append(u[pt])
        return u, rec

    pulse = [math.exp(-((i - src) / 4.0) ** 2) for i in range(cells)]
    _, rec = run(pulse[:], pulse[:], record=True)      # starts at rest: u^-1 = u^0

    # rec[p][k] = u^{k+1}(p). Reverse step k must produce u^{M-1-k}(p):
    # rec[M-2], ..., rec[0], then the initial value.
    def reversed_series(p):
        return rec[p][::-1][1:] + [pulse[p]]

    drive = {}
    if mirror in ("both", "left"):
        drive[a] = reversed_series(a)
    if mirror in ("both", "right"):
        drive[b] = reversed_series(b)
    u, _ = run([0.0] * cells, [0.0] * cells, drive)

    inner = range(a + 1, b)
    dot = sum(u[i] * pulse[i] for i in inner)
    norm = math.sqrt(sum(u[i] ** 2 for i in inner) * sum(pulse[i] ** 2 for i in inner)) or 1.0
    peak_i = max(inner, key=lambda i: abs(u[i]))
    return ReversalResult(dot / norm, abs(u[peak_i]), abs(peak_i - src))


# ------------------------------------------------------- advanced waves ---

@dataclass
class AbsorberResult:
    max_field_before_emission_symmetric: float
    max_field_before_emission_total: float
    max_error_vs_retarded: float


def absorber_theory(emit_time: float = 5.0, positions: Sequence[float] = (-3, -1, 0.5, 2, 4),
                    times: Sequence[float] | None = None, width: float = 0.3) -> AbsorberResult:
    """1-D wave from a source pulse s(t) at x = 0 (c = 1).

    retarded(x, t) = s(t - |x|)       arrives after emission
    advanced(x, t) = s(t + |x|)       converges on the source *before* emission
    Wheeler-Feynman: the source radiates (ret + adv)/2; a perfect absorber
    responds with (ret - adv)/2. The sum is exactly the retarded wave.
    """
    s = lambda t: math.exp(-((t - emit_time) / width) ** 2)
    ret = lambda x, t: s(t - abs(x))
    adv = lambda x, t: s(t + abs(x))
    times = times or [k * 0.01 for k in range(1500)]
    before_sym = before_tot = err = 0.0
    for x in positions:
        for t in times:
            sym = (ret(x, t) + adv(x, t)) / 2
            total = sym + (ret(x, t) - adv(x, t)) / 2
            err = max(err, abs(total - ret(x, t)))
            if t < emit_time - 4 * width:  # well before the source acts
                before_sym = max(before_sym, sym)
                before_tot = max(before_tot, total)
    return AbsorberResult(before_sym, before_tot, err)


# ---------------------------------------------------- gravitational waves ---

def chirp_mass(m1_sun: float, m2_sun: float) -> float:
    return (m1_sun * m2_sun) ** 0.6 / (m1_sun + m2_sun) ** 0.2


def time_to_merger(f_hz: float, mchirp_sun: float) -> float:
    """Leading-order (quadrupole) time from GW frequency f to coalescence, seconds."""
    tc = G * mchirp_sun * M_SUN / C**3
    return 5 / 256 * tc ** (-5 / 3) * (math.pi * f_hz) ** (-8 / 3)


def chirp(f0_hz: float, mchirp_sun: float, f_max_hz: float = 300.0, points: int = 200):
    """(time before merger, frequency) samples of the inspiral chirp."""
    T = time_to_merger(f0_hz, mchirp_sun)
    out = []
    for k in range(points):
        f = f0_hz * (f_max_hz / f0_hz) ** (k / (points - 1))
        out.append((T - time_to_merger(f, mchirp_sun), f))
    return out


def gw_speed_bound(distance_mpc: float = 40.0, delay_s: float = 1.7) -> float:
    """|v_gw - c| / c implied if the whole delay were due to a speed difference."""
    return C * delay_s / (distance_mpc * MPC)


def lookback_years(distance_mpc: float) -> float:
    """How old the information is when it reaches us (ignoring cosmic expansion)."""
    return distance_mpc * MPC / C / (365.25 * 86400)
