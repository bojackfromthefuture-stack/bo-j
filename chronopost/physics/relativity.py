"""Special and general relativity: what the real laws say about time travel.

* Travel to the future is real and measured: velocity time dilation (muons,
  particle accelerators), gravitational time dilation (GPS), the twin paradox.
* Signals to the past are forbidden by causality *only if* nothing goes faster
  than light. The "tachyonic antitelephone" (Tolman 1917, Benford et al. 1970)
  shows that any faster-than-light signal plus relativity lets you answer a
  message before it was sent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

C = 299_792_458.0            # m/s, exact
G = 6.674_30e-11             # m^3 kg^-1 s^-2
M_EARTH = 5.972_168e24       # kg
R_EARTH = 6.371_0e6          # m, mean radius
GM_EARTH = 3.986_004_418e14  # m^3/s^2 (WGS-84, more precise than G*M)
OMEGA_EARTH = 7.292_115e-5   # rad/s
DAY = 86_400.0
YEAR = 365.25 * DAY
LY = C * YEAR
G0 = 9.806_65                # standard gravity


def gamma(v: float) -> float:
    if abs(v) >= C:
        raise ValueError("|v| must be below c for a massive body")
    return 1.0 / math.sqrt(1.0 - (v / C) ** 2)


@dataclass(frozen=True)
class Event:
    t: float  # s
    x: float  # m

    def boost(self, v: float) -> "Event":
        """The same event seen from a frame moving at +v along x."""
        g = gamma(v)
        return Event(g * (self.t - v * self.x / C**2), g * (self.x - v * self.t))


def interval(a: Event, b: Event) -> float:
    """s^2 = c^2 dt^2 - dx^2. >0 timelike, 0 lightlike, <0 spacelike."""
    return (C * (b.t - a.t)) ** 2 - (b.x - a.x) ** 2


def order_is_invariant(a: Event, b: Event) -> bool:
    """Every observer agrees which event came first iff they are not spacelike-separated."""
    return interval(a, b) >= 0


def add_velocities(u: float, v: float) -> float:
    """Relativistic velocity addition (also used formally for tachyons, |u| > c)."""
    return (u + v) / (1 + u * v / C**2)


# --------------------------------------------------- tachyonic telephone ---

@dataclass
class AntitelephoneResult:
    question_sent: Event
    question_received: Event
    answer_received: Event

    @property
    def answer_before_question(self) -> bool:
        return self.answer_received.t < self.question_sent.t

    @property
    def lead_time(self) -> float:
        return self.question_sent.t - self.answer_received.t


def antitelephone(distance: float, bob_velocity: float, signal_speed: float) -> AntitelephoneResult:
    """Alice (at rest, x=0) sends at t=0 a signal of speed ``signal_speed`` in
    *her* frame to Bob, who is at ``distance`` and moves away at
    ``bob_velocity``. Bob replies at once at the same speed in *his* frame.
    When does the reply reach Alice, in her frame?

    Both signals follow the same physical law (same speed in the sender's rest
    frame), which is what makes the result unavoidable rather than a trick.
    """
    u, v = signal_speed, bob_velocity
    if u <= v:
        raise ValueError("signal never catches Bob")
    t1 = distance / (u - v)
    q = Event(t1, u * t1)
    w = add_velocities(-u, v)        # Bob's reply, seen in Alice's frame
    if w == 0:
        raise ValueError("reply is instantaneous along a line of constant x; never arrives")
    t2 = q.t - q.x / w
    return AntitelephoneResult(Event(0.0, 0.0), q, Event(t2, 0.0))


def past_signalling_threshold(bob_velocity: float) -> float:
    """Minimum signal speed (in sender's frame) for the reply to arrive before t=0.

    Setting t2 < 0 in ``antitelephone`` gives (v/c^2) u^2 - 2u + v > 0, so
    u > c^2 (1 + sqrt(1 - b^2)) / v with b = v/c, independent of distance.
    This is always > c: subluminal signals can never do it.
    """
    b = bob_velocity / C
    return C * (1 + math.sqrt(1 - b * b)) / b


# --------------------------------------------------------- time dilation ---

def gravitational_rate(r: float, gm: float = GM_EARTH) -> float:
    """dtau/dt for a static clock at radius r (Schwarzschild, exact)."""
    return math.sqrt(1 - 2 * gm / (r * C**2))


def clock_rate(r: float, v: float, gm: float = GM_EARTH) -> float:
    """dtau/dt for a clock at radius r moving at speed v (weak-field, exact in Schwarzschild
    for circular motion when v is the local orbital speed)."""
    return math.sqrt(1 - 2 * gm / (r * C**2) - (v / C) ** 2)


@dataclass
class GPSResult:
    gravitational_us_per_day: float
    velocity_us_per_day: float
    net_us_per_day: float


def gps_offset(orbit_radius: float = 26_561_750.0) -> GPSResult:
    """How much faster a GPS satellite clock runs than a clock on the ground.

    Real engineering: GPS clocks are set 4.4647e-10 slow before launch to
    cancel this, or positions would drift ~10 km/day.
    """
    v_sat = math.sqrt(GM_EARTH / orbit_radius)
    v_gnd = OMEGA_EARTH * R_EARTH  # equator
    grav = (gravitational_rate(orbit_radius) - gravitational_rate(R_EARTH)) * DAY * 1e6
    vel = (clock_rate(orbit_radius, v_sat) / gravitational_rate(orbit_radius)
           - clock_rate(R_EARTH, v_gnd) / gravitational_rate(R_EARTH)) * DAY * 1e6
    net = (clock_rate(orbit_radius, v_sat) - clock_rate(R_EARTH, v_gnd)) * DAY * 1e6
    return GPSResult(grav, vel, net)


# ---------------------------------------------------- relativistic rocket ---

@dataclass
class RocketTrip:
    distance_ly: float
    ship_years: float
    earth_years: float
    peak_gamma: float
    peak_speed_c: float

    @property
    def years_into_future(self) -> float:
        return self.earth_years - self.ship_years


def rocket_trip(distance_ly: float, accel: float = G0, round_trip: bool = True) -> RocketTrip:
    """Constant proper acceleration to the midpoint, then constant deceleration.

    Hyperbolic motion: x = c^2/a (cosh(a tau/c) - 1), t = c/a sinh(a tau/c).
    A round trip doubles everything: this is the twin paradox, done properly.
    """
    half = distance_ly * LY / 2
    tau_half = (C / accel) * math.acosh(1 + accel * half / C**2)
    t_half = (C / accel) * math.sinh(accel * tau_half / C)
    k = 4 if round_trip else 2
    g = math.cosh(accel * tau_half / C)
    return RocketTrip(distance_ly, k * tau_half / YEAR, k * t_half / YEAR, g,
                      math.tanh(accel * tau_half / C))
