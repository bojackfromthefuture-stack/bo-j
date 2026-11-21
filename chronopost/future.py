"""Sending information to the future.

The only *physically real* way to send a message forward in time so that nobody
can read it early is to make reading it cost time. This module implements the
Rivest-Shamir-Wagner (1996) time-lock puzzle:

    key = 2^(2^t) mod n,   n = p*q

The sender knows phi(n), so they compute the key instantly via
2^(2^t mod phi(n)) mod n. Anyone else must perform t *sequential* modular
squarings - work that cannot be parallelised. Choosing t fixes how far into
the future the message "arrives".

Stdlib only; the cipher is a SHA-256 counter-mode keystream with an HMAC tag.
It is meant for learning and experiments, not for protecting real secrets.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, asdict

# ---------------------------------------------------------------- primes ---

_SMALL_PRIMES = [p for p in range(3, 2000) if all(p % d for d in range(2, int(p**0.5) + 1))]


def _is_probable_prime(n: int, rounds: int = 40) -> bool:
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n == p:
            return True
        if n % p == 0:
            return False
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _random_prime(bits: int) -> int:
    while True:
        c = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if _is_probable_prime(c):
            return c


# ---------------------------------------------------------------- cipher ---

def _keystream(key: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(key + counter.to_bytes(8, "big")).digest()
        counter += 1
    return bytes(out[:length])


def _derive(secret_int: int, nonce: bytes) -> tuple[bytes, bytes]:
    raw = secret_int.to_bytes((secret_int.bit_length() + 7) // 8 or 1, "big")
    enc = hashlib.sha256(b"enc" + nonce + raw).digest()
    mac = hashlib.sha256(b"mac" + nonce + raw).digest()
    return enc, mac


# --------------------------------------------------------------- capsule ---

@dataclass
class TimeCapsule:
    """A sealed message. Safe to publish: it holds no shortcut to the key."""

    n: int
    t: int
    nonce: str
    ciphertext: str
    tag: str
    sealed_at: float
    note: str = ""

    def to_json(self) -> str:
        d = asdict(self)
        d["n"] = str(self.n)  # big ints as strings for portability
        return json.dumps(d, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "TimeCapsule":
        d = json.loads(text)
        d["n"] = int(d["n"])
        return cls(**d)


def calibrate(modulus_bits: int = 2048, sample: int = 20000) -> float:
    """Measure sequential squarings per second on this machine."""
    n = _random_prime(modulus_bits // 2) * _random_prime(modulus_bits // 2)
    x = 2
    start = time.perf_counter()
    for _ in range(sample):
        x = x * x % n
    return sample / (time.perf_counter() - start)


def seal(message: bytes, *, t: int | None = None, seconds: float | None = None,
         modulus_bits: int = 2048, note: str = "",
         rate: float | None = None) -> TimeCapsule:
    """Seal ``message`` so that opening it needs ``t`` sequential squarings.

    Give either ``t`` directly or ``seconds`` (converted with a measured or
    supplied squarings-per-second ``rate``). Sealing itself is instant.
    """
    if t is None:
        if seconds is None:
            raise ValueError("give t or seconds")
        rate = rate or calibrate(modulus_bits)
        t = max(1, int(seconds * rate))
    p, q = _random_prime(modulus_bits // 2), _random_prime(modulus_bits // 2)
    n, phi = p * q, (p - 1) * (q - 1)
    key_int = pow(2, pow(2, t, phi), n)  # the sender's shortcut

    nonce = secrets.token_bytes(16)
    enc, mac = _derive(key_int, nonce)
    ct = bytes(a ^ b for a, b in zip(message, _keystream(enc, len(message))))
    tag = hmac.new(mac, nonce + ct, hashlib.sha256).digest()
    b64 = lambda b: base64.b64encode(b).decode()
    return TimeCapsule(n=n, t=t, nonce=b64(nonce), ciphertext=b64(ct),
                       tag=b64(tag), sealed_at=time.time(), note=note)


def open_capsule(capsule: TimeCapsule, progress=None) -> bytes:
    """Do the t sequential squarings and decrypt. There is no shortcut."""
    x, n, t = 2, capsule.n, capsule.t
    step = max(1, t // 100)
    for i in range(t):
        x = x * x % n
        if progress and i % step == 0:
            progress(i / t)
    if progress:
        progress(1.0)

    nonce = base64.b64decode(capsule.nonce)
    ct = base64.b64decode(capsule.ciphertext)
    enc, mac = _derive(x, nonce)
    expected = hmac.new(mac, nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, base64.b64decode(capsule.tag)):
        raise ValueError("capsule is corrupt or was tampered with")
    return bytes(a ^ b for a, b in zip(ct, _keystream(enc, len(ct))))
