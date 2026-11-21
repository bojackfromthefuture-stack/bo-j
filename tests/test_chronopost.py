import dataclasses
import json
import math

import pytest

from chronopost import future, past
from chronopost.physics import dimensions as D, particles as P, relativity as R, wormhole as W

BITS = 512  # small modulus keeps tests fast; real use enforces >= 2048


def _seal(msg=b"hello, future", mode="hybrid", t=500, chain=3000, **kw):
    kw.setdefault("links", 5)
    return future.seal(msg, mode=mode, t=t, chain_hashes=chain, modulus_bits=BITS,
                       allow_insecure=True, **kw)


def _load(cap):
    return future.TimeCapsule.from_json(cap.to_json(), min_bits=0)


# ------------------------------------------------------------- future ---

@pytest.mark.parametrize("mode", future.MODES)
def test_roundtrip_all_modes(mode):
    cap = _seal(mode=mode, note="for later")
    assert future.open_capsule(_load(cap)) == b"hello, future"


def test_hybrid_parallel_open():
    assert future.open_capsule(_seal(), parallel=True) == b"hello, future"


def test_empty_and_binary_messages():
    for msg in [b"", bytes(range(256)) * 3, b"\x80\x00\x00"]:
        assert future.open_capsule(_seal(msg)) == msg


def test_padding_hides_exact_length():
    assert len(_seal(b"a").ciphertext) == len(_seal(b"a" * 200).ciphertext) == 256


def test_hashchain_needs_every_link_in_order():
    cap = _seal(mode="hashchain", chain=1000, links=4)
    assert cap.chain_steps == 250 and len(cap.chain_links) == 3 and cap.chain_total == 1000
    # Knowing only the final link's work is not enough: each link's start is encrypted
    # under the previous link's end.
    wrong_end = future._chain(cap.chain_links[-1], cap.chain_steps)
    with pytest.raises(ValueError):
        future.decrypt(cap, None, wrong_end)


def test_hashchain_needs_no_modulus():
    cap = _seal(mode="hashchain")
    assert cap.n == 0 and "n" not in json.loads(cap.to_json())
    future.TimeCapsule.from_json(cap.to_json())   # no min_bits issue: no RSW part


def test_hybrid_needs_both_secrets():
    cap = _seal()
    x = future.solve_rsw(cap)
    end = future.solve_chain(cap)
    assert future.decrypt(cap, x, end) == b"hello, future"
    with pytest.raises(ValueError):
        future.decrypt(cap, x, b"\0" * 32)          # quantum attacker who only factored n
    with pytest.raises(ValueError):
        future.decrypt(cap, 2, end)


def test_rejects_small_modulus_by_default():
    with pytest.raises(future.InsecureParameters):
        future.seal(b"x", mode="rsw", t=10, modulus_bits=1024)
    with pytest.raises(future.InsecureParameters):
        future.TimeCapsule.from_json(_seal(mode="rsw").to_json())


@pytest.mark.parametrize("field,value", [
    ("t", 499), ("note", "forged"), ("sealed_at", 0), ("chain_steps", 599),
    ("mode", "hashchain"), ("n", None), ("nonce", None), ("ciphertext", None), ("tag", None),
    ("chain_seed", None), ("chain_links", None),
])
def test_any_tampering_is_detected(field, value):
    cap = _seal(note="original")
    if value is None:
        if field == "n":
            value = cap.n + 2
        elif field == "chain_links":
            value = cap.chain_links[1:] + cap.chain_links[:1]
        else:
            b = bytearray(getattr(cap, field)); b[0] ^= 1; value = bytes(b)
    bad = dataclasses.replace(cap, **{field: value})
    with pytest.raises(ValueError):
        future.open_capsule(bad)


def test_strict_parsing():
    d = json.loads(_seal().to_json())
    for mutate in [
        lambda d: d.update(version=2),
        lambda d: d.update(mode="quantum-magic"),
        lambda d: d.update(t="500"),
        lambda d: d.update(t=0),
        lambda d: d.update(n="zz"),
        lambda d: d.update(chain_steps=0),
        lambda d: d.update(chain_links=["AAAA"]),
        lambda d: d.update(nonce="not base64!"),
        lambda d: d.update(format="other"),
    ]:
        x = dict(d); mutate(x)
        with pytest.raises((ValueError, KeyError)):
            future.TimeCapsule.from_json(json.dumps(x), min_bits=0)


