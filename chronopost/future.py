"""Sending information to the future: time-lock puzzles (format v2).

The only physically real way to send a message forward in time so that nobody
can read it early is to make reading it *cost time*. This module implements
the Rivest-Shamir-Wagner (1996) time-lock puzzle:

    x = 2^(2^t) mod n,   n = p*q   (p, q secret, discarded after sealing)

The sealer knows phi(n), so computing x takes one exponentiation. Everyone
else must do t *sequential* modular squarings, which nobody knows how to
parallelise. See SECURITY.md for the threat model and limitations.

Construction (v2)
-----------------
* ``ikm = I2OSP(x, len(n))``: fixed-length encoding of the puzzle solution.
* ``HKDF-SHA256(ikm, salt=nonce, info=label || header)`` gives a 32-byte
  encryption key and a 32-byte MAC key. The header (version, n, t, note,
  sealed_at, padded length) is authenticated, so no field can be changed
  without detection.
* Encryption: HMAC-SHA256 used as a PRF in counter mode.
* Authentication: encrypt-then-MAC with HMAC-SHA256 over header || ciphertext,
  checked in constant time.
* The plaintext is padded (ISO/IEC 7816-4) up to a bucket size, so the
  ciphertext length shows only roughly how long the message is.

Stdlib only. If ``gmpy2`` is installed it is used for squaring (about 5x
faster), both when calibrating and when opening, so the delay is measured
against the fastest arithmetic an ordinary attacker would also use.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import secrets
import time
from dataclasses import dataclass, field

VERSION = 2
LABEL = b"chronopost/timelock/v2"
MIN_MODULUS_BITS = 2048          # below this, factoring n is the shortcut
MAX_T = 1 << 62
MAX_CAPSULE_BYTES = 64 << 20     # refuse absurd inputs when parsing
DEFAULT_PAD = 256

try:  # optional fast arithmetic
    import gmpy2 as _gmp
    _mpz = _gmp.mpz
    BACKEND = "gmpy2"
except ImportError:  # pragma: no cover - depends on environment
    _gmp = None
    _mpz = int
    BACKEND = "python"

# If we must calibrate with pure Python, an attacker with GMP is ~5-6x faster
# (measured: 107k vs 594k squarings/s at 2048 bits). Assume 8x to be safe.
PYTHON_VS_GMP_FACTOR = 8.0


class InsecureParameters(ValueError):
    pass


# ---------------------------------------------------------------- primes ---

_SMALL_PRIMES = [p for p in range(3, 5000) if all(p % d for d in range(2, int(p**0.5) + 1))]


def _is_probable_prime(n: int, rounds: int = 64) -> bool:
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n == p:
            return True
        if n % p == 0:
            return False
    if _gmp is not None:
        return bool(_gmp.is_prime(n, rounds))
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
    """Uniform-ish random prime with its two top bits set (so p*q has exactly 2*bits)."""
    while True:
        c = secrets.randbits(bits) | (0b11 << (bits - 2)) | 1
        if _is_probable_prime(c):
            return c


def _generate_modulus(bits: int) -> tuple[int, int]:
    half = bits // 2
    while True:
        p, q = _random_prime(half), _random_prime(half)
        # Fermat factoring is fast when p and q are close; demand a large gap.
        if abs(p - q).bit_length() > half - 100:
            n = p * q
            if n.bit_length() == bits:
                return n, (p - 1) * (q - 1)


# ------------------------------------------------------------ primitives ---

def _i2osp(x: int, length: int) -> bytes:
    return int(x).to_bytes(length, "big")


def _hkdf(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    out, block, i = b"", b"", 1
    while len(out) < length:
        block = hmac.new(prk, block + info + bytes([i]), hashlib.sha256).digest()
        out += block
        i += 1
    return out[:length]


def _ctr(key: bytes, data: bytes) -> bytes:
    out = bytearray(len(data))
    for blk in range(math.ceil(len(data) / 32)):
        ks = hmac.new(key, blk.to_bytes(8, "big"), hashlib.sha256).digest()
        off = blk * 32
        chunk = data[off:off + 32]
        out[off:off + len(chunk)] = bytes(a ^ b for a, b in zip(chunk, ks))
    return bytes(out)


def _pad(msg: bytes, bucket: int) -> bytes:
    padded = msg + b"\x80"
    return padded + b"\x00" * (-len(padded) % bucket)


def _unpad(data: bytes) -> bytes:
    stripped = data.rstrip(b"\x00")
    if not stripped.endswith(b"\x80"):
        raise ValueError("bad padding")
    return stripped[:-1]


def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _b64d(s: str) -> bytes:
    if not isinstance(s, str):
        raise ValueError("expected base64 string")
    return base64.b64decode(s, validate=True)


# --------------------------------------------------------------- capsule ---

@dataclass(frozen=True)
class TimeCapsule:
    """A sealed message. Safe to publish: it holds no shortcut to the key."""

    n: int
    t: int
    nonce: bytes
    ciphertext: bytes
    tag: bytes
    sealed_at: int
    note: str = ""
    version: int = VERSION

    @property
    def modulus_bytes(self) -> int:
        return (self.n.bit_length() + 7) // 8

    def header(self) -> bytes:
        """Canonical bytes of every public field; covered by the MAC and HKDF."""
        note = self.note.encode()
        return b"".join([
            LABEL,
            self.version.to_bytes(2, "big"),
            self.modulus_bytes.to_bytes(4, "big"), _i2osp(self.n, self.modulus_bytes),
            self.t.to_bytes(8, "big"),
            self.sealed_at.to_bytes(8, "big"),
            len(note).to_bytes(4, "big"), note,
            len(self.ciphertext).to_bytes(8, "big"),
        ])

    def capsule_id(self) -> str:
        return hashlib.sha256(self.header() + self.nonce).hexdigest()[:16]

    def to_json(self) -> str:
        return json.dumps({
            "format": "chronopost-timelock", "version": self.version,
            "n": format(self.n, "x"), "t": self.t,
            "nonce": _b64e(self.nonce), "ciphertext": _b64e(self.ciphertext),
            "tag": _b64e(self.tag), "sealed_at": self.sealed_at, "note": self.note,
        }, indent=2)

    @classmethod
    def from_json(cls, text: str, *, min_bits: int = MIN_MODULUS_BITS) -> "TimeCapsule":
        if len(text) > MAX_CAPSULE_BYTES:
            raise ValueError("capsule too large")
        d = json.loads(text)
        if not isinstance(d, dict) or d.get("format") != "chronopost-timelock":
            raise ValueError("not a chronopost capsule")
        if d.get("version") != VERSION:
            raise ValueError(f"unsupported capsule version {d.get('version')!r}")
        n_hex, t, sealed_at, note = d.get("n"), d.get("t"), d.get("sealed_at"), d.get("note", "")
        if not isinstance(n_hex, str) or not all(c in "0123456789abcdef" for c in n_hex):
            raise ValueError("bad modulus encoding")
        if type(t) is not int or type(sealed_at) is not int or not isinstance(note, str):
            raise ValueError("bad field types")
        cap = cls(n=int(n_hex, 16), t=t, nonce=_b64d(d["nonce"]),
                  ciphertext=_b64d(d["ciphertext"]), tag=_b64d(d["tag"]),
                  sealed_at=sealed_at, note=note)
        cap.validate(min_bits=min_bits)
        return cap

    def validate(self, *, min_bits: int = MIN_MODULUS_BITS) -> None:
        if self.n.bit_length() < min_bits:
            raise InsecureParameters(
                f"modulus is {self.n.bit_length()} bits; below {min_bits} it can be factored "
                "and the puzzle skipped")
        if self.n % 2 == 0:
            raise ValueError("modulus must be odd")
        if not 1 <= self.t <= MAX_T:
            raise ValueError("t out of range")
        if not 0 <= self.sealed_at < 1 << 63:
            raise ValueError("sealed_at out of range")
        if len(self.nonce) != 32 or len(self.tag) != 32:
            raise ValueError("bad nonce/tag length")
        if not self.ciphertext:
            raise ValueError("empty ciphertext")


def _keys(cap: TimeCapsule, x: int) -> tuple[bytes, bytes]:
    okm = _hkdf(_i2osp(x, cap.modulus_bytes), cap.nonce, cap.header(), 64)
    return okm[:32], okm[32:]


# ------------------------------------------------------------ calibrate ---

@dataclass
class Calibration:
    backend: str
    local_rate: float           # squarings/s measured here
    attacker_rate: float        # what we assume the fastest attacker does

    def t_for(self, seconds: float) -> int:
        return max(1, int(seconds * self.attacker_rate))

    def describe(self, t: int) -> str:
        return (f"earliest open by assumed attacker: {_fmt(t / self.attacker_rate)}; "
                f"open time on this machine: {_fmt(t / self.local_rate)}")


def _fmt(s: float) -> str:
    for unit, k in [("years", 31_557_600), ("days", 86400), ("hours", 3600), ("minutes", 60)]:
        if s >= k:
            return f"{s / k:.2f} {unit}"
    return f"{s:.2f} s"


def calibrate(modulus_bits: int = MIN_MODULUS_BITS, *, attacker_speedup: float = 1.0,
              sample: int = 20000) -> Calibration:
    """Measure sequential squaring speed and derive a conservative attacker rate.

    ``attacker_speedup`` covers hardware beyond optimised software on this
    machine (a faster CPU, an FPGA or ASIC). If gmpy2 is missing, the
    measurement is also scaled by PYTHON_VS_GMP_FACTOR.
    """
    n, _ = _generate_modulus(modulus_bits)
    x, N = _mpz(2), _mpz(n)
    start = time.perf_counter()
    for _ in range(sample):
        x = x * x % N
    local = sample / (time.perf_counter() - start)
    sw = 1.0 if BACKEND == "gmpy2" else PYTHON_VS_GMP_FACTOR
    return Calibration(BACKEND, local, local * sw * attacker_speedup)


# ------------------------------------------------------------ seal/open ---

def seal(message: bytes, *, t: int | None = None, seconds: float | None = None,
         modulus_bits: int = MIN_MODULUS_BITS, note: str = "",
         calibration: Calibration | None = None, attacker_speedup: float = 1.0,
         pad_to: int = DEFAULT_PAD, allow_insecure: bool = False) -> TimeCapsule:
    """Seal ``message`` so it can't be read before ``seconds`` of attacker work.

    Give either ``t`` (squarings) directly or ``seconds`` (minimum delay for the
    calibrated attacker). ``note`` and the seal time are stored in the clear but
    authenticated.
    """
    if modulus_bits < MIN_MODULUS_BITS and not allow_insecure:
        raise InsecureParameters(f"modulus_bits must be >= {MIN_MODULUS_BITS}")
    if modulus_bits % 2:
        raise ValueError("modulus_bits must be even")
    if t is None:
        if seconds is None:
            raise ValueError("give t or seconds")
        calibration = calibration or calibrate(modulus_bits, attacker_speedup=attacker_speedup)
        t = calibration.t_for(seconds)
    if not 1 <= t <= MAX_T:
        raise ValueError("t out of range")

    n, phi = _generate_modulus(modulus_bits)
    x = pow(2, pow(2, t, phi), n)     # the sealer's shortcut
    del phi                           # best effort; Python cannot wipe memory

    nonce = secrets.token_bytes(32)
    body = _pad(message, pad_to)
    # The header covers the ciphertext *length*, not its bytes, so a draft with
    # placeholder contents gives the same header and keys.
    draft = TimeCapsule(n=n, t=t, nonce=nonce, ciphertext=b"\0" * len(body),
                        tag=b"\0" * 32, sealed_at=int(time.time()), note=note)
    enc, mac = _keys(draft, x)
    ct = _ctr(enc, body)
    tag = hmac.new(mac, draft.header() + ct, hashlib.sha256).digest()
    return TimeCapsule(n=n, t=t, nonce=nonce, ciphertext=ct, tag=tag,
                       sealed_at=draft.sealed_at, note=note)


@dataclass
class Checkpoint:
    """Resumable progress. It holds no secret: x is only useful once i == t."""
    capsule_id: str
    i: int
    x: int

    def save(self, path: str) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"capsule_id": self.capsule_id, "i": self.i, "x": format(self.x, "x")}, f)
        os.replace(tmp, path)          # atomic: a crash never leaves half a file

    @classmethod
    def load(cls, path: str, cap: TimeCapsule) -> "Checkpoint | None":
        try:
            with open(path) as f:
                d = json.load(f)
        except FileNotFoundError:
            return None
        if d.get("capsule_id") != cap.capsule_id():
            raise ValueError("checkpoint belongs to a different capsule")
        i, x = int(d["i"]), int(d["x"], 16)
        if not 0 <= i <= cap.t or not 0 < x < cap.n:
            raise ValueError("corrupt checkpoint")
        return cls(cap.capsule_id(), i, x)


def solve(cap: TimeCapsule, *, progress=None, checkpoint: str | None = None,
          checkpoint_every: float = 30.0) -> int:
    """Do the t sequential squarings. Resumes from ``checkpoint`` if given.

    A forged checkpoint can only waste the opener's time: a wrong x fails the MAC.
    """
    n, t = _mpz(cap.n), cap.t
    i, x = 0, _mpz(2)
    if checkpoint:
        cp = Checkpoint.load(checkpoint, cap)
        if cp:
            i, x = cp.i, _mpz(cp.x)
    chunk = max(1, min(t // 200 or 1, 200_000))
    last_save = time.monotonic()
    while i < t:
        for _ in range(min(chunk, t - i)):
            x = x * x % n
        i = min(t, i + chunk)
        if progress:
            progress(i / t)
        if checkpoint and time.monotonic() - last_save >= checkpoint_every:
            Checkpoint(cap.capsule_id(), i, int(x)).save(checkpoint)
            last_save = time.monotonic()
    return int(x)


def decrypt(cap: TimeCapsule, x: int) -> bytes:
    enc, mac = _keys(cap, x)
    expected = hmac.new(mac, cap.header() + cap.ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, cap.tag):
        raise ValueError("authentication failed: capsule corrupt, tampered with, or wrong solution")
    return _unpad(_ctr(enc, cap.ciphertext))


def open_capsule(cap: TimeCapsule, progress=None, checkpoint: str | None = None) -> bytes:
    """Do the work and decrypt. There is no shortcut without the factors of n.

    Modulus size is enforced when parsing (``TimeCapsule.from_json``); here
    only the structure is checked, so test capsules with small n still open.
    """
    cap.validate(min_bits=0)
    return decrypt(cap, solve(cap, progress=progress, checkpoint=checkpoint))
