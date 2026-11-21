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
| Past | Two time dimensions | A time circle is a CTC. Free data is unpredictable (Hadamard); data obeying a nonlocal constraint evolves deterministically (Craig-Weinstein 2009); Bars's gauge symmetry reduces it to 1-time physics | `physics.twotime` |
| Reversal | Entropy decreases (Sidis) | Real but exponentially rare (fluctuation theorem); a reversed arrow follows from a *future* low-entropy boundary (Schulman 1999) | `physics.entropy` |
| Past (logic) | Self-consistency (Novikov) and Deutsch CTCs | The rules any such channel must obey | `past` |

## Dimensions
* **Space:** gravity in `n` spatial dimensions falls off as `1/r^(n-1)`. Circular orbits are
  stable only for `n < 4`. The simulation kicks an orbit by 2%: it stays bound for n=2 and
  n=3, drifts away for n=4, and escapes or collapses for n>=5.
* **Hidden dimensions:** a compact dimension of radius `R` shows up as a Kaluza-Klein
  mass tower `k * hbar c / R`. LHC limits of a few TeV mean `R < ~1e-19 m`.
* **Time:** with two time dimensions, a circle in the time plane is a closed timelike
  curve. See the next section for whether that really breaks cause and effect.

## Two time dimensions: does cause and effect break? Does it loop?
1. **No past or future.** With one time dimension, the timelike directions form 2 separate
   pieces, future and past. With two, they form 1 piece. That's computed by sampling the
   hyperboloid and counting connected clusters. Rotating in the (t1, t2) plane turns
   "forward" into "backward" continuously, so no observer-independent arrow exists.
2. **Predictability.** For waves with two times, random data at t1 = 0 is amplified
   x7, x200, x4e5 and x2e12 at finer and finer resolution. The future doesn't depend
   continuously on the present (Hadamard ill-posedness). Restrict the data with the
   Craig-Weinstein nonlocal constraint and the amplification stays below 1: evolution
   is deterministic again. **So causality can survive, but causes stop being free and
   local:** what happens here must be correlated with what happens elsewhere in t2.
3. **If it loops.** On a time circle, only self-reproducing histories exist.
   * Linear systems: an oscillator exists only if omega*T = 2*pi*n, so energy is quantised
     (E_n = n h / T). A damped system admits only "nothing happens".
   * Continuous systems: Brouwer's theorem guarantees a consistent history. The
     billiard-ball paradox resolves with a glancing blow (x = 0.5). Some loops have
     several solutions, and physics doesn't choose between them. Only all-or-nothing
     rules, like the yes/no grandfather, have none. This links the physics to
     `chronopost.past`'s Novikov and Deutsch models.
4. **Two-time physics (Bars).** With signature (d, 2) plus an Sp(2,R) gauge symmetry,
   the extra time is gauge. Ordinary physics appears as its "shadows", and causality
   is kept.

Verdict: two times do not *necessarily* break cause and effect. They break *free local*
cause and effect. Loops impose self-consistency, which quantises what can exist.

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

## Squeezed light
A squeezed state pushes the noise of one light quadrature below the vacuum level
(10 dB: variance 0.025 vs 0.25), and the other quadrature pays (2.5). The product
stays at the Heisenberg minimum of 1/16, and photons come only in pairs. Loss is the
enemy: however much squeezing is generated, efficiency 0.97 caps what you can measure
at about 15 dB (the world record), and 0.70 caps it at about 5 dB. In a
gravitational-wave detector, 6 dB of fixed-angle squeezing cuts high-frequency noise
4x but adds 4x at low frequency. Frequency-dependent squeezing (LIGO since 2023)
cuts both and dips below the standard quantum limit (0.25 x SQL at 100 Hz).
Two-mode squeezing gives EPR entanglement: Duan sum 0.135 < 1, Reid product
0.0044 < 1/16. Yet Bob's variance is 0.94 whether Alice does nothing or measures
X or P. Squeezing sharpens what can be known, but it is no channel to the past or
faster than light.

## Sidis: *The Animate and the Inanimate* (1925), reversals and entropy
| Sidis's claim | Verdict | Evidence here |
|---|---|---|
| A. Reversible laws make the second law statistical | **Right** (Boltzmann, Loschmidt) | Kac ring: entropy 0 -> 0.692 -> exactly 0 on reversal; 1% error spoils it; exact recurrence at 2000 steps |
| B. Regions where the second law runs backwards exist | **Partly**: real, but P ~ e^{-dS/k} | Fluctuation theorem exact to 1e-14; P(decrease) 0.17 -> 7e-11 from 10 to 1000 steps; Schulman's two-boundary urn rises then *falls* |
| C. Life is such a reversal | **No**: life exports entropy | A demon needs 110 bits of memory to lower the gas entropy by 57 bits; Earth exports 6e14 W/K |
| D. Reversed regions look dark and absorb light | **Inverted**: black holes absorb, but hold *maximum* entropy | 1 Msun hole: 1e77 k, versus about 3e58 k for the Sun |
| E. No heat death, endless alternation | **Open** | Past hypothesis; recurrence times ~e^(10^122) |

Sidis's lasting insight is B, in Schulman's form: the arrow of time comes from boundary
conditions. A low-entropy *future* boundary would make a region run backwards. In our
observed universe, the only low-entropy boundary is the Big Bang.

Run `python -m chronopost physics` to see every number above computed.