def test_modulus_quality():
    n, phi = future._generate_modulus(BITS)
    assert n.bit_length() == BITS and n % 2 == 1


def test_checkpoint_resume(tmp_path):
    cap = _seal(t=3000, chain=4000, links=4)
    path = str(tmp_path / "cp.json")
    cp = future.Checkpoint(path, cap)
    x_mid = 2
    for _ in range(1000):
        x_mid = x_mid * x_mid % cap.n
    v = future._chain(cap.chain_seed, 300)
    cp.state = {"rsw": {"i": 1000, "x": format(x_mid, "x")},
                "chain": {"link": 0, "j": 300, "v": v.hex()}}
    cp.save()
    assert future.open_capsule(cap, checkpoint=path) == b"hello, future"


def test_forged_checkpoint_cannot_forge_message(tmp_path):
    cap = _seal()
    path = str(tmp_path / "cp.json")
    cp = future.Checkpoint(path, cap)
    cp.state = {"chain": {"link": 0, "j": 10, "v": "00" * 32}}
    cp.save()
    with pytest.raises(ValueError):
        future.open_capsule(cap, checkpoint=path)


def test_checkpoint_bound_to_capsule(tmp_path):
    a, b = _seal(), _seal()
    path = str(tmp_path / "cp.json")
    future.Checkpoint(path, a).save()
    with pytest.raises(ValueError):
        future.open_capsule(b, checkpoint=path)


def test_calibration_is_conservative():
    cal = future.calibrate(BITS, attacker_speedup=10, sample=2000, hash_sample=20000)
    assert cal.attacker_rate >= 10 * cal.local_rate
    assert cal.hash_attacker_rate >= 10 * cal.hash_local_rate
    assert cal.t_for(1.0) >= int(cal.attacker_rate)


def test_seconds_sets_both_locks():
    cal = future.Calibration("python", 1000.0, 1000.0, 5000.0, 5000.0, 2)
    cap = future.seal(b"x", seconds=2, calibration=cal, modulus_bits=BITS,
                      allow_insecure=True, links=4)
    assert cap.t == 2000 and cap.chain_total >= 10000
    assert "quantum attacker >= " in cal.describe(cap)
    rsw = future.seal(b"x", mode="rsw", seconds=2, calibration=cal, modulus_bits=BITS,
                      allow_insecure=True)
    assert "Shor" in cal.describe(rsw)


# --------------------------------------------------------------- past ---

def test_grandfather_is_paradox_but_deutsch_mixes():
    nov, deu = past.SCENARIOS["grandfather"].run()
    assert nov.consistent == []
    assert deu.distribution == {True: 0.5, False: 0.5}


def test_bootstrap_and_prophecy():
    assert len(past.SCENARIOS["bootstrap"].run()[0].consistent) == 3
    assert past.SCENARIOS["prophecy"].run()[0].consistent == ["rain"]


def test_noisy_grandfather():
    _, deu = past.SCENARIOS["noisy-grandfather"].run()
    assert deu.distribution[True] == pytest.approx(1 / 1.7, abs=1e-6)


def test_ctc_factoring():
    assert past.ctc_solve(range(2, 2021), lambda d: 2021 % d == 0).consistent == [43, 47]


# ------------------------------------------------------------ physics ---

def test_lorentz_preserves_interval_and_light_speed():
    a, b = R.Event(0, 0), R.Event(3.0, 1e8)
    for v in [0.1 * R.C, 0.9 * R.C, -0.5 * R.C]:
        assert R.interval(a.boost(v), b.boost(v)) == pytest.approx(R.interval(a, b), rel=1e-9)
    assert R.add_velocities(R.C, 0.7 * R.C) == pytest.approx(R.C)


def test_spacelike_order_can_flip():
    a, b = R.Event(0, 0), R.Event(1.0, 2 * R.C)  # spacelike
    assert not R.order_is_invariant(a, b)
    assert b.boost(0.9 * R.C).t < a.boost(0.9 * R.C).t


def test_antitelephone():
    v = 0.8 * R.C
    thr = R.past_signalling_threshold(v)
    assert thr == pytest.approx(2 * R.C)
    assert R.antitelephone(R.LY, v, 1.01 * thr).answer_before_question
    assert not R.antitelephone(R.LY, v, 0.99 * thr).answer_before_question
    for b in [0.1, 0.5, 0.99]:
        assert R.past_signalling_threshold(b * R.C) > R.C


