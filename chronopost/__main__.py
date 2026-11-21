"""Command line: python -m chronopost {seal,open,calibrate,past}."""

from __future__ import annotations

import argparse
import sys
import time

from . import future, past


def _bar(frac: float) -> None:
    width = 40
    done = int(frac * width)
    sys.stderr.write(f"\r  [{'#' * done}{'.' * (width - done)}] {frac:6.1%}")
    if frac >= 1:
        sys.stderr.write("\n")
    sys.stderr.flush()


def cmd_calibrate(a):
    rate = future.calibrate(a.bits)
    print(f"{rate:,.0f} sequential squarings/second ({a.bits}-bit modulus)")
    for label, s in [("1 minute", 60), ("1 hour", 3600), ("1 day", 86400), ("1 year", 31_557_600)]:
        print(f"  {label:>8}: t = {int(rate * s):,}")


def cmd_seal(a):
    msg = a.message.encode() if a.message is not None else sys.stdin.buffer.read()
    cap = future.seal(msg, t=a.t, seconds=a.seconds, modulus_bits=a.bits, note=a.note)
    with open(a.out, "w") as f:
        f.write(cap.to_json())
    print(f"sealed {len(msg)} bytes into {a.out} (t = {cap.t:,} squarings)")


def cmd_open(a):
    with open(a.capsule) as f:
        cap = future.TimeCapsule.from_json(f.read())
    if cap.note:
        print(f"note: {cap.note}", file=sys.stderr)
    print(f"opening: {cap.t:,} sequential squarings...", file=sys.stderr)
    start = time.perf_counter()
    msg = future.open_capsule(cap, progress=_bar)
    print(f"opened in {time.perf_counter() - start:.1f}s", file=sys.stderr)
    sys.stdout.buffer.write(msg + b"\n")


def cmd_past(a):
    names = list(past.SCENARIOS) if a.scenario == "all" else [a.scenario]
    for name in names:
        s = past.SCENARIOS[name]
        print(f"== {s.name} ==\n{s.story}")
        nov, deu = s.run()
        if nov is not None:
            print(f"  Novikov: {nov.verdict}")
            if len(nov.consistent) > 1:
                print(f"           consistent: {nov.consistent}")
        if deu is not None:
            dist = ", ".join(f"{k!r}: {v:.3f}" for k, v in deu.distribution.items())
            print(f"  Deutsch: stationary mixture {{{dist}}}")
        print()


def main(argv=None):
    p = argparse.ArgumentParser(prog="chronopost", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("calibrate", help="measure how fast this machine squares")
    c.add_argument("--bits", type=int, default=2048)
    c.set_defaults(fn=cmd_calibrate)

    s = sub.add_parser("seal", help="send a message to the future")
    s.add_argument("message", nargs="?", help="text (default: read stdin)")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--seconds", type=float, help="approximate delay on this machine")
    g.add_argument("-t", type=int, help="exact number of squarings")
    s.add_argument("-o", "--out", default="capsule.json")
    s.add_argument("--bits", type=int, default=2048)
    s.add_argument("--note", default="", help="public label stored in clear")
    s.set_defaults(fn=cmd_seal)

    o = sub.add_parser("open", help="do the work and read a capsule")
    o.add_argument("capsule")
    o.set_defaults(fn=cmd_open)

    pa = sub.add_parser("past", help="simulate messages sent to the past")
    pa.add_argument("scenario", nargs="?", default="all", choices=["all", *past.SCENARIOS])
    pa.set_defaults(fn=cmd_past)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
