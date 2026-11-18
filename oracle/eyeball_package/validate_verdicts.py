#!/usr/bin/env python3
"""validate_verdicts.py — contract check for the eyeball audit deliverable.

Usage:
    python3 validate_verdicts.py [verdicts.jsonl]

Checks, against gates.json in this directory:
  * 33 lines, one JSON object per line, exact README schema (no extra keys)
  * enum membership for verdict / diff_kind / confidence
  * every gate once, no duplicates, no unknowns, none missing
  * every referenced pair image exists

Also reports exact-duplicate pair composites, because the audit's "33
gates" are not 33 independent observations. Exit 0 only when the
contract holds.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GATES = os.path.join(HERE, "gates.json")

VERDICTS = {"MATCH", "MINOR", "MISMATCH", "UNREADABLE"}
DIFF_KINDS = {"none", "edge-aa", "stroke", "fill-color", "transform",
              "missing-elem", "extra-elem", "backdrop", "text", "scale", "other"}
CONFIDENCE = {"high", "med", "low"}
FIELDS = {"gate", "verdict", "diff_kind", "region", "confidence", "note"}


def main(path):
    gates = json.load(open(GATES))
    gate_names = [g["gate"] for g in gates]
    known = set(gate_names)

    errors = []
    rows = []
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {lineno}: invalid JSON: {exc}")
                continue
            if set(row) != FIELDS:
                errors.append(f"line {lineno}: fields {sorted(row)} != {sorted(FIELDS)}")
            if row.get("verdict") not in VERDICTS:
                errors.append(f"line {lineno}: verdict {row.get('verdict')!r} not in {sorted(VERDICTS)}")
            if row.get("diff_kind") not in DIFF_KINDS:
                errors.append(f"line {lineno}: diff_kind {row.get('diff_kind')!r} not in {sorted(DIFF_KINDS)}")
            if row.get("confidence") not in CONFIDENCE:
                errors.append(f"line {lineno}: confidence {row.get('confidence')!r} not in {sorted(CONFIDENCE)}")
            if not isinstance(row.get("region"), str) or not row.get("region"):
                errors.append(f"line {lineno}: region must be a non-empty string")
            if not isinstance(row.get("note"), str) or not row.get("note"):
                errors.append(f"line {lineno}: note must be a non-empty string")
            rows.append(row)

    if len(rows) != len(gate_names):
        errors.append(f"{len(rows)} verdicts for {len(gate_names)} gates")
    seen = [r.get("gate") for r in rows]
    for name in seen:
        if name not in known:
            errors.append(f"unknown gate {name!r}")
    dupes = sorted({n for n in seen if seen.count(n) > 1})
    if dupes:
        errors.append(f"duplicate gate verdicts: {dupes}")
    missing = [g for g in gate_names if g not in seen]
    if missing:
        errors.append(f"missing gate verdicts: {missing}")

    # Order is not required by the contract, but report it.
    if not errors and seen != gate_names:
        print("note: verdict order differs from gates.json order")

    # Independent-observation count.
    groups = {}
    for g in gates:
        p = os.path.join(HERE, g["pair"])
        if not os.path.isfile(p):
            errors.append(f"gate {g['gate']}: missing pair {g['pair']}")
            continue
        digest = hashlib.sha256(open(p, "rb").read()).hexdigest()
        groups.setdefault(digest, []).append(g["gate"])
    dup_groups = {h: names for h, names in groups.items() if len(names) > 1}

    counts = {v: sum(1 for r in rows if r.get("verdict") == v) for v in sorted(VERDICTS)}
    print(f"verdicts: {len(rows)}  " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"unique pair composites: {len(groups)} of {len(gate_names)} gate(s)")
    for names in dup_groups.values():
        print("  shared composite:", ", ".join(names))

    if errors:
        print("\nFAIL")
        for e in errors:
            print("  -", e)
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "verdicts.jsonl")
    sys.exit(main(target))