def test_gps_matches_published_38_us_per_day():
    g = R.gps_offset()
    assert g.gravitational_us_per_day == pytest.approx(45.7, abs=0.2)
    assert g.velocity_us_per_day == pytest.approx(-7.2, abs=0.2)
    assert g.net_us_per_day == pytest.approx(38.6, abs=0.3)


def test_rocket_slow_limit_and_proxima():
    r = R.rocket_trip(1e-6)
    assert r.ship_years == pytest.approx(r.earth_years, rel=1e-6)
    p = R.rocket_trip(4.24)
    assert p.ship_years == pytest.approx(7.08, abs=0.05)
    assert p.earth_years > p.ship_years


def test_wormhole_time_machine():
    prof = W.out_and_park(0.99, 10, 1)
    w = W.simulate(prof, prof.total + R.YEAR, 50_000)
    assert w.lag_s == pytest.approx(W.analytic_lag(0.99, prof.total), rel=1e-3)
    assert w.is_time_machine
    assert w.send_back(100 * R.YEAR) < 100 * R.YEAR
    assert w.ctc_onset_s >= prof.total  # not before the machine is built
    slow = W.out_and_park(0.1, 1, 0.09)
    assert not W.simulate(slow, slow.total + R.YEAR, 20_000).is_time_machine


def test_orbits_stable_only_below_four_dimensions():
    assert D.orbit(2).stable and D.orbit(3).stable
    assert not D.orbit(4).stable and not D.orbit(4, -0.02).stable
    assert D.orbit(5).fate == "escaped" and D.orbit(5, -0.02).fate == "collapsed"


def test_kaluza_klein():
    assert D.kk_tower(1e-19, 1)[0] == pytest.approx(1973.27, rel=1e-4)
    assert D.radius_for_mass(D.kk_tower(3e-20, 1)[0]) == pytest.approx(3e-20)


def test_two_times_allow_ctc_one_time_does_not():
    assert D.is_closed_timelike(D.time_circle(), 2)
    assert not D.is_closed_timelike(D.time_circle(), 1)


def test_cycle_conserves_four_momentum():
    for seed in range(5):
        for s in P.matter_energy_matter(kinetic_mev=3.0, seed=seed):
            assert s.conservation_error < 1e-9
            for out in s.outputs:
                expected = 0.0 if "-> gamma" in s.process else P.M_E
                assert out.mass == pytest.approx(expected, abs=1e-6)


def test_annihilation_at_rest_gives_two_511_kev_photons():
    import random
    g1, g2 = P.annihilate(P.P4.at_rest(P.M_E), P.P4.at_rest(P.M_E), random.Random(0))
    assert g1.E == pytest.approx(P.M_E) and g2.E == pytest.approx(P.M_E)
    assert (g1 + g2).p == pytest.approx(0, abs=1e-12)


def test_pair_threshold():
    import random
    assert not P.breit_wheeler_threshold(0.5, 0.5, math.pi)
    assert P.breit_wheeler_threshold(0.52, 0.52, math.pi)
    with pytest.raises(ValueError):
        P.breit_wheeler(P.P4(0.5, 0, 0, 0.5), P.P4(0.5, 0, 0, -0.5), random.Random(0))
    assert P.bethe_heitler_threshold(938.272) == pytest.approx(1.02256, abs=1e-5)


def test_breit_wheeler_peak_is_quarter_thomson():
    peak = max(P.sigma_breit_wheeler(4 * P.M_E**2 / (1 - b * b)) for b in
               (i / 1000 for i in range(1, 1000)))
    assert peak / P.SIGMA_T == pytest.approx(0.256, abs=0.003)


def test_feynman_stueckelberg_single_worldline():
    segs = P.worldline_reading()
    assert segs[1].t_end < segs[1].t_start                  # backwards in time
    assert segs[0].t_end == segs[1].t_start and segs[1].t_end == segs[2].t_start
    assert segs[0].x_end == segs[1].x_start and segs[1].x_end == segs[2].x_start


# -------------------------------------------------------------- waves ---

from chronopost.physics import waves as WV


