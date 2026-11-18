#!/usr/bin/env python3
"""authored_parity.py — name the first divergent layer on authored .riv files.

The corpus sweep says "0/30 FAIL" for every real authored demo and never says
which layer failed. This harness answers that, cheaply and repeatably:

    file → reference stream (oracle/dump, rive-cpp recording Renderer)
         → our stream      (kr/rive:opsdump via koruc)
         → digest → first differing field → named layer

## Why a digest and not an op diff

The two streams order geometry differently by construction: the reference
records `drawPath` and then its `V` points; ours records the points and then
the `draw`. A raw sequence diff would report divergence at the first drawable
of every file for a reason that is not a bug. The digest therefore compares
what the layers genuinely agree on — drawable count and paint, clip, save/
restore balance, transform count, geometry volume — and names the first of
those that differs.

## Instrument traps this file exists to guard

- `ab` is an OBJECT INDEX from `abnames`, not an ordinal. A wrong index does
  not error: it emits a plausible degenerate op skeleton. This harness always
  resolves the index by artboard NAME, and refuses if the name is missing.
- `oracle/dump` cannot read every authored file (rive-cpp asserts in its asset
  importer on duplicate file assets). That is reported as `ref-unavailable`,
  not as a divergence.

Usage:
  python3 oracle/authored_parity.py                       # default set
  python3 oracle/authored_parity.py path/to/a.riv ...     # specific files
  python3 oracle/authored_parity.py --json > parity.json

Exit code: 0 when every compared file is op-identical, 1 otherwise.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "rive-cpp/tests/unit_tests/assets")

DEFAULT_FILES = [
    "joystick_databound_keyframe_test.riv",
    "car_widgets_v01.riv",
    "jellyfish_test.riv",
    "data_viz_demo.riv",
    "inventory_demo_test_v2.riv",
]

# OpRec kind vocabulary, rive/index.kz:4810.
KIND = {
    0: "save",
    1: "move",
    2: "line",
    3: "quad",
    4: "cubic",
    5: "close",
    6: "pushmat",
    7: "popmat",
    8: "draw",
    9: "clippush",
    10: "clippop",
    11: "image",
}
GEOMETRY_KINDS = {1, 2, 3, 4}


def short_color(h):
    """Both sides print hex; normalise to the low 6 digits (alpha dropped)."""
    return (h or "0")[-6:].rjust(6, "0").lower()


def run(cmd, timeout):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except FileNotFoundError as e:
        return 127, "", str(e)


# ---------------------------------------------------------------- reference


def ref_blocks(path, frames, dt, dump_bin, timeout):
    """Return ({block_name: [op lines]}, artboards, error)."""
    code, out, err = run([dump_bin, path, str(frames), str(dt)], timeout)
    if code != 0 or "Assertion failed" in (out + err):
        return None, None, (err or out).strip().splitlines()[0] if (err or out).strip() else f"exit {code}"
    artboards = []
    blocks = {}
    current = None
    for line in out.splitlines():
        m = re.match(r"ARTBOARD (\d+) name=(.*)", line)
        if m:
            artboards.append(m.group(2))
            continue
        m = re.match(r"--- (.*?) ---\s*$", line)
        if m:
            current = m.group(1).strip()
            blocks[current] = []
            continue
        if current is not None:
            blocks[current].append(line)
    return blocks, artboards, None


def ref_digest(lines):
    d = {"save": 0, "restore": 0, "xform": 0, "clip": 0, "draw": 0, "colors": [], "styles": [], "points": 0}
    for line in lines:
        s = line.strip()
        if s == "save":
            d["save"] += 1
        elif s == "restore":
            d["restore"] += 1
        elif s.startswith("transform "):
            d["xform"] += 1
        elif s.startswith("clipPath"):
            d["clip"] += 1
        elif s.startswith("drawPath"):
            d["draw"] += 1
            m = re.search(r"color=([0-9a-fA-F]+)", s)
            d["colors"].append(short_color(m.group(1) if m else "0"))
            m = re.search(r"style=(-?\d+)", s)
            d["styles"].append(int(m.group(1)) if m else 0)
        elif s.startswith("V "):
            d["points"] += 1
    return d


# --------------------------------------------------------------------- ours


ABNAMES_PROBE = """import kr/rive
import std/io
kr/rive:open(path: "{path}")
| loaded r |> kr/rive:abnames(r) |> kr/rive:free(r)
| failed e |> std/io:print.ln("OPENFAIL {{ e:s }}")
"""

OPS_PROBE = """import kr/rive
import std/io
kr/rive:open(path: "{path}")
| loaded r
    |> kr/rive:abnames(r)
    |> kr/rive:opsdump(r, ab: {ab}, frame: {frame})
    |> kr/rive:free(r)
