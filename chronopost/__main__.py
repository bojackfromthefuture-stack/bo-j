"""Command line: python -m chronopost {seal,open,calibrate,past,physics}."""

from __future__ import annotations

import argparse
import math
import sys
import time

from . import future, past
from .physics import dimensions as D, entropy as EN, particles as P, relativity as R, squeezing as SQ, \
    twotime as TT, waves as WV, wormhole as W


def _bar(phase: str, frac: float) -> None:
    width = 40
    done = int(frac * width)
    end = "\n" if frac >= 1 else ""
    sys.stderr.write(f"\r  {phase:<9} [{'#' * done}{'.' * (width - done)}] {frac:6.1%}{end}")
    sys.stderr.flush()


# ----------------------------------------------------------------- future ---

def cmd_calibrate(a):
    cal = future.calibrate(a.bits, attacker_speedup=a.attacker_speedup)
    print(f"backend {cal.backend}: {cal.local_rate:,.0f} squarings/s here; "
          f"assumed attacker {cal.attacker_rate:,.0f}/s ({a.bits}-bit modulus)")
    if cal.backend == "python":
        print("  note: gmpy2 not installed; attacker rate scaled by "
              f"{future.PYTHON_VS_GMP_FACTOR}x (pip install gmpy2 to open faster)")
    print(f"hash chain: {cal.hash_local_rate:,.0f} SHA-256/s here (1 core, {cal.cores} cores); "
          f"assumed attacker {cal.hash_attacker_rate:,.0f}/s")
    for label, s in [("1 minute", 60), ("1 hour", 3600), ("1 day", 86400), ("1 year", 31_557_600)]:
        h = cal.hashes_for(s)
        print(f"  {label:>8}: t = {cal.t_for(s):,} squarings | {h:,} hashes "
              f"(sealing the chain here: {future._fmt(cal.seal_seconds(h))})")


def cmd_seal(a):
    msg = a.message.encode() if a.message is not None else sys.stdin.buffer.read()
    cal = future.calibrate(a.bits, attacker_speedup=a.attacker_speedup)
    if a.seconds and a.mode != "rsw":
        est = cal.seal_seconds(cal.hashes_for(a.seconds))
        print(f"building the hash chain takes about {future._fmt(est)} on {cal.cores} cores "
              "(post-quantum locks have no trapdoor)", file=sys.stderr)
    cap = future.seal(msg, mode=a.mode, t=a.t, chain_hashes=a.hashes, seconds=a.seconds,
                      modulus_bits=a.bits, note=a.note, calibration=cal, links=a.links,
                      pad_to=a.pad, allow_insecure=a.allow_insecure)
    with open(a.out, "w") as f:
        f.write(cap.to_json())
    print(f"sealed {len(msg)} bytes into {a.out} (id {cap.capsule_id()}, mode {cap.mode})")
    print("  " + cal.describe(cap))


def cmd_open(a):
    with open(a.capsule) as f:
        cap = future.TimeCapsule.from_json(f.read(), min_bits=0 if a.allow_insecure else future.MIN_MODULUS_BITS)
    if cap.note:
        print(f"note (authenticated): {cap.note}", file=sys.stderr)
    work = []
    if cap.uses_rsw:
        work.append(f"{cap.t:,} squarings ({future.BACKEND})")
    if cap.uses_chain:
        work.append(f"{cap.chain_total:,} hashes in {len(cap.chain_links) + 1} links")
    print(f"opening {cap.capsule_id()} [{cap.mode}]: " + " + ".join(work), file=sys.stderr)
    start = time.perf_counter()
    msg = future.open_capsule(cap, progress=None if a.parallel else _bar,
                              checkpoint=a.checkpoint, parallel=a.parallel)
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


