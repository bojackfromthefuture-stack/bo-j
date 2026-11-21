"""Sending information to the future: time-lock capsules (format v3).

The only physically real way to send a message forward in time so that nobody
can read it early is to make reading it *cost time*. Three modes:

``rsw`` (Rivest-Shamir-Wagner 1996)
    x = 2^(2^t) mod n with n = p*q. The sealer knows phi(n), so sealing is
    instant; everyone else does t *sequential* squarings. **Not quantum-safe**:
    Shor's algorithm factors n and skips the work.

``hashchain`` (post-quantum)
    The opener walks a chain of k*m sequential SHA-256 evaluations. Grover's
    algorithm does not shorten a *sequential* chain, and hash chains have
    proofs of post-quantum sequentiality in the quantum random-oracle model
    (Chung-Fehr-Huang-Liao 2021; Blocki-Lee-Zhou 2021). The price: there is no
    trapdoor, so the sealer must do the same total work, but can split it over
    k parallel links (Mahmoody-Moran-Vadhan 2011 show you cannot do better from
    hashing alone). Link i's endpoint decrypts link i+1's start, which forces
    the opener to go through the links in order.

``hybrid`` (default)
    Both locks, keys combined. A classical attacker must break both; a quantum
    attacker who factors n still faces the full hash chain.

Construction
------------
* ikm = I2OSP(x, len(n)) || chain_end  (each part present if its mode is used)
* HKDF-SHA256(ikm, salt=nonce, info=header) -> encryption key || MAC key.
  The header covers every public field, so nothing can be altered undetected.
* HMAC-SHA256 counter-mode keystream; encrypt-then-MAC; ISO 7816-4 padding.
* 256-bit symmetric keys: Grover leaves 128-bit security, which is ample.

Nothing here is *unbreakable*: a time-lock is only ever a lower bound on
work. An attacker with unlimited time, or faster sequential hardware, opens it
sooner. See SECURITY.md.
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
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

VERSION = 3
LABEL = b"chronopost/timelock/v3"
MODES = ("rsw", "hashchain", "hybrid")
MIN_MODULUS_BITS = 2048          # below this, factoring n is the shortcut
MAX_T = 1 << 62
MAX_LINKS = 1 << 16
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

# Pure Python vs GMP squaring: measured 107k vs 594k/s at 2048 bits; assume 8x.
PYTHON_VS_GMP_FACTOR = 8.0
# Python's hashlib loop (~2.6M SHA-256/s here, dominated by call overhead) vs a
# tight SHA-NI loop in C (~15-20M/s). Assume 8x. ASICs: use attacker_speedup.
PYTHON_VS_NATIVE_HASH_FACTOR = 8.0


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
    """Random prime with its two top bits set (so p*q has exactly 2*bits)."""
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


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


# ------------------------------------------------------------ hash chain ---

def _chain(start: bytes, steps: int) -> bytes:
    """steps sequential SHA-256 evaluations. Each depends on the last."""
    h = hashlib.sha256
    x = start
    for _ in range(steps):
        x = h(x).digest()
    return x


def _link_pad(end: bytes) -> bytes:
    return hashlib.sha256(b"chronopost/link" + end).digest()


# --------------------------------------------------------------- capsule ---

@dataclass(frozen=True)
class TimeCapsule:
    """A sealed message. Safe to publish: it holds no shortcut to the key."""

    mode: str
    nonce: bytes
    ciphertext: bytes
    tag: bytes
    sealed_at: int
    note: str = ""
    n: int = 0                        # rsw: modulus
    t: int = 0                        # rsw: squarings
    chain_steps: int = 0              # hashchain: hashes per link (m)
    chain_seed: bytes = b""           # hashchain: start of link 0
    chain_links: tuple = ()           # hashchain: encrypted starts of links 1..k-1
    version: int = VERSION

    @property
    def uses_rsw(self) -> bool:
        return self.mode in ("rsw", "hybrid")

    @property
    def uses_chain(self) -> bool:
        return self.mode in ("hashchain", "hybrid")

    @property
    def modulus_bytes(self) -> int:
        return (self.n.bit_length() + 7) // 8

    @property
    def chain_total(self) -> int:
        return self.chain_steps * (len(self.chain_links) + 1) if self.uses_chain else 0

    def header(self) -> bytes:
        """Canonical bytes of every public field; covered by HKDF and the MAC."""
        note = self.note.encode()
        parts = [LABEL, self.version.to_bytes(2, "big"),
                 len(self.mode).to_bytes(1, "big"), self.mode.encode()]
        if self.uses_rsw:
            parts += [self.modulus_bytes.to_bytes(4, "big"), _i2osp(self.n, self.modulus_bytes),
                      self.t.to_bytes(8, "big")]
        if self.uses_chain:
            parts += [self.chain_steps.to_bytes(8, "big"),
                      len(self.chain_links).to_bytes(4, "big"), self.chain_seed, *self.chain_links]
        parts += [self.sealed_at.to_bytes(8, "big"), len(note).to_bytes(4, "big"), note,
                  len(self.ciphertext).to_bytes(8, "big")]
        return b"".join(parts)

    def capsule_id(self) -> str:
        return hashlib.sha256(self.header() + self.nonce).hexdigest()[:16]

    def to_json(self) -> str:
        d = {"format": "chronopost-timelock", "version": self.version, "mode": self.mode,
             "nonce": _b64e(self.nonce), "ciphertext": _b64e(self.ciphertext),
             "tag": _b64e(self.tag), "sealed_at": self.sealed_at, "note": self.note}
        if self.uses_rsw:
            d.update(n=format(self.n, "x"), t=self.t)
        if self.uses_chain:
            d.update(chain_steps=self.chain_steps, chain_seed=_b64e(self.chain_seed),
                     chain_links=[_b64e(c) for c in self.chain_links])
        return json.dumps(d, indent=2)

    @classmethod
    def from_json(cls, text: str, *, min_bits: int = MIN_MODULUS_BITS) -> "TimeCapsule":
        if len(text) > MAX_CAPSULE_BYTES:
            raise ValueError("capsule too large")
        d = json.loads(text)
        if not isinstance(d, dict) or d.get("format") != "chronopost-timelock":
            raise ValueError("not a chronopost capsule")
        if d.get("version") != VERSION:
            raise ValueError(f"unsupported capsule version {d.get('version')!r}")
        mode = d.get("mode")
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}")
        sealed_at, note = d.get("sealed_at"), d.get("note", "")
        if type(sealed_at) is not int or not isinstance(note, str):
            raise ValueError("bad field types")
        kw = {}
        if mode in ("rsw", "hybrid"):
            n_hex, t = d.get("n"), d.get("t")
            if not isinstance(n_hex, str) or not n_hex or not all(c in "0123456789abcdef" for c in n_hex):
                raise ValueError("bad modulus encoding")
            if type(t) is not int:
                raise ValueError("bad field types")
            kw.update(n=int(n_hex, 16), t=t)
        if mode in ("hashchain", "hybrid"):
            m, links = d.get("chain_steps"), d.get("chain_links")
            if type(m) is not int or not isinstance(links, list):
                raise ValueError("bad field types")
            kw.update(chain_steps=m, chain_seed=_b64d(d.get("chain_seed")),
                      chain_links=tuple(_b64d(c) for c in links))
        cap = cls(mode=mode, nonce=_b64d(d["nonce"]), ciphertext=_b64d(d["ciphertext"]),
                  tag=_b64d(d["tag"]), sealed_at=sealed_at, note=note, **kw)
        cap.validate(min_bits=min_bits)
        return cap

    def validate(self, *, min_bits: int = MIN_MODULUS_BITS) -> None:
        if self.mode not in MODES:
            raise ValueError("unknown mode")
        if self.uses_rsw:
            if self.n.bit_length() < min_bits:
                raise InsecureParameters(
                    f"modulus is {self.n.bit_length()} bits; below {min_bits} it can be factored "
                    "and the puzzle skipped")
            if self.n % 2 == 0 or self.n < 3:
                raise ValueError("modulus must be odd")
            if not 1 <= self.t <= MAX_T:
                raise ValueError("t out of range")
        if self.uses_chain:
            if not 1 <= self.chain_steps <= MAX_T:
                raise ValueError("chain_steps out of range")
            if len(self.chain_links) >= MAX_LINKS:
                raise ValueError("too many links")
            if len(self.chain_seed) != 32 or any(len(c) != 32 for c in self.chain_links):
                raise ValueError("bad chain encoding")
        if not 0 <= self.sealed_at < 1 << 63:
            raise ValueError("sealed_at out of range")
        if len(self.nonce) != 32 or len(self.tag) != 32:
            raise ValueError("bad nonce/tag length")
        if not self.ciphertext:
            raise ValueError("empty ciphertext")


def _keys(cap: TimeCapsule, x: int | None, chain_end: bytes | None) -> tuple[bytes, bytes]:
    ikm = b""
    if cap.uses_rsw:
        ikm += _i2osp(x, cap.modulus_bytes)
    if cap.uses_chain:
        ikm += chain_end
    okm = _hkdf(ikm, cap.nonce, cap.header(), 64)
    return okm[:32], okm[32:]


# ------------------------------------------------------------ calibrate ---

@dataclass
class Calibration:
    backend: str
    local_rate: float           # squarings/s measured here
    attacker_rate: float        # squarings/s assumed for the fastest attacker
    hash_local_rate: float      # sequential SHA-256/s measured here (one core)
    hash_attacker_rate: float
    cores: int

    def t_for(self, seconds: float) -> int:
        return max(1, int(seconds * self.attacker_rate))

    def hashes_for(self, seconds: float) -> int:
        return max(1, int(seconds * self.hash_attacker_rate))

    def seal_seconds(self, total_hashes: int) -> float:
        """Wall time for the sealer to build a chain of this total length on all cores."""
        return total_hashes / (self.hash_local_rate * self.cores)

    def describe(self, cap: TimeCapsule) -> str:
        parts = []
        if cap.uses_rsw:
            parts.append(f"RSW: attacker >= {_fmt(cap.t / self.attacker_rate)}, "
                         f"here {_fmt(cap.t / self.local_rate)}")
        if cap.uses_chain:
            parts.append(f"hash chain: attacker >= {_fmt(cap.chain_total / self.hash_attacker_rate)}, "
                         f"here {_fmt(cap.chain_total / self.hash_local_rate)}")
        if cap.mode == "rsw":
            parts.append("quantum attacker: ~instant (Shor)")
        else:
            parts.append(f"quantum attacker >= {_fmt(cap.chain_total / self.hash_attacker_rate)}")
        return "; ".join(parts)


def _fmt(s: float) -> str:
    for unit, k in [("years", 31_557_600), ("days", 86400), ("hours", 3600), ("minutes", 60)]:
        if s >= k:
            return f"{s / k:.2f} {unit}"
    return f"{s:.2f} s"


def calibrate(modulus_bits: int = MIN_MODULUS_BITS, *, attacker_speedup: float = 1.0,
              sample: int = 20000, hash_sample: int = 200_000) -> Calibration:
    """Measure sequential squaring and hashing speed; derive conservative attacker rates.

    ``attacker_speedup`` covers hardware beyond optimised software on this
    machine (a faster CPU, FPGA or ASIC).
    """
    n, _ = _generate_modulus(modulus_bits)
    x, N = _mpz(2), _mpz(n)
    start = time.perf_counter()
    for _ in range(sample):
        x = x * x % N
    local = sample / (time.perf_counter() - start)
    sw = 1.0 if BACKEND == "gmpy2" else PYTHON_VS_GMP_FACTOR

    start = time.perf_counter()
    _chain(b"\0" * 32, hash_sample)
    h_local = hash_sample / (time.perf_counter() - start)
    return Calibration(BACKEND, local, local * sw * attacker_speedup,
                       h_local, h_local * PYTHON_VS_NATIVE_HASH_FACTOR * attacker_speedup,
                       os.cpu_count() or 1)


# ------------------------------------------------------------------ seal ---

def _build_chain(total: int, links: int, workers: int | None) -> tuple[int, bytes, tuple, bytes]:
    links = max(1, min(links, total, MAX_LINKS - 1))
    m = math.ceil(total / links)
    seeds = [secrets.token_bytes(32) for _ in range(links)]
    if links > 1 and (workers or 0) != 1 and m * links > 200_000:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            ends = list(pool.map(_chain, seeds, [m] * links))
    else:
        ends = [_chain(s, m) for s in seeds]
    enc_links = tuple(_xor(seeds[i + 1], _link_pad(ends[i])) for i in range(links - 1))
    return m, seeds[0], enc_links, ends[-1]


def seal(message: bytes, *, mode: str = "hybrid", t: int | None = None,
         chain_hashes: int | None = None, seconds: float | None = None,
         modulus_bits: int = MIN_MODULUS_BITS, note: str = "",
         calibration: Calibration | None = None, attacker_speedup: float = 1.0,
         links: int | None = None, workers: int | None = None,
         pad_to: int = DEFAULT_PAD, allow_insecure: bool = False) -> TimeCapsule:
    """Seal ``message``.

    Either give the work directly (``t`` squarings and/or ``chain_hashes``
    total hashes, depending on mode) or ``seconds``: the minimum delay for the
    calibrated attacker. In hybrid mode each lock gets the full delay, since an
    opener can run both at once. Hash-chain sealing costs the sealer the same
    total work, spread over ``links`` parallel pieces (default 4 per core).
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    use_rsw, use_chain = mode in ("rsw", "hybrid"), mode in ("hashchain", "hybrid")
    if use_rsw:
        if modulus_bits < MIN_MODULUS_BITS and not allow_insecure:
            raise InsecureParameters(f"modulus_bits must be >= {MIN_MODULUS_BITS}")
        if modulus_bits % 2:
            raise ValueError("modulus_bits must be even")
    if seconds is not None:
        calibration = calibration or calibrate(modulus_bits, attacker_speedup=attacker_speedup)
        t = t or calibration.t_for(seconds)
        chain_hashes = chain_hashes or calibration.hashes_for(seconds)
    if use_rsw and not (t and 1 <= t <= MAX_T):
        raise ValueError("give t or seconds")
    if use_chain and not (chain_hashes and 1 <= chain_hashes <= MAX_T):
        raise ValueError("give chain_hashes or seconds")

    kw = {}
    x = chain_end = None
    if use_rsw:
        n, phi = _generate_modulus(modulus_bits)
        x = pow(2, pow(2, t, phi), n)     # the sealer's shortcut
        del phi                           # best effort; Python cannot wipe memory
        kw.update(n=n, t=t)
    if use_chain:
        k = links or 4 * (os.cpu_count() or 1)
        m, seed, enc_links, chain_end = _build_chain(chain_hashes, k, workers)
        kw.update(chain_steps=m, chain_seed=seed, chain_links=enc_links)

    nonce = secrets.token_bytes(32)
    body = _pad(message, pad_to)
    # The header covers the ciphertext *length*, not its bytes, so a draft with
    # placeholder contents gives the same header and keys.
    draft = TimeCapsule(mode=mode, nonce=nonce, ciphertext=b"\0" * len(body), tag=b"\0" * 32,
                        sealed_at=int(time.time()), note=note, **kw)
    enc, mac = _keys(draft, x, chain_end)
    ct = _ctr(enc, body)
    tag = hmac.new(mac, draft.header() + ct, hashlib.sha256).digest()
    return TimeCapsule(mode=mode, nonce=nonce, ciphertext=ct, tag=tag,
                       sealed_at=draft.sealed_at, note=note, **kw)


