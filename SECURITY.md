# Security of time-lock capsules (`chronopost.future`)

## What it promises
Nobody can read a capsule without doing `t` modular squarings **one after another**, unless
they can factor the 2048-bit modulus `n`. The delay is set by the fastest *sequential*
squaring speed an attacker has. Extra computers don't help: no one knows how to
parallelise repeated squaring.

## Changes in format v2 (from the v1 review)

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
* **Quantum computers.** Shor's algorithm factors `n` and breaks the time lock.
* Not audited. The primitives are standard (HKDF, HMAC-SHA256, Miller-Rabin or GMP
  `is_prime`), but treat this as a carefully built research tool.
