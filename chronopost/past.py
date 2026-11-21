"""Sending information to the past: a simulation.

Nobody knows a way to send information backwards in time. What physics *does*
offer are rules for what a backwards channel would have to obey if closed
timelike curves existed. This module simulates the two best-known rules.

Model
-----
A message ``m`` arrives at time t0 from the future. The world then runs
forward and at time t1 > t0 somebody sends a message back to t0. We write
that as ``respond(m) -> m'``: given what arrived, what gets sent back.

* **Novikov self-consistency** (classical, deterministic): only histories with
  ``respond(m) == m`` can happen. With no fixed point the setup is
  impossible (the grandfather paradox). With several, nothing in the laws
  picks one: that is a bootstrap ambiguity.

* **Deutsch (1991)** (quantum-inspired, probabilistic): ``respond`` returns
  a probability distribution, and the message on the loop must be a
  *stationary distribution* ``rho = T(rho)``. One always exists, so paradoxes
  turn into mixtures (the grandfather both is and isn't killed, 50/50).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Hashable, Iterable, Mapping, Sequence

Msg = Hashable


# ------------------------------------------------------------- Novikov ---

@dataclass
class NovikovResult:
    consistent: list[Msg]

    @property
    def verdict(self) -> str:
        k = len(self.consistent)
        if k == 0:
            return "PARADOX: no self-consistent history; the universe forbids this setup"
        if k == 1:
            return f"CONSISTENT LOOP: the only possible history carries {self.consistent[0]!r}"
        return (f"BOOTSTRAP AMBIGUITY: {k} consistent histories; physics does not "
                "choose, and the information comes from nowhere")


def novikov(messages: Iterable[Msg], respond: Callable[[Msg], Msg]) -> NovikovResult:
    """Return every message that is a fixed point of the loop."""
    return NovikovResult([m for m in messages if respond(m) == m])


# ------------------------------------------------------------- Deutsch ---

@dataclass
class DeutschResult:
    distribution: dict[Msg, float]
    iterations: int

    def most_likely(self) -> Msg:
        return max(self.distribution, key=self.distribution.get)


def deutsch(messages: Sequence[Msg],
            transition: Callable[[Msg], Mapping[Msg, float]],
            *, start: Mapping[Msg, float] | None = None,
            tol: float = 1e-12, max_iter: int = 100_000) -> DeutschResult:
    """Find a stationary distribution of the loop's Markov map.

    Power iteration on the lazy chain (T + I)/2 has the same fixed points as T
    and always converges for a finite state space, periodic chains included.
    """
    msgs = list(messages)
    rho = dict(start) if start else {m: 1 / len(msgs) for m in msgs}
    for i in range(1, max_iter + 1):
        nxt = {m: 0.5 * rho.get(m, 0.0) for m in msgs}
        for m, p in rho.items():
            if p:
                for m2, q in transition(m).items():
                    nxt[m2] += 0.5 * p * q
        if max(abs(nxt[m] - rho.get(m, 0.0)) for m in msgs) < tol:
            rho = nxt
            break
        rho = nxt
    clean = {m: round(p, 9) for m, p in rho.items() if p > 1e-9}
    return DeutschResult(clean, i)


# ----------------------------------------------------- time-loop compute ---

def ctc_solve(space: Sequence[Msg], predicate: Callable[[Msg], bool]) -> NovikovResult:
    """Use a self-consistent loop as a computer.

    Rule for the future self: "if the message I got is a solution, send it
    back unchanged; otherwise send the next candidate." Only solutions are
    fixed points, so under Novikov the only histories that can happen are the
    ones where the past self already holds an answer. The simulator still has
    to check every candidate; nature, if it allowed such a loop, would not.
    """
    idx = {m: i for i, m in enumerate(space)}

    def respond(m):
        return m if predicate(m) else space[(idx[m] + 1) % len(space)]

    return novikov(space, respond)


# ------------------------------------------------------------ scenarios ---

@dataclass
class Scenario:
    name: str
    story: str
    run: Callable[[], object] = field(repr=False)


def _grandfather():
    # message = "did grandfather survive?"  You go back iff he survived, and
    # then he doesn't.
    respond = lambda survived: not survived
    return (novikov([True, False], respond),
            deutsch([True, False], lambda s: {not s: 1.0}))


def _bootstrap():
    # An old woman hands you a proof. You later publish it and send it back.
    # Any proof you received is the one you send.
    proofs = ["proof A", "proof B", "proof C"]
    return novikov(proofs, lambda p: p), None


def _prophecy():
    # Oracle sends back tomorrow's weather. Hearing "storm" makes you cancel
    # the cloud seeding, which turns a storm into sun; hearing "sun" means you
    # seed the clouds and get rain.
    world = {"storm": "sun", "sun": "rain", "rain": "rain"}
    return novikov(world, world.__getitem__), None


def _noisy_grandfather():
    # Your gun jams 30% of the time.
    def t(survived):
        return {False: 0.7, True: 0.3} if survived else {True: 1.0}
    return None, deutsch([True, False], t)


def _factoring():
    n = 2021  # = 43 * 47
    return ctc_solve(range(2, 2021), lambda d: n % d == 0), None


SCENARIOS = {
    s.name: s for s in [
        Scenario("grandfather", "Go back and stop your grandfather iff he survived.", _grandfather),
        Scenario("bootstrap", "A proof with no author loops forever.", _bootstrap),
        Scenario("prophecy", "A weather forecast that changes the weather.", _prophecy),
        Scenario("noisy-grandfather", "The grandfather paradox with a gun that jams 30% of the time.", _noisy_grandfather),
        Scenario("factoring", "Factor 2021 with a time loop.", _factoring),
    ]
}
