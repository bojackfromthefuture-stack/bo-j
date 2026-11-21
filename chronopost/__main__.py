"""Command line: python -m chronopost {seal,open,calibrate,past,physics}."""

from __future__ import annotations

import argparse
import math
import sys
import time

from . import future, past
from .physics import dimensions as D, particles as P, relativity as R, waves as WV, wormhole as W


def _bar(frac: float) -> None:
    width = 40
    done = int(frac * width)
    end = "\n" if frac >= 1 else ""
    sys.stderr.write(f"\r  [{'#' * done}{'.' * (width - done)}] {frac:6.1%}{end}")
    sys.stderr.flush()


# ----------------------------------------------------------------- future ---

def cmd_calibrate(a):
    cal = future.calibrate(a.bits, attacker_speedup=a.attacker_speedup)
    print(f"backend {cal.backend}: {cal.local_rate:,.0f} squarings/s here; "
          f"assumed attacker {cal.attacker_rate:,.0f}/s ({a.bits}-bit modulus)")
    if cal.backend == "python":
        print("  note: gmpy2 not installed; attacker rate scaled by "
              f"{future.PYTHON_VS_GMP_FACTOR}x (pip install gmpy2 to open faster)")
    for label, s in [("1 minute", 60), ("1 hour", 3600), ("1 day", 86400), ("1 year", 31_557_600)]:
        print(f"  {label:>8}: t = {cal.t_for(s):,}")


def cmd_seal(a):
    msg = a.message.encode() if a.message is not None else sys.stdin.buffer.read()
    cal = None
    if a.t is None:
        cal = future.calibrate(a.bits, attacker_speedup=a.attacker_speedup)
    cap = future.seal(msg, t=a.t, seconds=a.seconds, modulus_bits=a.bits, note=a.note,
                      calibration=cal, pad_to=a.pad, allow_insecure=a.allow_insecure)
    with open(a.out, "w") as f:
        f.write(cap.to_json())
    print(f"sealed {len(msg)} bytes into {a.out} (id {cap.capsule_id()}, t = {cap.t:,})")
    if cal:
        print("  " + cal.describe(cap.t))


def cmd_open(a):
    with open(a.capsule) as f:
        cap = future.TimeCapsule.from_json(f.read(), min_bits=0 if a.allow_insecure else future.MIN_MODULUS_BITS)
    if cap.note:
        print(f"note (authenticated): {cap.note}", file=sys.stderr)
    print(f"opening {cap.capsule_id()}: {cap.t:,} sequential squarings ({future.BACKEND})",
          file=sys.stderr)
    start = time.perf_counter()
    msg = future.open_capsule(cap, progress=_bar, checkpoint=a.checkpoint)
    print(f"opened in {time.perf_counter() - start:.1f}s", file=sys.stderr)
    sys.stdout.buffer.write(msg + b"\n")


# ------------------------------------------------------------------- past ---

def cmd_past(a):
    names = list(past.SCENARIOS) if a.scenario == "all" else [a.scenario]
    for name in names:
        s = past.SCENARIOS[name]
        print(f"== {s.name} ==\n{s.story}")
        nov, deu = s.run()
        if nov is not None:
            print(f"  Novikov: {nov.verdict}")
            if len(nov.consistent) > 1:
                print(f"           consistent: {nov.consistent}")
        if deu is not None:
            dist = ", ".join(f"{k!r}: {v:.3f}" for k, v in deu.distribution.items())
            print(f"  Deutsch: stationary mixture {{{dist}}}")
        print()


# ---------------------------------------------------------------- physics ---

def ph_antitelephone():
    print("Alice sends a faster-than-light signal to Bob, 1 light-year away, who moves")
    print("away at 0.8c. Bob replies at the same speed in his own frame.")
    print(f"  threshold signal speed for a reply into the past: {R.past_signalling_threshold(0.8 * R.C) / R.C:.2f}c")
    for u in [1.5, 2.0, 3.0, 10.0, 1e6]:
        r = R.antitelephone(R.LY, 0.8 * R.C, u * R.C)
        when = r.answer_received.t / R.YEAR
        tag = "BEFORE the question" if r.answer_before_question else "after the question"
        print(f"  signal {u:>9g}c: answer arrives at t = {when:+.3f} yr  ({tag})")
    print("  => relativity + any FTL signal = messages to the past. No FTL signal is known.")


def ph_gps():
    g = R.gps_offset()
    print("GPS satellite clock vs a ground clock (time travel to the future, measured daily):")
    print(f"  gravity (weaker field up there): {g.gravitational_us_per_day:+.2f} us/day")
    print(f"  speed (3.9 km/s orbit):          {g.velocity_us_per_day:+.2f} us/day")
    print(f"  net:                             {g.net_us_per_day:+.2f} us/day "
          f"(~{g.net_us_per_day * 1e-6 * R.C / 1000:.1f} km/day error if uncorrected)")