def test_fft_roundtrip_and_known_transform():
    import random
    x = [random.Random(1).random() for _ in range(128)]
    assert max(abs(a - b) for a, b in zip(x, WV.fft(WV.fft(x), inverse=True))) < 1e-12
    X = WV.fft([math.cos(2 * math.pi * 3 * k / 64) for k in range(64)])
    assert abs(X[3]) == pytest.approx(32) and abs(X[61]) == pytest.approx(32)


def test_plasma_phase_times_group_is_c_squared():
    vp, vg = WV.plasma_velocities(3.0, 1.2)
    assert vp > 1 > vg and vp * vg == pytest.approx(1.0)


def test_vacuum_propagation_is_pure_delay():
    dt, L = 0.05, 2.0
    sig = [math.exp(-((k * dt - 50) / 3) ** 2) for k in range(2048)]
    out = WV.propagate(sig, dt, lambda w: 0j, L)
    shift = int(round(L / dt))
    assert max(abs(out[k + shift] - sig[k]) for k in range(1500)) < 1e-9


def test_superluminal_peak_but_luminal_front():
    r = WV.superluminal_pulse()
    assert r.group_index < 0
    assert r.peak_exits_before_entering and r.peak_advance > 0
    assert r.group_velocity_front < 0            # naive v_g picture: out before switched on
    assert r.leak_before_light < 1e-10           # reality: nothing before t_on + L/c
    assert r.signal_just_after_light > 1e-4      # and something right after it


def test_absorber_cancels_advanced_waves():
    a = WV.absorber_theory()
    assert a.max_field_before_emission_symmetric > 0.4
    assert a.max_field_before_emission_total < 1e-12
    assert a.max_error_vs_retarded < 1e-12


def test_time_reversal_cavity():
    full = WV.time_reversal_cavity()
    assert full.fidelity > 0.99 and full.amplitude == pytest.approx(1, abs=0.02)
    assert full.focus_error == 0
    one = WV.time_reversal_cavity(mirror="left")
    lossy = WV.time_reversal_cavity(damping=0.01)
    assert one.amplitude < 0.8 and lossy.amplitude < 0.2 and lossy.fidelity < full.fidelity


def test_gravitational_waves():
    mc = WV.chirp_mass(36, 29)
    assert mc == pytest.approx(28.1, abs=0.2)          # LIGO: ~28-30 Msun (detector frame ~30)
    assert 0.1 < WV.time_to_merger(35, mc) < 0.3        # observed ~0.2 s in band
    f = [p[1] for p in WV.chirp(35, mc)]
    assert all(b > a for a, b in zip(f, f[1:]))
    assert WV.gw_speed_bound() < 1e-15


# ------------------------------------------------------------ two times ---

from chronopost.physics import entropy as EN, squeezing as SQ, twotime as TT


def test_time_orientation():
    assert TT.timelike_components(1, 1) == 2 and TT.timelike_components(1, 2) == 2
    assert TT.timelike_components(2, 1) == 1
    assert TT.reverse_time_continuously(2) and not TT.reverse_time_continuously(1)


def test_ultrahyperbolic_ill_posed_unless_constrained():
    growth = [TT.ultrahyperbolic(m).amplification for m in (8, 16, 32)]
    assert growth[0] < growth[1] < growth[2] and growth[2] > 1e4
    for m in (8, 16, 32):
        c = TT.ultrahyperbolic(m, constrained=True)
        assert c.worst_mode_growth <= 1 + 1e-12 and c.amplification <= 1


def test_time_loop_quantisation():
    assert TT.loop_consistent_dimension(TT.oscillator(2 * math.pi), 1.0) == 2
    assert TT.loop_consistent_dimension(TT.oscillator(4 * math.pi), 1.0) == 2
    assert TT.loop_consistent_dimension(TT.oscillator(2.5 * math.pi), 1.0) == 0
    assert TT.loop_consistent_dimension(TT.oscillator(2 * math.pi, 0.05), 1.0) == 0


def test_continuous_loops_always_consistent_discontinuous_can_fail():
    assert TT.consistent_histories(TT.billiard_ball()) == [pytest.approx(0.5)]
    assert len(TT.consistent_histories(TT.wobbly_billiard())) >= 3
    assert TT.consistent_histories(TT.grandfather_step()) == []
    for s in (0.3, 0.7, 1.0):  # Brouwer: any continuous self-map of [0,1]
        assert TT.consistent_histories(TT.billiard_ball(s))


# --------------------------------------------------------------- Sidis ---

