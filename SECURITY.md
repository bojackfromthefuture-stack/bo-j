# Security of time-lock capsules (`chronopost.future`)

## What it promises
Nobody can read a capsule without doing a fixed amount of **sequential** work. The
delay is set by the attacker's fastest *sequential* speed. Extra computers don't help.

## Can it be quantum-unbreakable? (format v3)
**Unbreakable: no.** No time-lock can be. A time-lock is a lower bound on work, not
information-theoretic secrecy: the ciphertext fixes the message, so enough time always
opens it. It can be made **quantum-resistant**:

| Mode | Lock | Classical attacker | Quantum attacker | Sealing cost |
|---|---|---|---|---|
| `rsw` | t squarings mod n | t sequential squarings | **Shor factors n: ~instant** | instant (trapdoor) |
| `hashchain` | k links x m SHA-256 | k*m sequential hashes | k*m sequential hashes | k*m hashes, spread over cores |
| `hybrid` (default) | both | must break both | still faces the full hash chain | both |

* **Why hash chains survive quantum computers.** Grover's algorithm speeds up *searching*
  for preimages. It doesn't speed up computing H(H(H(...))) in order. Post-quantum
  proofs of sequential work exist in the quantum random-oracle model (Chung, Fehr,
  Huang & Liao 2021; Blocki, Lee & Zhou 2021). A quantum computer also evaluates
  SHA-256 far slower than a classical chip.
* **The symmetric layer** (HKDF, HMAC-SHA256, 256-bit keys) keeps about 128-bit security
  against Grover.
* **The price of having no trapdoor.** The sealer does the same total work as the opener,
  split across `links` parallel pieces. Mahmoody, Moran & Vadhan (2011) proved that hash
  functions alone can't do better. Measured here: 3.7M SHA-256/s per core, with an
  assumed 8x faster native attacker (`PYTHON_VS_NATIVE_HASH_FACTOR`). A 1-hour lock
  therefore takes about 2 hours to seal on 4 cores and about 8 hours to open in Python.
  An opener with a native SHA-NI loop opens in about 1 hour.
* **Link chaining.** Link i+1's start is XOR-encrypted under H(label || end of link i),
  so the links can only be walked in order. All the chain fields are in the
  authenticated header.
* **Hybrid opening** can run both locks at once (`open --parallel`), so the wait is the
  longer of the two, not their sum.
* **Not done:** lattice-based time-lock puzzles (post-quantum *with* a trapdoor) are still
  research-stage; quantum "timed-release" schemes (Unruh 2014) need quantum memory.

## Changes in format v2 (from the v1 review; v3 adds the modes above)

| v1 weakness | v2 fix |
|---|---|
| Delay calibrated with pure-Python integers; GMP is ~5.5x faster (measured 107k vs 594k squarings/s at 2048 bits), so a "1 hour" capsule opened in ~11 min | Calibrate with gmpy2 when present; otherwise scale the attacker rate by 8x. `--attacker-speedup` adds headroom for faster hardware |
| Any modulus size accepted; 512-bit `n` can be factored and the puzzle skipped | `n` must be >= 2048 bits at seal and parse time (`--allow-insecure` for tests only) |
| `note`, `t` and `sealed_at` were not authenticated | Every public field is in a canonical header, bound into the HKDF key derivation and the MAC |
| Ad-hoc `SHA-256(secret||ctr)` keys and keystream | HKDF-SHA256 key derivation, HMAC-SHA256 used as a PRF in counter mode, encrypt-then-MAC |
| Variable-length encoding of the puzzle solution | Fixed-length I2OSP encoding to `len(n)` bytes |
| Ciphertext length = message length | ISO 7816-4 padding up to a 256-byte bucket (`--pad`) |
| Loose JSON parsing | Strict types, version and format check, strict base64, size limits |
| p and q could be close (Fermat factoring) | Top two bits set, exact bit length, and a gap of >= half-100 bits required |
| A crash lost all opening progress | Atomic, capsule-bound checkpoints (`open --checkpoint`) |

## Threat model and limits (read these)
* **The delay is relative to hardware.** Specialist hardware such as VDF ASICs could
  square several times faster than GMP on a desktop. For long delays, seal with
  `--attacker-speedup 10` or more. The honest opener then also takes longer: that cost
  can't be avoided.
* **The delay is not wall-clock time.** Nothing stops someone starting the work the day
  after you publish. For "not before date D" guarantees, use threshold-network
  time-lock encryption (drand/tlock). It replaces the computation with trust in a network.
* **The sealer is trusted.** They can make a capsule that never opens, and the opener
  only finds out after doing the work. No zero-knowledge proof of a well-formed puzzle
  is included.
* **Sealing memory.** Python can't wipe `p`, `q` and `phi` from memory. Seal on a machine
  you trust.
* **Quantum computers.** Shor's algorithm breaks `rsw` mode. Use `hashchain` or `hybrid`
  (the default) against a future quantum attacker.
* Not audited. The primitives are standard (HKDF, HMAC-SHA256, Miller-Rabin or GMP
  `is_prime`), but treat this as a carefully built research tool.
