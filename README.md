# chronopost

Moving information through time, in both directions, as far as physics allows.

## To the future: real

`chronopost.future` uses **time-lock puzzles** (Rivest, Shamir and Wagner, 1996). A sealed
capsule can only be opened after `t` *sequential* modular squarings. That work can't be
spread across more machines, so `t` sets how far into the future the message arrives.
The sender knows the factors of `n`, so sealing takes no time at all.

```sh
python -m chronopost calibrate                      # squarings/sec on this machine
python -m chronopost seal "hello, future" --seconds 3600 -o capsule.json   # hybrid: RSW + post-quantum hash chain
python -m chronopost open capsule.json              # ~1 hour of work on similar hardware
```

The capsule JSON can be published: it contains no shortcut to the key.
Format v3 offers `--mode rsw|hashchain|hybrid`: `hashchain` and the default `hybrid` resist
quantum computers (Shor breaks RSW, not sequential hashing). It authenticates every field, enforces 2048-bit moduli, pads the message length,
calibrates against GMP-speed attackers (install `gmpy2` to open ~5x faster), and supports
`open --checkpoint` to resume. Read [SECURITY.md](SECURITY.md) for the threat model.

## To the past: simulated

No known physics sends information backwards in time. `chronopost.past` simulates what
such a channel would *have to obey* if closed timelike curves existed:

| Model | Rule | Grandfather paradox |
|---|---|---|
| **Novikov** | only self-consistent histories happen (`respond(m) == m`) | impossible: no history exists |
| **Deutsch (1991)** | the loop settles into a stationary distribution | resolves into a 50/50 mixture |

```sh
python -m chronopost past            # grandfather, bootstrap, prophecy, noisy-grandfather, factoring
```

`ctc_solve` shows time-loop computing: the future self sends back the input unchanged if
it solves the problem, and otherwise sends the next candidate. The only consistent
histories are the ones where the past self already holds the answer.

## Real physics

```sh
python -m chronopost physics    # antitelephone gps rocket wormhole dimensions cycle waves
                                # squeezing twotime sidis
```
Relativistic time dilation, the tachyonic antitelephone, a Morris-Thorne-Yurtsever wormhole
time machine, orbits in n dimensions, Kaluza-Klein towers, closed timelike curves with two
time dimensions, and the matter -> energy -> matter cycle (annihilation and Breit-Wheeler
pair creation, with exact four-momentum conservation), and waves (phase/group/front velocity
with a negative-group-velocity pulse, Fink time-reversal mirrors, Wheeler-Feynman advanced
waves, gravitational-wave chirps, squeezed light and EPR without signalling), two time
dimensions and time loops, and Sidis's entropy reversals tested against modern
thermodynamics. See [ANALYSIS.md](ANALYSIS.md).

## Development

```sh
python -m pytest
```
No required dependencies beyond the Python 3.10+ standard library; `gmpy2` is optional.