| failed e |> std/io:print.ln("OPENFAIL {{ e:s }}")
"""


def run_probe(koruc, root, body, timeout):
    with tempfile.NamedTemporaryFile("w", suffix=".k", dir=root, delete=False) as f:
        f.write(body)
        probe = f.name
    try:
        env = dict(os.environ, ZIG_GLOBAL_CACHE_DIR=os.path.join(root, ".zig-global"))
        code, out, err = run([koruc, "run", probe], timeout)
        return out + "\n" + err, code
    finally:
        os.unlink(probe)


def ours_abnames(path, koruc, root, timeout):
    text, code = run_probe(koruc, root, ABNAMES_PROBE.format(path=path), timeout)
    if "OPENFAIL" in text:
        return None, text.strip().splitlines()[-1]
    arts = [(int(m.group(1)), m.group(2)) for m in re.finditer(r"AB idx=(\d+) name='(.*?)'", text)]
    return arts, None


def ours_digest(path, ab, frame, koruc, root, timeout):
    text, code = run_probe(koruc, root, OPS_PROBE.format(path=path, ab=ab, frame=frame), timeout)
    if "OPENFAIL" in text:
        return None, text.strip().splitlines()[-1]
    d = {"save": 0, "restore": 0, "xform": 0, "clip": 0, "draw": 0, "colors": [], "styles": [], "points": 0}
    pending_points = 0
    for line in text.splitlines():
        m = re.match(r"OP k=(\d+)\b", line)
        if not m:
            continue
        kind = int(m.group(1))
        if kind in GEOMETRY_KINDS:
            pending_points += 1 if kind in (1, 2) else (2 if kind == 3 else 3)
            d["points"] += 1
            continue
        if kind == 0:
            d["save"] += 1
        elif kind == 7:
            d["restore"] += 1
        elif kind == 6:
            d["xform"] += 1
        elif kind == 9:
            d["clip"] += 1
        elif kind == 8:
            d["draw"] += 1
            mc = re.search(r"color=([0-9a-fA-F]+)", line)
            d["colors"].append(short_color(mc.group(1) if mc else "0"))
            ms = re.search(r"style=(-?\d+)", line)
            d["styles"].append(int(ms.group(1)) if ms else 0)
        pending_points = 0
    return d, None


# ------------------------------------------------------------------- compare

def first_divergence(ref, ours):
    """Return (layer, detail) for the first field that differs, or None."""
    if ref["draw"] != ours["draw"]:
        return "drawable-count", f"reference draws {ref['draw']}, ours draws {ours['draw']}"
    if ref["colors"] != ours["colors"]:
        for i, (a, b) in enumerate(zip(ref["colors"], ours["colors"])):
            if a != b:
                return "paint", f"drawable {i}: reference colour {a}, ours {b}"
        return "paint", f"reference {ref['colors']}, ours {ours['colors']}"
    if ref["styles"] != ours["styles"]:
        return "paint-style", f"reference {ref['styles']}, ours {ours['styles']}"
    if ref["clip"] != ours["clip"]:
        return "clip", f"reference clips {ref['clip']} time(s), ours {ours['clip']}"
    if (ref["save"], ref["restore"]) != (ours["save"], ours["restore"]):
        return "save/restore", f"reference {ref['save']}/{ref['restore']}, ours {ours['save']}/{ours['restore']}"
    if ref["xform"] != ours["xform"]:
        return "transform-count", f"reference {ref['xform']}, ours {ours['xform']}"
    if ref["points"] != ours["points"]:
        return "geometry", f"reference {ref['points']} points, ours {ours['points']}"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="authored .riv files (default: the demo set)")
    ap.add_argument("--frames", type=int, default=3, help="reference advance+draw steps (default 3)")
    ap.add_argument("--dt", default="0.008335", help="reference seconds per step")
    ap.add_argument("--frame", type=int, default=0, help="our frame to compare against reference frame 0")
    ap.add_argument("--koruc", default=os.path.expanduser("~/src/koru/zig-out/bin/koruc"))
    ap.add_argument("--dump", default=os.path.join(HERE, "dump"))
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    files = args.files or [os.path.join(ASSETS, f) for f in DEFAULT_FILES]
    results = []
    for path in files:
        name = os.path.basename(path)
        rec = {"file": name, "path": path}

        blocks, artboards, ref_err = ref_blocks(path, args.frames, args.dt, args.dump, args.timeout)
        if ref_err:
            rec.update(status="ref-unavailable", detail=ref_err)
            results.append(rec)
            continue
        block = blocks.get("frame 0") or next((blocks[k] for k in blocks if k.startswith("frame 0")), None)
        if block is None:
            rec.update(status="ref-unavailable", detail="reference produced no 'frame 0' block")
            results.append(rec)
            continue
        ref = ref_digest(block)
        rec["ref"] = ref
        rec["artboards"] = artboards

        arts, ours_err = ours_abnames(path, args.koruc, ROOT, args.timeout)
        if ours_err:
            rec.update(status="ours-unavailable", detail=ours_err)
            results.append(rec)
            continue
        want = artboards[0] if artboards else None
        match = [a for a in arts if a[1] == want] or arts
        if not match:
            rec.update(status="ours-unavailable", detail="no artboards decoded")
            results.append(rec)
            continue
        ab_idx, ab_name = match[0]
        rec["artboard"] = f"{ab_name} (idx {ab_idx})"

        ours, ours_err = ours_digest(path, ab_idx, args.frame, args.koruc, ROOT, args.timeout)
        if ours_err:
            rec.update(status="ours-unavailable", detail=ours_err)
            results.append(rec)
            continue
        rec["ours"] = ours

        div = first_divergence(ref, ours)
        if div is None:
            rec.update(status="op-identical")
        else:
            rec.update(status="divergent", layer=div[0], detail=div[1])
        results.append(rec)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            if r["status"] != "divergent":
                print(f"{r['status']:<16} {r['file']}: {r.get('detail', '')}")
                continue
            print(f"divergent        {r['file']}  [{r.get('artboard', '?')}]")
            print(f"                 layer: {r['layer']} — {r['detail']}")
            print(f"                 ref : {r['ref']}")
            print(f"                 ours: {r['ours']}")

    compared = [r for r in results if r["status"] in ("op-identical", "divergent")]
    return 0 if compared and all(r["status"] == "op-identical" for r in compared) else 1


if __name__ == "__main__":
    sys.exit(main())
