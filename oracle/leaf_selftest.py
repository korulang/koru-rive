#!/usr/bin/env python3
"""leaf_selftest.py -- enforce koru-rive's per-handle independence (LEAF_CONTRACT R1).

`run_gates.py` compares images, so a behavioural invariant has no place there.
This runs `kr/rive:selftest.handles` on a few fixtures: the verb opens the same
file twice, mutates only the first handle's input schedule, pointer log and VM
binding, and reports a leak if the second handle can see any of it.

    python3 oracle/leaf_selftest.py [file.riv ...]

Exit 0 = every fixture independent, 1 = a leak (the message says which handle saw
what), 2 = could not run the probe at all (build/toolchain), which is NOT a pass.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import authored_parity as ap  # noqa: E402

PROBE = '''import kr/rive
import std/io
kr/rive:selftest.handles(path: "{path}")
std/io:print.ln("SELFTEST_DONE")
'''

DEFAULT = [
    "joystick_databound_keyframe_test.riv",
    "car_widgets_v01.riv",
    "data_viz_demo.riv",
]


def main(argv):
    koruc = os.path.expanduser("~/src/koru/zig-out/bin/koruc")
    files = argv[1:] or [os.path.join(ap.ASSETS, f) for f in DEFAULT]
    bad = 0
    for path in files:
        name = os.path.basename(path)
        if not os.path.isfile(path):
            print(f"missing      {name}")
            bad += 1
            continue
        text, code = ap.run_probe(koruc, ap.ROOT, PROBE.format(path=path), 600)
        verdict = [l for l in text.splitlines() if "selftest.handles:" in l]
        if "SELFTEST_DONE" not in text:
            print(f"unavailable  {name} (probe produced no output; build or toolchain)")
            bad += 1
        elif not verdict:
            print(f"no-verdict   {name}")
            bad += 1
        elif "ok" in verdict[0]:
            print(f"independent  {name}")
        else:
            print(f"LEAK         {name}: {verdict[0].strip()}")
            bad += 1
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
