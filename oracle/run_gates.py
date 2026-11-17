#!/usr/bin/env python3
"""run_gates.py -- run every gate in oracle/gates.json through pixel_oracle.

The manifest is the only source of what a gate compares: both files are named
explicitly and must live in oracle/images/. Nothing is resolved by glob, by
mtime, or from /tmp -- a probe overwriting a /tmp name once made a gate show
the wrong render. Verdicts are computed here and written to
oracle/gate_verdicts.json; nobody types PASS.

  uv run --with numpy --with pillow python oracle/run_gates.py [--only GATE] [--json]
Exit 0 = every gate passed, 1 = at least one failed, 2 = manifest unusable.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pixel_oracle as po  # noqa: E402

IMG = os.path.join(HERE, "images")


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def load_manifest():
    gates = json.load(open(os.path.join(HERE, "gates.json")))
    for g in gates:
        for k in ("ours", "ref"):
            if os.path.basename(g[k]) != g[k] or not os.path.isfile(os.path.join(IMG, g[k])):
                print("REFUSING: gate %s %s=%r is not a file in oracle/images/" % (g["gate"], k, g[k]))
                sys.exit(2)
    return gates


def run_gate(g):
    ours, ref = os.path.join(IMG, g["ours"]), os.path.join(IMG, g["ref"])
    # The manifest IS the pairing declaration; the filename time token is
    # still enforced whenever both names carry one.
    untimed = po.time_token(ours) is None or po.time_token(ref) is None
    res = po.evaluate(ref, ours, bg=tuple(g["bg"]), comp=tuple(g["comp"]) if g.get("comp") else None,
                      bbox_axes="x,y", allow_missing_time=untimed)
    failed = [c["check"] for c in res["checks"] if not c["pass"]]
    return {"gate": g["gate"], "verdict": "PASS" if res["pass"] else "FAIL", "failed": failed,
            "hand_label": g["hand_label"], "ours": g["ours"], "ref": g["ref"],
            "vacuous": bool(res["report"].get("vacuous")),
            "ours_sha": sha(ours), "ref_sha": sha(ref), "checks": res["checks"], "report": res["report"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    gates = [g for g in load_manifest() if not a.only or g["gate"] == a.only]
    rows = [run_gate(g) for g in gates]
    if not a.only:
        json.dump(rows, open(os.path.join(HERE, "gate_verdicts.json"), "w"), indent=1, default=str)
    if a.json:
        print(json.dumps(rows, indent=1, default=str))
    else:
        for r in rows:
            print("%-13s %-4s (hand label %-5s) %s" % (r["gate"], r["verdict"], r["hand_label"],
                                                      ", ".join(r["failed"]) or "-"))
            if a.only:
                for c in r["checks"]:
                    print("    [%s] %-14s %s" % ("PASS" if c["pass"] else "FAIL", c["check"], c["detail"]))
        n = sum(r["verdict"] == "PASS" for r in rows)
        print("\n%d gates: %d PASS, %d FAIL" % (len(rows), n, len(rows) - n))
    sys.exit(0 if all(r["verdict"] == "PASS" for r in rows) else 1)


if __name__ == "__main__":
    main()