def test_kac_ring_reversal_and_recurrence():
    k = EN.kac_ring()
    assert k.entropy[0] == 0 and max(k.entropy) > 0.69
    assert k.returned_exactly and k.entropy[-1] == 0
    assert k.recurrence_step in (2000, 4000)
    assert not EN.kac_ring(reverse_error=0.01).returned_exactly


def test_fluctuation_theorem_exact():
    for n in (10, 101, 500):
        f = EN.fluctuation_theorem(n)
        for s, lnr in f.ratio_checks:
            assert lnr == pytest.approx(s, rel=1e-9)
    ps = [EN.fluctuation_theorem(n).p_entropy_decrease for n in (10, 100, 1000)]
    assert ps[0] > ps[1] > ps[2]


def test_schulman_two_boundary_reversed_arrow():
    u = EN.two_boundary_urn(balls=30, duration=80)
    S, T = u.entropy_two_boundary, len(u.entropy_two_boundary) - 1
    assert S[0] == pytest.approx(0) and S[T] == pytest.approx(0)
    assert S[T // 2] > 15
    assert all(S[t + 1] <= S[t] + 1e-9 for t in range(T // 2 + 5, T))  # entropy falling
    assert u.entropy_forward_only[T] > 15                             # without the future boundary


def test_maxwell_demon_pays():
    d = EN.maxwell_demon()
    assert d.memory_bits >= d.gas_entropy_drop_bits and d.second_law_holds


def test_earth_and_black_hole():
    e = EN.earth_budget()
    assert e.export_w_per_k == pytest.approx(6.1e14, rel=0.05)
    b = EN.black_hole()
    assert b.entropy_over_k == pytest.approx(1.05e77, rel=0.02)
    assert b.hawking_temperature_k == pytest.approx(6.17e-8, rel=0.01)
    assert b.entropy_over_k > 1e17 * EN.sun_entropy_over_k()


# ------------------------------------------------------------ squeezing ---

def test_squeezing_minimum_uncertainty_and_db():
    r = SQ.r_from_db(10)
    vs, va = SQ.variances(r)
    assert vs * va == pytest.approx(1 / 16) and SQ.db(r) == pytest.approx(10)
    assert SQ.quadrature_variance(r, math.pi / 2) == pytest.approx(va)


def test_photons_in_pairs():
    P = SQ.photon_distribution(0.8, 300)
    assert sum(P) == pytest.approx(1) and all(P[n] == 0 for n in range(1, 300, 2))
    assert sum(n * p for n, p in enumerate(P)) == pytest.approx(math.sinh(0.8) ** 2)


def test_losses_cap_squeezing():
    assert SQ.with_losses(SQ.r_from_db(30), 0.97).squeezed_db < 15.3
    assert SQ.with_losses(SQ.r_from_db(10), 1.0).squeezed_db == pytest.approx(10)
    assert SQ.with_losses(SQ.r_from_db(15), 1.0, 0.05).squeezed_db < 12


def test_homodyne_statistics():
    xs = SQ.homodyne_samples(0.5, 0.0, 50_000)
    assert sum(x * x for x in xs) / len(xs) == pytest.approx(SQ.variances(0.5)[0], rel=0.03)


def test_interferometer_squeezing():
    r = SQ.r_from_db(6)
    assert SQ.interferometer_noise(100) == pytest.approx(1.0, abs=1e-9)   # vacuum touches the SQL at K=1
    assert SQ.interferometer_noise(1000, r) < SQ.interferometer_noise(1000) / 3.9
    assert SQ.interferometer_noise(10, r) > SQ.interferometer_noise(10) * 3.9
    for f in (10, 30, 100, 300, 1000):
        assert SQ.interferometer_noise(f, r, frequency_dependent=True) == pytest.approx(
            SQ.interferometer_noise(f) * math.exp(-2 * r))
    assert SQ.interferometer_noise(100, r, frequency_dependent=True) < 1   # below the SQL


def test_epr_without_signalling():
    t = SQ.two_mode(1.0, samples=100_000)
    v = math.cosh(2) / 4
    for x in (t.bob_variance_alice_idle, t.bob_variance_alice_measures_x, t.bob_variance_alice_measures_p):
        assert x == pytest.approx(v, rel=0.02)
    assert t.conditional_variance < v / 10
    assert t.epr_product < 1 / 16 and t.duan_sum == pytest.approx(math.exp(-2))
