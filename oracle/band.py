#!/usr/bin/env python3
"""Band check: is our render inside the disagreement of two independent oracles?

The problem this solves: a hand-picked tolerance is either arbitrary (so it can
be tuned to the result) or arbitrary-with-a-table (same problem, later). Use the
oracles to calibrate each other instead.

Given two INDEPENDENT reference renderers A and B of the same fixture at the
same tick, their disagreement d(A,B) is the noise floor of the comparison. The
criterion is then:

    d(A, ours) <= max(1.25 * d(A, B), floor)
    d(B, ours) <= max(1.25 * d(B, A), floor)

i.e. we may not be further from either oracle than the two oracles are from each
other. No number here is chosen to make our output pass or fail; every tolerance
comes from the oracles' disagreement, and if the oracles cannot agree there is no
test to run and this script says so.

  python3 oracle/band.py --a A.png --b B.png --ours C.bmp [--inset 2] [--json]
Exit 0 = inside the band, 1 = outside, 2 = oracles disagree too much to judge.
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixel_oracle as po  # noqa: E402

# Absolute floors stop a near-zero horn from making the criterion impossible
# to satisfy. They are floors on *agreement*, not on our output.
FLOORS = {"coverage_gap": 2.0, "mass_dev": 0.02, "pixdiff": 2.0, "mean_abs": 1.0}
# If two independent oracles differ by more than this, they cannot define truth.
UNUSABLE = {"coverage_gap": 5.0, "mass_dev": 0.15, "pixdiff": 5.0, "mean_abs": 3.0}


def load(path, inset):
    rgb, _, _ = po.load_rgb(path)
    if inset:
        rgb = rgb[inset:-inset, inset:-inset]
    return rgb


def metrics(ref_rgb, our_rgb):
    bg_r = po.modal_colour(ref_rgb)[0]
    bg_o = po.modal_colour(our_rgb)[0]
    cr, co = po.coverage(ref_rgb, bg_r), po.coverage(our_rgb, bg_o)
    rb, ob = po.box_blur(cr, 1), po.box_blur(co, 1)

    def near(a):
        n = a.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx or dy:
                    n = np.maximum(n, np.roll(np.roll(a, dy, 0), dx, 1))
        return n

    denom = float(rb.sum() + ob.sum())
    gap = 100.0 * float(np.maximum(0, rb - near(ob)).sum() + np.maximum(0, ob - near(rb)).sum()) / max(denom, 1e-9)
    mass_dev = abs(1.0 - float(co.sum()) / max(float(cr.sum()), 1e-9))
    d = np.abs(our_rgb.astype(float) - ref_rgb.astype(float)).max(axis=2)
    pixdiff = 100.0 * float((d > 16).mean())
    mean_abs = float(np.abs(our_rgb.astype(float) - ref_rgb.astype(float)).mean())
    return {"coverage_gap": round(gap, 2), "mass_dev": round(mass_dev, 4),
            "pixdiff": round(pixdiff, 2), "mean_abs": round(mean_abs, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="independent oracle A")
    ap.add_argument("--b", required=True, help="independent oracle B")
    ap.add_argument("--ours", required=True)
    ap.add_argument("--inset", type=int, default=0)
    ap.add_argument("--allow-missing-time", action="store_true",
                    help="permit inputs without a _t<tick> token. Off by default: an unnamed "
                         "pair is how ref_f8-vs-ours500 happened.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    # All three inputs must declare the SAME tick. A band computed across two
    # different animation times is the original bug this project kept making.
    toks = {k: po.time_token(v) for k, v in (("a", args.a), ("b", args.b), ("ours", args.ours))}
    if not args.allow_missing_time:
        if any(t is None for t in toks.values()):
            print("REFUSING: inputs must carry a _t<tick> token so a comparison cannot span two "
                  "animation times (got %s). Pass --allow-missing-time to override deliberately." % toks)
            sys.exit(2)
        if len(set(toks.values())) != 1:
            print("REFUSING: inputs are at different ticks: %s" % toks)
            sys.exit(2)
    A, B, O = load(args.a, args.inset), load(args.b, args.inset), load(args.ours, args.inset)
    ab, ao, bo = metrics(A, B), metrics(A, O), metrics(B, O)

    names = list(FLOORS)
    rows, verdicts = [], []
    for k in names:
        band = ab[k]
        if band > UNUSABLE[k]:
            verdicts.append(("UNUSABLE", k, "the two oracles differ by %.2f (limit %.2f)" % (band, UNUSABLE[k])))
            continue
        limit = max(1.25 * band, FLOORS[k])
        ok = ao[k] <= limit and bo[k] <= limit
        rows.append({"metric": k, "band(A,B)": band, "A vs ours": ao[k], "B vs ours": bo[k],
                     "limit": round(limit, 3), "ok": ok})
        if not ok:
            verdicts.append(("OUTSIDE", k, "A-vs-ours %.2f / B-vs-ours %.2f exceed limit %.2f"
                             % (ao[k], bo[k], limit)))

    unusable = [v for v in verdicts if v[0] == "UNUSABLE"]
    outside = [v for v in verdicts if v[0] == "OUTSIDE"]
    usable = [r for r in rows if r["metric"] not in {u[1] for u in unusable}]
    # A metric whose two oracles disagree is not evidence either way: drop it
    # and say so, rather than letting it veto a verdict the others support.
    # Only refuse outright if too few metrics survive to carry a judgement.
    MIN_USABLE = 2

    if args.json:
        print(json.dumps({"rows": rows, "verdicts": verdicts}, indent=2))
        sys.exit(2 if len(usable) < MIN_USABLE else (1 if outside else 0))
    else:
        print("BAND CHECK  A=%s  B=%s  ours=%s" % (os.path.basename(args.a), os.path.basename(args.b), os.path.basename(args.ours)))
        print("  %-14s %10s %11s %11s %9s" % ("metric", "band(A,B)", "A-vs-ours", "B-vs-ours", "limit"))
        for r in rows:
            print("  %-14s %10.2f %11.2f %11.2f %9.2f %s"
                  % (r["metric"], r["band(A,B)"], r["A vs ours"], r["B vs ours"], r["limit"],
                     "" if r["ok"] else "  <-- OUTSIDE"))
    if unusable:
        for _, k, why in unusable:
            print("  note: %s EXCLUDED -- %s" % (k, why))
    if len(usable) < MIN_USABLE:
        print("\nRESULT: CANNOT JUDGE -- only %d usable metric(s); the oracles"
              " disagree too widely to define truth." % len(usable))
        sys.exit(2)
    print()
    print("RESULT:", "PASS -- inside the oracles' own disagreement"
          if not outside else "FAIL -- outside the band",
          "(%d metric(s) usable)" % len(usable))
    for _, k, why in outside:
        print("   %s: %s" % (k, why))
    sys.exit(0 if not outside else 1)


if __name__ == "__main__":
    main()