# ------------------------------------------------------------------ open ---

class Checkpoint:
    """Resumable progress, bound to one capsule. It holds no secret: partial
    results are useless until the work is complete, and a forged checkpoint can
    only waste the opener's time (a wrong result fails the MAC)."""

    def __init__(self, path: str | None, cap: TimeCapsule):
        self.path, self.cap = path, cap
        self.state: dict = {}
        if path and os.path.exists(path):
            with open(path) as f:
                d = json.load(f)
            if d.get("capsule_id") != cap.capsule_id():
                raise ValueError("checkpoint belongs to a different capsule")
            self.state = d

    def save(self) -> None:
        if not self.path:
            return
        self.state["capsule_id"] = self.cap.capsule_id()
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.state, f)
        os.replace(tmp, self.path)       # atomic: a crash never leaves half a file

    def rsw(self) -> tuple[int, int]:
        s = self.state.get("rsw")
        if not s:
            return 0, 2
        i, x = int(s["i"]), int(s["x"], 16)
        if not 0 <= i <= self.cap.t or not 0 < x < self.cap.n:
            raise ValueError("corrupt checkpoint")
        return i, x

    def chain(self) -> tuple[int, int, bytes]:
        s = self.state.get("chain")
        if not s:
            return 0, 0, self.cap.chain_seed
        link, j, v = int(s["link"]), int(s["j"]), bytes.fromhex(s["v"])
        if not (0 <= link <= len(self.cap.chain_links) and 0 <= j <= self.cap.chain_steps
                and len(v) == 32):
            raise ValueError("corrupt checkpoint")
        return link, j, v