def ph_twotime():
    print("1. Is there a past and a future? (connected pieces of the timelike directions)")
    for t, x in [(1, 1), (1, 2), (2, 1)]:
        print(f"  {t} time + {x} space: {TT.timelike_components(t, x)} piece(s); "
              f"forward can be turned into backward: {TT.reverse_time_continuously(t)}")
    print("  => with two times there is no invariant arrow, and a circle in (t1, t2) is a time loop.")
    print("2. Can the future be predicted? Waves with two times, random data at t1 = 0, evolved to t1 = 1:")
    for m in [8, 16, 32, 64]:
        free, con = TT.ultrahyperbolic(m), TT.ultrahyperbolic(m, constrained=True)
        print(f"  resolution {m:>2}: free data amplified x{free.amplification:.1e} | "
              f"Craig-Weinstein-constrained data x{con.amplification:.2f}")
    print("  => free local causes: unpredictable (Hadamard). Nonlocally constrained causes: deterministic.")
    print("3. If time loops (circle of length T = 1):")
    for label, A in [("oscillator, omega = 2pi", TT.oscillator(2 * math.pi)),
                     ("oscillator, omega = 2.2pi", TT.oscillator(2.2 * math.pi)),
                     ("damped oscillator, omega = 2pi", TT.oscillator(2 * math.pi, 0.1))]:
        print(f"  {label:<31}: {TT.loop_consistent_dimension(A, 1.0)} independent consistent histories")
    print(f"  allowed frequencies: {', '.join(f'{w:.2f}' for w in TT.allowed_frequencies(1.0, 4))} ... "
          "(E_n = n h / T: a time loop quantises energy)")
    for label, f in [("billiard ball (continuous)", TT.billiard_ball()),
                     ("billiard ball, many solutions", TT.wobbly_billiard()),
                     ("grandfather (yes/no rule)", TT.grandfather_step())]:
        sols = TT.consistent_histories(f)
        print(f"  {label:<31}: consistent histories at x = {[round(v, 3) for v in sols] or 'none: paradox'}")
    print("  => continuous physics always finds a consistent loop (Brouwer); only all-or-nothing rules fail.")
    print("4. Bars's two-time physics: a gauge symmetry removes the extra time; ordinary physics is its shadow.")


def ph_sidis():
    print("W. J. Sidis, The Animate and the Inanimate (1925), tested claim by claim.")
    k = EN.kac_ring()
    print("A. Reversible laws -> statistical second law (Kac ring, 2000 sites):")
    print(f"  entropy 0 -> {k.entropy[150]:.3f} (max ln2 = 0.693) after 150 steps; reverse the motion -> "
          f"{k.entropy[-1]:.3f}; exact return: {k.returned_exactly}")
    k2 = EN.kac_ring(reverse_error=0.01)
    print(f"  imperfect reversal (1% of markers moved): back to {k2.entropy[-1]:.3f}, not 0")
    print(f"  Poincare recurrence: the whole state repeats after {k.recurrence_step} steps")
    print("B. Reversed regions exist, but rarely (fluctuation theorem, exact):")
    for n in [10, 100, 1000]:
        f = EN.fluctuation_theorem(n)
        print(f"  watched for {n:>4} steps: P(entropy decreased) = {f.p_entropy_decrease:.2e}")
    sig, lnratio = EN.fluctuation_theorem(100).ratio_checks[2]
    print(f"  ln[P(+s)/P(-s)] = {lnratio:.6f} for s = {sig:.6f}: equal, as the theorem says")
    print(f"  odds of any system spontaneously lowering its entropy by just 1 J/K: e^-{1 / EN.K_B:.1e}")
    u = EN.two_boundary_urn()
    pts = ", ".join(f"{x:.1f}" for x in u.entropy_two_boundary[::12])
    print(f"  Schulman: low entropy at BOTH ends of time (40-ball urn): S(t) = {pts}")
    print("  => the second half runs with a reversed arrow: Sidis's reversal, set by a future boundary.")
    d = EN.maxwell_demon()
    print("C. Life as a reversal? A demon sorting 60 molecules into one box:")
    print(f"  gas entropy lowered by {d.gas_entropy_drop_bits:.1f} bits; memory recorded {d.memory_bits:.1f} bits;"
          f" erasing it costs >= {d.erasure_cost_bits:.1f} bits; second law holds: {d.second_law_holds}")
    e = EN.earth_budget()
    print(f"  Earth: sunlight in {e.entropy_in_w_per_k:.1e} W/K, infrared out {e.entropy_out_w_per_k:.1e} W/K,"
          f" export {e.export_w_per_k:.1e} W/K; a person ~{EN.human_entropy_production():.2f} W/K")
    print("  => life lowers its own entropy by exporting more; it rides the second law, not against it.")
    b = EN.black_hole()
    print("D. Dark, light-absorbing stars? Black holes, yes, but the opposite of a reversal:")
    print(f"  1 Msun hole: entropy {b.entropy_over_k:.1e} k vs the Sun's ~{EN.sun_entropy_over_k():.0e} k;"
          f" Hawking T = {b.hawking_temperature_k:.1e} K; evaporates in {b.evaporation_years:.0e} yr")
    print("E. No heat death? Open: a low-entropy Big Bang is observed; recurrences need ~e^(10^122) years.")


