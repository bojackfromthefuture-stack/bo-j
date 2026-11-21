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
| Past | Negative group velocity (pulse peak exits before it enters) | Measured (Wang et al. 2000), but the signal front still moves at exactly c | `physics.waves.superluminal_pulse` |
| Past | Advanced (backwards-in-time) waves | Allowed by Maxwell's equations; Wheeler-Feynman absorber theory shows they cancel in an absorbing universe | `physics.waves.absorber_theory` |
| Reversal | Time-reversal mirrors | Real (Fink; medical ultrasound). Waves retrace their path, but only as far as nothing was lost | `physics.waves.time_reversal_cavity` |
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

## Waves
* **Three speeds.** The phase velocity can exceed c (in a plasma, v_p v_g = c^2). The group
  velocity can be negative: in the gain-doublet simulation, n_g = -5.5 and the pulse peak
  leaves the cell 2.85 time units early, before the peak has even entered. The *front*
  is what carries information, and it arrives at exactly L/c. The output before that is
  2e-14 of the peak, which is rounding error. Had the front moved at v_g, it would have
  exited before it was switched on.
* **Running waves backwards.** Recording a scattered pulse at two mirrors and playing it
  back in reverse rebuilds it with 0.997 fidelity. With one mirror, strong disorder
  (1-D Anderson localization traps energy), or 1% damping, the refocusing degrades.
  Damping cuts the refocused amplitude to 5%. Wave equations are time-symmetric; loss
  is what makes time one-way.
* **Advanced waves.** On its own, a time-symmetric source radiates half its field *before*
  it acts. Add the absorber response of a universe that absorbs all radiation, and that
  early field cancels to 1e-14. Waves to the past are in the equations, but the
  universe's boundary conditions remove them.
* **Gravitational waves.** GW150914's chirp mass of 28 Msun gives 0.19 s from 35 Hz to
  merger, and that information left 1.3 billion years ago. GW170817 limits
  |v_gw - c|/c to below 4e-16. Every wave we detect is information from the past, never
  information sent to it.

Run `python -m chronopost physics` to see every number above computed.
