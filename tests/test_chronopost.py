import dataclasses

import pytest

from chronopost import future, past


def test_roundtrip():
    cap = future.seal(b"hello, future", t=2000, modulus_bits=512)
    assert future.open_capsule(future.TimeCapsule.from_json(cap.to_json())) == b"hello, future"


def test_ciphertext_hides_message():
    cap = future.seal(b"secret secret secret", t=10, modulus_bits=512)
    assert b"secret" not in cap.to_json().encode()


def test_wrong_t_fails():
    cap = future.seal(b"x", t=100, modulus_bits=512)
    with pytest.raises(ValueError):
        future.open_capsule(dataclasses.replace(cap, t=99))


def test_grandfather_is_paradox_but_deutsch_mixes():
    nov, deu = past.SCENARIOS["grandfather"].run()
    assert nov.consistent == []
    assert deu.distribution == {True: 0.5, False: 0.5}


def test_bootstrap_has_many_histories():
    nov, _ = past.SCENARIOS["bootstrap"].run()
    assert len(nov.consistent) == 3


def test_prophecy_unique():
    nov, _ = past.SCENARIOS["prophecy"].run()
    assert nov.consistent == ["rain"]


def test_noisy_grandfather():
    _, deu = past.SCENARIOS["noisy-grandfather"].run()
    # rho(T) = 0.3 rho(T) + rho(F), rho(T)+rho(F)=1  ->  rho(T) = 1/1.7
    assert deu.distribution[True] == pytest.approx(1 / 1.7, abs=1e-6)


def test_ctc_factoring():
    assert past.ctc_solve(range(2, 2021), lambda d: 2021 % d == 0).consistent == [43, 47]