def ph_squeezing():
    r = SQ.r_from_db(10)
    vs, va = SQ.variances(r)
    print("Squeezed light: quantum noise moved from one quadrature to the other (vacuum = 0.25):")
    print(f"  10 dB: amplitude variance {vs:.4f}, phase variance {va:.3f}, product {vs * va:.4f} = 1/16 (minimum)")
    P = SQ.photon_distribution(1.0, 8)
    print(f"  photons come in pairs (r = 1): P(0..6) = {', '.join(f'{x:.3f}' for x in P[:7])}")
    print("What survives a real detector (15 dB made):")
    for eta, jit in [(1.0, 0.0), (0.97, 0.0), (0.97, 0.002), (0.90, 0.0), (0.70, 0.0)]:
        m = SQ.with_losses(SQ.r_from_db(15), eta, jit)
        print(f"  efficiency {eta:.2f}, phase jitter {jit * 1000:.0f} mrad -> {m.squeezed_db:5.2f} dB below vacuum")
    print("Gravitational-wave detector quantum noise, relative to the standard quantum limit (6 dB):")
    print("     f [Hz]   no squeezing   fixed angle   frequency-dependent")
    for f in [10, 30, 100, 300, 1000]:
        print(f"  {f:>8} {SQ.interferometer_noise(f):14.3f} {SQ.interferometer_noise(f, SQ.r_from_db(6)):13.3f}"
              f" {SQ.interferometer_noise(f, SQ.r_from_db(6), frequency_dependent=True):21.3f}")
    print("  => fixed squeezing trades shot noise for radiation pressure; rotating it (LIGO since 2023)"
          " wins everywhere, even below the SQL.")
    t = SQ.two_mode(1.0)
    print("Two-mode squeezing = EPR entanglement. Bob's X variance when Alice does nothing / measures X / P:")
    print(f"  {t.bob_variance_alice_idle:.3f} / {t.bob_variance_alice_measures_x:.3f} / "
          f"{t.bob_variance_alice_measures_p:.3f}  (no signal)")
    print(f"  with Alice's result in hand: {t.conditional_variance:.3f}; EPR product {t.epr_product:.4f} < 1/16;"
          f" Duan sum {t.duan_sum:.3f} < 1 (entangled)")
    print("  => correlations need Alice's light-speed message: squeezing sharpens, it never sends back.")


TOPICS = {"antitelephone": ph_antitelephone, "gps": ph_gps, "rocket": ph_rocket,
          "wormhole": ph_wormhole, "dimensions": ph_dimensions, "cycle": ph_cycle,
          "waves": ph_waves, "squeezing": ph_squeezing, "twotime": ph_twotime, "sidis": ph_sidis}


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
    g = s.add_mutually_exclusive_group()
    g.add_argument("--seconds", type=float, help="minimum delay against the assumed attacker")
    g.add_argument("-t", type=int, help="exact number of squarings (rsw/hybrid)")
    s.add_argument("--hashes", type=int, help="exact total hash-chain length (hashchain/hybrid)")
    s.add_argument("--mode", choices=future.MODES, default="hybrid",
                   help="rsw: instant to seal, broken by quantum computers; hashchain: post-quantum, "
                        "sealer does the work in parallel; hybrid (default): both")
    s.add_argument("--links", type=int, help="parallel hash-chain links (default 4 per core)")
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
    o.add_argument("--parallel", action="store_true", help="hybrid: run both locks at once on two cores")
    o.add_argument("--allow-insecure", action="store_true")
    o.set_defaults(fn=cmd_open)

    pa = sub.add_parser("past", help="logic of messages sent to the past (Novikov, Deutsch)")
    pa.add_argument("scenario", nargs="?", default="all", choices=["all", *past.SCENARIOS])
    pa.set_defaults(fn=cmd_past)

    ph = sub.add_parser("physics", help="real-physics simulations: relativity, wormholes, dimensions, matter/energy, waves, squeezing, two times, entropy")
    ph.add_argument("topic", nargs="?", default="all", choices=["all", *TOPICS])
    ph.set_defaults(fn=cmd_physics)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