def ph_rocket():
    print("Constant 1 g rocket, accelerate halfway, decelerate, and back (twin paradox):")
    for name, d in [("Proxima Centauri", 4.24), ("Galactic centre", 26_000), ("Andromeda", 2.5e6)]:
        r = R.rocket_trip(d)
        print(f"  {name:<17} {d:>10,g} ly: crew ages {r.ship_years:7.1f} yr, Earth ages "
              f"{r.earth_years:13,.1f} yr; peak gamma {r.peak_gamma:,.0f}")


def ph_wormhole():
    prof = W.out_and_park(0.99, 10, 1)
    w = W.simulate(prof, prof.total + R.YEAR, 100_000)
    print("Wormhole time machine (Morris-Thorne-Yurtsever): mouth B flies at 0.99c for 10 yr,")
    print("comes back and parks 1 ly from mouth A.")
    print(f"  B's clock lags A's by        {w.lag_s / R.YEAR:.2f} yr (analytic "
          f"{W.analytic_lag(0.99, prof.total) / R.YEAR:.2f})")
    print(f"  light travel time A -> B:     {w.separation_m / R.C / R.YEAR:.2f} yr")
    print(f"  closed timelike curve?        {w.is_time_machine}")
    print(f"  a radio message looped once arrives {w.max_lookback_s / R.YEAR:.2f} yr before it was sent")
    print(f"  earliest reachable time:      t = {w.ctc_onset_s / R.YEAR:.2f} yr (never before the machine exists)")
    print("  caveats: needs negative-energy exotic matter; chronology protection may forbid it.")


def ph_dimensions():
    print("Orbits with a 2% speed kick, gravity in n spatial dimensions (F ~ 1/r^(n-1)):")
    for n in [2, 3, 4, 5, 6]:
        o = D.orbit(n)
        w2 = D.radial_frequency_squared(n)
        kind = "stable" if w2 > 0 else ("marginal" if w2 == 0 else "unstable")
        print(f"  n={n}: r in [{o.r_min:.3f}, {o.r_max:.3f}] -> {o.fate:<9} (linear theory: {kind})")
    print("Kaluza-Klein: a hidden circular dimension of radius R gives a mass tower:")
    for r in [1e-35, 1e-19, 1e-18]:
        tower = ", ".join(f"{m:,.4g}" for m in D.kk_tower(r, 3))
        print(f"  R = {r:.0e} m -> {tower} GeV ...")
    print("  colliders see no tower below a few TeV, so R < ~1e-19 m.")
    print("Two time dimensions: a circle in the (t1, t2) plane")
    print(f"  closed timelike curve with 1 time dim?  {D.is_closed_timelike(D.time_circle(), 1)}")
    print(f"  closed timelike curve with 2 time dims? {D.is_closed_timelike(D.time_circle(), 2)}"
          "  (causality fails without any exotic matter)")


def ph_cycle():
    print("matter -> energy -> matter -> energy, head-on e+ e- at 5 MeV kinetic each:")
    for s in P.matter_energy_matter():
        sqrt_s = sum(s.outputs, P.P4(0.0)).mass
        outs = ", ".join(f"E={p.E:.4f}" for p in s.outputs)
        print(f"  {s.process:<22} out: {outs} MeV | sqrt(s) = {sqrt_s:.6f} | "
              f"4-momentum error {s.conservation_error:.1e}")
    print(f"  pair threshold sqrt(s) >= 2 m_e = {2 * P.M_E:.6f} MeV")
    print(f"  pair off a proton needs E_gamma >= {P.bethe_heitler_threshold(938.272_088):.6f} MeV")
    peak = max((P.sigma_breit_wheeler(4 * P.M_E**2 / (1 - b * b)), b) for b in
               (i / 1000 for i in range(1, 1000)))
    print(f"  Breit-Wheeler peak cross section {peak[0] / P.SIGMA_T:.3f} sigma_T at beta = {peak[1]:.2f}")
    print("Feynman-Stueckelberg: the same history as a single electron")
    for seg in P.worldline_reading():
        print(f"  {seg.particle:<24} t {seg.t_start:+5.1f} -> {seg.t_end:+5.1f}, "
              f"x {seg.x_start:+.1f} -> {seg.x_end:+.1f}")
    print("  a symmetry of the equations (CPT), not a channel: no message can ride it.")


