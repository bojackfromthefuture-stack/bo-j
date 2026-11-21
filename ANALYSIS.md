# Information through time: what physics allows

| Direction | Mechanism | Status | Module |
|---|---|---|---|
| Future | Velocity time dilation (twin paradox) | Measured (muons, atomic clocks on aircraft) | `physics.relativity.rocket_trip` |
| Future | Gravitational time dilation | Corrected for daily in GPS (+38.6 us/day) | `physics.relativity.gps_offset` |
| Future | Computational delay (time-lock puzzle) | Works today | `future` |
| Past | Faster-than-light signals | Relativity turns any FTL signal into a message to the past. No FTL signal exists; entanglement can't send one (no-communication theorem) | `physics.relativity.antitelephone` |
| Past | Traversable wormhole time machine | A valid solution of general relativity, but it needs negative-energy exotic matter and may be ruled out by chronology protection | `physics.wormhole` |
| Past | Extra time dimension | Closed timelike curves appear with no exotic matter at all, and predictability goes with them. Observed: exactly 1 time dimension | `physics.dimensions.is_closed_timelike` |
| Past | Antimatter as matter going backwards (Feynman-Stueckelberg) | A real symmetry of QFT (CPT), not a channel | `physics.particles.worldline_reading` |
| Past (logic) | Self-consistency (Novikov) and Deutsch CTCs | The rules any such channel must obey | `past` |

## Dimensions
* **Space:** gravity in `n` spatial dimensions falls off as `1/r^(n-1)`. Circular orbits are
  stable only for `n < 4`. The simulation kicks an orbit by 2%: it stays bound for n=2 and
  n=3, drifts away for n=4, and escapes or collapses for n>=5.
* **Hidden dimensions:** a compact dimension of radius `R` shows up as a Kaluza-Klein
  mass tower `k * hbar c / R`. LHC limits of a few TeV mean `R < ~1e-19 m`.
* **Time:** with two time dimensions, a circle in the time plane is a closed timelike
  curve. That is the geometric core of why 2+ time dimensions break causality.

## Matter -> energy -> matter
`E = mc^2` is a statement about invariant mass. In the cycle e+e- -> gamma gamma -> e+e- ->
gamma gamma, the four-momentum is conserved to rounding error at every step, and
`sqrt(s)` (11.022 MeV in the demo) is carried unchanged. Energy becomes matter only above
threshold, `sqrt(s) >= 2 m_e = 1.022 MeV`. The Breit-Wheeler cross-section peaks at
0.256 sigma_T. This is the "energy -> matter" step first observed directly by STAR in 2021.

The positron in that cycle can be read as the electron running backwards in time. The
mathematics allows that reading, but it carries no signal. Every known route to the past
needs something not yet observed: FTL signals, exotic matter, or a second time dimension.

Run `python -m chronopost physics` to see every number above computed.
