#!/usr/bin/env python3
"""Validate band.py -- the tool that issues verdicts.

`oracle/selftest.py` proves the pixel CHECKS can fail. It does not touch
`band.py`, which is what actually decides PASS / FAIL / CANNOT JUDGE. An
untested verdict function is the most dangerous part of a harness: if it always
returned PASS, every other check would be theatre.

Cases, built from two independent reference renders A and B:

  MUST PASS (0)
    ours == A                       - trivially inside the band
    ours == B                       - the other side of the band
    ours == A shifted 0.5px         - legitimate AA phase

  MUST FAIL (1)
    ours == A thinned 26%           - real fidelity loss
    ours == noise                   - unrelated image

  MUST REFUSE (2)
    A and B made to disagree wildly - the oracles cannot define truth, so no
                                      verdict is manufactured

  python3 oracle/band_selftest.py --a A.png --b B.png [--inset 2] [--json]
Exit 0 = band.py behaves on every path.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BAND = os.path.join(HERE, "band.py")


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.float64)


def save(arr, path):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").save(path)


def shift(arr, dx, dy):
    ix, iy = int(np.floor(dx)), int(np.floor(dy))
    fx, fy = dx - ix, dy - iy
    p = np.pad(arr, ((16, 16), (16, 16), (0, 0)), mode="edge")
    h, w = arr.shape[0], arr.shape[1]
    def r(sy, sx):
        return p[16 + sy:16 + sy + h, 16 + sx:16 + sx + w]
    return (r(iy, ix) * (1 - fx) * (1 - fy) + r(iy, ix + 1) * fx * (1 - fy)
            + r(iy + 1, ix) * (1 - fx) * fy + r(iy + 1, ix + 1) * fx * fy)


def thin(arr, bg, factor):
    out = arr.copy()
    out = bg + (out - bg) * factor
    return out


def scaled(arr, factor):
    """Scale about the centre and crop back to size -- makes B disagree with A
    on mass, pixel diff and coverage all at once."""
    h, w = arr.shape[:2]
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    big = im.resize((int(w * factor), int(h * factor)), Image.BICUBIC)
    left = (big.width - w) // 2
    top = (big.height - h) // 2
    return np.asarray(big.crop((left, top, left + w, top + h))).astype(np.float64)


def run_band(a, b, ours, inset):
    r = subprocess.run([sys.executable, BAND, "--a", a, "--b", b, "--ours", ours,
                        "--inset", str(inset), "--allow-missing-time", "--json"],
                       capture_output=True, text=True)
    try:
        payload = json.loads(r.stdout)
    except Exception:
        payload = None
    return r.returncode, payload, (r.stdout + r.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--inset", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    A, B = load(args.a), load(args.b)
    bg = np.median(A.reshape(-1, 3), axis=0)
    tmp = tempfile.mkdtemp(prefix="band_selftest_")

    def put(name, arr):
        p = os.path.join(tmp, name + ".png")
        save(arr, p)
        return p

    cases = [
        ("ok_ours_is_A", put("m_eq_a", A), args.a, args.b, 0),
        ("ok_ours_is_B", put("m_eq_b", B), args.a, args.b, 0),
        ("ok_shift_half_px", put("m_shift", shift(A, 0.5, 0.0)), args.a, args.b, 0),
        ("bad_thin_26pct", put("m_thin", thin(A, bg, 0.74)), args.a, args.b, 1),
        ("bad_unrelated_noise", put("m_noise", np.random.RandomState(7).rand(*A.shape) * 255),
         args.a, args.b, 1),
    ]

    rows, failures = [], []
    for name, ours, a, b, want in cases:
        code, payload, raw = run_band(a, b, ours, args.inset)
        ok = (code == want)
        detail = "" if payload is None else ",".join(
            r["metric"] for r in payload["rows"] if not r["ok"]) or "-"
        rows.append({"case": name, "want": want, "got": code, "ok": ok, "failing metrics": detail})
        if not ok:
            failures.append((name, want, code, raw[-300:]))

    # Oracles made to disagree so completely that NO metric can define truth.
    # (A merely scaled B still leaves 2 usable metrics, and with ours == A a
    # PASS is mathematically correct there -- verified, so this case uses an
    # unrelated image rather than a scaled one.)
    bad_b = put("m_unrelated_b", np.random.RandomState(11).rand(*B.shape) * 255)
    code, payload, raw = run_band(args.a, bad_b, args.a, args.inset)
    ok = (code == 2)
    rows.append({"case": "refuse_when_oracles_disagree", "want": 2, "got": code, "ok": ok,
                 "failing metrics": "exit"})
    if not ok:
        failures.append(("refuse_when_oracles_disagree", 2, code, raw[-300:]))

    if args.json:
        print(json.dumps({"rows": rows, "ok": not failures}, indent=2))
    else:
        w = max(len(r["case"]) for r in rows) + 2
        print("BAND SELFTEST  A=%s  B=%s" % (os.path.basename(args.a), os.path.basename(args.b)))
        print("%-*s %-5s %-5s %-6s %s" % (w, "case", "want", "got", "ok", "failing metrics"))
        for r in rows:
            print("%-*s %-5d %-5d %-6s %s" % (w, r["case"], r["want"], r["got"],
                                              "OK" if r["ok"] else "**BAD**", r["failing metrics"]))
        print()
        if failures:
            print("BAND SELFTEST: FAIL -- %d case(s): %s" % (len(failures), ", ".join(f[0] for f in failures)))
        else:
            print("BAND SELFTEST: PASS -- verdict logic correct on pass, fail and refuse paths.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