def solve_rsw(cap: TimeCapsule, progress=None, cp: Checkpoint | None = None,
              every: float = 30.0) -> int:
    cp = cp or Checkpoint(None, cap)
    i, x = cp.rsw()
    n, t, x = _mpz(cap.n), cap.t, _mpz(x)
    chunk = max(1, min(t // 200 or 1, 200_000))
    last = time.monotonic()
    while i < t:
        for _ in range(min(chunk, t - i)):
            x = x * x % n
        i = min(t, i + chunk)
        if progress:
            progress("rsw", i / t)
        if time.monotonic() - last >= every:
            cp.state["rsw"] = {"i": i, "x": format(int(x), "x")}
            cp.save()
            last = time.monotonic()
    cp.state["rsw"] = {"i": t, "x": format(int(x), "x")}
    cp.save()
    return int(x)


def solve_chain(cap: TimeCapsule, progress=None, cp: Checkpoint | None = None,
                every: float = 30.0) -> bytes:
    cp = cp or Checkpoint(None, cap)
    link, j, v = cp.chain()
    m, k = cap.chain_steps, len(cap.chain_links) + 1
    chunk = max(1, min(m, 200_000))
    last = time.monotonic()
    while True:
        while j < m:
            step = min(chunk, m - j)
            v = _chain(v, step)
            j += step
            if progress:
                progress("hashchain", (link * m + j) / (k * m))
            if time.monotonic() - last >= every:
                cp.state["chain"] = {"link": link, "j": j, "v": v.hex()}
                cp.save()
                last = time.monotonic()
        if link == k - 1:
            return v
        v = _xor(cap.chain_links[link], _link_pad(v))   # unlock the next link's start
        link, j = link + 1, 0


def decrypt(cap: TimeCapsule, x: int | None, chain_end: bytes | None) -> bytes:
    enc, mac = _keys(cap, x, chain_end)
    expected = hmac.new(mac, cap.header() + cap.ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, cap.tag):
        raise ValueError("authentication failed: capsule corrupt, tampered with, or wrong solution")
    return _unpad(_ctr(enc, cap.ciphertext))


def open_capsule(cap: TimeCapsule, progress=None, checkpoint: str | None = None,
                 parallel: bool = False) -> bytes:
    """Do the work and decrypt.

    ``parallel`` runs the hash chain in a second process while this one does
    the RSW squarings (hybrid mode), so the wait is the longer of the two
    rather than their sum. Checkpointing then covers the RSW part only.
    Modulus size is enforced when parsing (``TimeCapsule.from_json``).
    """
    cap.validate(min_bits=0)
    cp = Checkpoint(checkpoint, cap)
    x = chain_end = None
    if parallel and cap.uses_rsw and cap.uses_chain:
        with ProcessPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(solve_chain, cap)
            x = solve_rsw(cap, progress, cp)
            chain_end = fut.result()
    else:
        if cap.uses_rsw:
            x = solve_rsw(cap, progress, cp)
        if cap.uses_chain:
            chain_end = solve_chain(cap, progress, cp)
    return decrypt(cap, x, chain_end)