def ph_waves():
    vp, vg = WV.plasma_velocities(2.0, 1.0)
    print("Plasma at twice its plasma frequency:")
    print(f"  phase velocity {vp:.3f}c (> c), group velocity {vg:.3f}c (< c), product {vp * vg:.3f}c^2")
    r = WV.superluminal_pulse()
    print("Pulse through a gain-doublet cell (Wang-Kuzmich-Dogariu 2000 style), c = 1, L = 0.45:")
    print(f"  group index {r.group_index:+.2f}: the peak exits {r.peak_advance:.2f} time units early;"
          f" before it enters? {r.peak_exits_before_entering}")
    print(f"  if the signal moved at v_g it would exit {-r.group_velocity_front:.2f} before it was switched on")
    print(f"  actual output before light could arrive: {r.leak_before_light:.1e} of peak (rounding error)")
    print(f"  output in the 3 time units after light arrives: {r.signal_just_after_light:.1e} of peak")
    print("  => the front moves at exactly c. The early peak carries no new information.")
    print("Time-reversal cavity (Fink): record a scattered pulse at two mirrors, play it backwards:")
    for label, kw in [("lossless, both mirrors", {}), ("one mirror only", {"mirror": "left"}),
                      ("strong disorder (localization)", {"contrast": 0.3}),
                      ("1% damping per step", {"damping": 0.01})]:
        t = WV.time_reversal_cavity(**kw)
        print(f"  {label:<31} fidelity {t.fidelity:.3f}, refocused amplitude {t.amplitude:.3f}")
    print("  => waves run backwards perfectly only if nothing is lost: loss is the arrow of time.")
    a = WV.absorber_theory()
    print("Wheeler-Feynman absorber theory (advanced = backwards-in-time waves):")
    print(f"  field before emission, time-symmetric source alone: {a.max_field_before_emission_symmetric:.3f}")
    print(f"  field before emission, with the universe's absorber:  {a.max_field_before_emission_total:.1e}")
    mc = WV.chirp_mass(36, 29)
    print("Gravitational waves:")
    print(f"  GW150914 (36 + 29 Msun): chirp mass {mc:.1f} Msun, 35 Hz -> merger in "
          f"{WV.time_to_merger(35, mc):.2f} s; the signal left {WV.lookback_years(410) / 1e9:.1f} Gyr ago")
    print(f"  GW170817: 1.7 s gap after {WV.lookback_years(40) / 1e6:.0f} Myr -> "
          f"|v_gw - c|/c < {WV.gw_speed_bound():.0e}")


TOPICS = {"antitelephone": ph_antitelephone, "gps": ph_gps, "rocket": ph_rocket,
          "wormhole": ph_wormhole, "dimensions": ph_dimensions, "cycle": ph_cycle,
          "waves": ph_waves}


def cmd_physics(a):
    for name in (TOPICS if a.topic == "all" else [a.topic]):
        print(f"== {name} ==")
        TOPICS[name]()
        print()


# ------------------------------------------------------------------- main ---

def main(argv=None):
    p = argparse.ArgumentParser(prog="chronopost", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("calibrate", help="measure sequential squaring speed")
    c.add_argument("--bits", type=int, default=future.MIN_MODULUS_BITS)
    c.add_argument("--attacker-speedup", type=float, default=1.0)
    c.set_defaults(fn=cmd_calibrate)

    s = sub.add_parser("seal", help="send a message to the future")
    s.add_argument("message", nargs="?", help="text (default: read stdin)")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--seconds", type=float, help="minimum delay against the assumed attacker")
    g.add_argument("-t", type=int, help="exact number of squarings")
    s.add_argument("-o", "--out", default="capsule.json")
    s.add_argument("--bits", type=int, default=future.MIN_MODULUS_BITS)
    s.add_argument("--attacker-speedup", type=float, default=1.0,
                   help="how much faster than optimised software here the attacker is (e.g. 10 for an ASIC)")
    s.add_argument("--pad", type=int, default=future.DEFAULT_PAD, help="pad length to a multiple of this")
    s.add_argument("--note", default="", help="public label, stored in clear but authenticated")
    s.add_argument("--allow-insecure", action="store_true", help="permit modulus below 2048 bits (testing)")
    s.set_defaults(fn=cmd_seal)

    o = sub.add_parser("open", help="do the work and read a capsule")
    o.add_argument("capsule")
    o.add_argument("--checkpoint", help="file to save/resume progress")
    o.add_argument("--allow-insecure", action="store_true")
    o.set_defaults(fn=cmd_open)

    pa = sub.add_parser("past", help="logic of messages sent to the past (Novikov, Deutsch)")
    pa.add_argument("scenario", nargs="?", default="all", choices=["all", *past.SCENARIOS])
    pa.set_defaults(fn=cmd_past)

    ph = sub.add_parser("physics", help="real-physics simulations: relativity, wormholes, dimensions, matter/energy, waves")
    ph.add_argument("topic", nargs="?", default="all", choices=["all", *TOPICS])
    ph.set_defaults(fn=cmd_physics)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
