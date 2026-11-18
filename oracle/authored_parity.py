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
    """Return ({(artboard_position, block_name): lines}, artboards, error).

    The dumper prints every ARTBOARD header first, then one stream per
    artboard in order — and every artboard's blocks carry the SAME marker text
    ("--- frame 0 t=0.0083 ---"). Keying by marker text alone therefore keeps
    only the last artboard, which silently compared our Main against the
    reference's *last* artboard (found by the parallel session; a real bug in
    this harness's first version). Key on the artboard position as well: a
    "static t=0" marker opens each new artboard's stream.
    """
    code, out, err = run([dump_bin, path, str(frames), str(dt)], timeout)
    if code != 0 or "Assertion failed" in (out + err):
        msg = (err or out).strip().splitlines()
        return None, None, msg[0] if msg else f"exit {code}"
    artboards = []
    blocks = {}
    ab_pos = -1
    current = None
    for line in out.splitlines():
        m = re.match(r"ARTBOARD (\d+) name=(.*)", line)
        if m:
            artboards.append(m.group(2))
            continue
        m = re.match(r"--- (.*?) ---\s*$", line)
        if m:
            name = m.group(1).strip()
            if name.startswith("static"):
                ab_pos += 1
            current = (ab_pos, name)
            blocks[current] = []
            continue
        if current is not None:
            blocks[current].append(line)
    return blocks, artboards, None


def _bbox(points):
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _bbox_close(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def frame0_block(blocks, pos):
    """Find artboard `pos`'s frame-0 block. Markers carry the timestamp
    ("--- frame 0 t=0.0083 ---"), so the name can only be prefix-matched."""
    return next((blocks[k] for k in blocks if k[0] == pos and k[1].startswith("frame 0")), None)


def ref_digest(lines):
    """Semantic digest of one reference block.

    `save`/`restore`/`transform` are the recorder's own state vocabulary and
    are kept for reporting only, never compared: our op stream has no
    renderer-state save at all (kind 0 is a PATH open, not a save).

    FillRule 2 is `clockwise`, which fills identically to nonZero; normalise
    it to 0 so only a genuine evenOdd/nonZero difference reports.

    Geometry is compared as a per-drawable bounding box, not a point count:
    the two streams represent the same rect differently (the reference omits
    the closing corner and prints a bare close marker, ours repeats it), so
    counts differ for reasons that are not ink.
    """
    d = {"save": 0, "restore": 0, "xform": 0, "clip": 0, "draw": 0,
         "colors": [], "styles": [], "rules": [], "points": 0, "draws": []}
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
            m = re.search(r"fillRule=(-?\d+)", s)
            rule = int(m.group(1)) if m else 0
            d["rules"].append(1 if rule == 1 else 0)
            d["draws"].append([])
        elif s.startswith("V ") and d["draws"]:
            parts = s.split()
            if len(parts) >= 4:
                d["points"] += 1
                d["draws"][-1].append((float(parts[-2]), float(parts[-1])))
    d["bboxes"] = [_bbox(p) for p in d["draws"]]
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
        env.setdefault("KORU_BACKEND_LIBPATH", os.path.expanduser("~/src/oshun/canvas/koruos-darwin"))
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
    # A probe that fails to build prints no op stream. An empty digest is NOT
    # "zero drawables" — say unavailable and quote the failure, or a broken
    # toolchain reports as a decoder finding (it did once).
    if "OPSDUMP" not in text:
        tail = [ln for ln in text.strip().splitlines() if ln.strip()][-1:]
        return None, f"no op stream emitted (exit {code}): {tail[0] if tail else 'no output'}"
    d = {"draw": 0, "colors": [], "styles": [], "rules": [], "clip": 0, "points": 0,
         "paths": 0, "matpush": 0, "matpop": 0, "draws": []}
    buf = []

    def pt(line, xg, yg):
        mx = re.search(xg + r"=(-?[0-9.]+)", line)
        my = re.search(yg + r"=(-?[0-9.]+)", line)
        if mx and my:
            buf.append((float(mx.group(1)), float(my.group(1))))

    for line in text.splitlines():
        m = re.match(r"OP k=(\d+)\b", line)
        if not m:
            continue
        kind = int(m.group(1))
        if kind in GEOMETRY_KINDS:
            d["points"] += 1
            if kind in (1, 2):
                pt(line, "x1", "y1")
            elif kind == 3:
                pt(line, "x1", "y1")
                pt(line, "x2", "y2")
            elif kind == 4:
                pt(line, "x1", "y1")
                pt(line, "x2", "y2")
                pt(line, "x3", "y3")
            continue
        if kind == 0:
            d["paths"] += 1  # path open — NOT a save
            buf = []
        elif kind == 6:
            d["matpush"] += 1
        elif kind == 7:
            d["matpop"] += 1
        elif kind == 9:
            d["clip"] += 1
        elif kind == 8:
            d["draw"] += 1
            mc = re.search(r"color=([0-9a-fA-F]+)", line)
            d["colors"].append(short_color(mc.group(1) if mc else "0"))
            ms = re.search(r"style=(-?\d+)", line)
            d["styles"].append(int(ms.group(1)) if ms else 0)
            me = re.search(r"eo=(\d+)", line)
            d["rules"].append(int(me.group(1)) if me else 0)
            d["draws"].append(list(buf))
            buf = []
    d["bboxes"] = [_bbox(p) for p in d["draws"]]
    return d, None


# ------------------------------------------------------------------- compare

def first_divergence(ref, ours):
    """Return (layer, detail) for the first field that differs, or None."""
    if ours["matpush"] != ours["matpop"]:
        return "matrix-balance", f"ours pushes {ours['matpush']} matrices and pops {ours['matpop']}"
    if ref["draw"] != ours["draw"]:
        return "drawable-count", f"reference draws {ref['draw']}, ours draws {ours['draw']}"
    if ref["colors"] != ours["colors"]:
        for i, (a, b) in enumerate(zip(ref["colors"], ours["colors"])):
            if a != b:
                return "paint", f"drawable {i}: reference colour {a}, ours {b}"
        return "paint", f"reference {ref['colors']}, ours {ours['colors']}"
    if ref["styles"] != ours["styles"]:
        return "paint-style", f"reference {ref['styles']}, ours {ours['styles']}"
    if ref["rules"] != ours["rules"]:
        for i, (a, b) in enumerate(zip(ref["rules"], ours["rules"])):
            if a != b:
                return "fill-rule", f"drawable {i}: reference {'evenOdd' if a else 'nonZero'}, ours {'evenOdd' if b else 'nonZero'}"
    if ref["clip"] != ours["clip"]:
        return "clip", f"reference clips {ref['clip']} time(s), ours {ours['clip']}"
    for i, (a, b) in enumerate(zip(ref["bboxes"], ours["bboxes"])):
        if not _bbox_close(a, b, 0.5):
            return "geometry", f"drawable {i}: reference bbox {a}, ours {b}"
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
    ap.add_argument("--all-artboards", action="store_true",
                    help="compare every reference artboard, not just the first")
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
        block = frame0_block(blocks, 0)
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

        # Which reference artboards to compare. Default: the first one, by name.
        if args.all_artboards:
            targets = [(pos, nm) for pos, nm in enumerate(artboards)]
        else:
            targets = [(0, artboards[0] if artboards else None)]

        per_ab = []
        for pos, want in targets:
            blk = frame0_block(blocks, pos)
            if blk is None:
                per_ab.append({"artboard": want, "status": "ref-unavailable", "detail": "no frame-0 block"})
                continue
            r_dig = ref_digest(blk)
            match = [a for a in arts if a[1] == want]
            if not match:
                per_ab.append({"artboard": want, "status": "ours-unavailable",
                               "detail": "artboard name not decoded", "ref_draw": r_dig["draw"]})
                continue
            ab_idx, ab_name = match[0]
            o_dig, o_err = ours_digest(path, ab_idx, args.frame, args.koruc, ROOT, args.timeout)
            if o_err:
                per_ab.append({"artboard": want, "status": "ours-unavailable", "detail": o_err,
                               "ref_draw": r_dig["draw"]})
                continue
            div = first_divergence(r_dig, o_dig)
            row = {"artboard": f"{ab_name} (idx {ab_idx})", "ref_draw": r_dig["draw"],
                   "ours_draw": o_dig["draw"], "ref_clip": r_dig["clip"], "ours_clip": o_dig["clip"]}
            if div is None:
                row["status"] = "op-identical"
            else:
                row["status"] = "divergent"
                row["layer"], row["detail"] = div
            row["ref_digest"], row["ours_digest"] = r_dig, o_dig
            per_ab.append(row)

        if args.all_artboards:
            rec["per_artboard"] = per_ab
            compared = [r for r in per_ab if r["status"] in ("op-identical", "divergent")]
            rec["status"] = "op-identical" if compared and all(r["status"] == "op-identical" for r in compared) else "divergent"
            results.append(rec)
            continue

        # single-artboard path keeps the flat record shape
        row = per_ab[0]
        if row["status"] == "ours-unavailable":
            rec.update(status="ours-unavailable", detail=row.get("detail", ""))
        elif row["status"] == "op-identical":
            rec.update(status="op-identical", artboard=row["artboard"])
        else:
            rec.update(status="divergent", layer=row.get("layer"), detail=row.get("detail"),
                       artboard=row["artboard"])
            rec["ours"] = row["ours_digest"]
        results.append(rec)

    if args.json:
        print(json.dumps(results, indent=2))
    elif args.all_artboards:
        for r in results:
            print(f"{r['status']:<16} {r['file']}")
            if r.get("detail") and "per_artboard" not in r:
                print(f"                 {r['detail']}")
            for row in r.get("per_artboard", []):
                if row["status"] in ("op-identical",):
                    print(f"  {row['artboard']:<28} {'op-identical':<14} draws {row['ref_draw']:>4}={row['ours_draw']:<4}")
                elif row["status"] == "divergent" and row.get("layer") == "drawable-count":
                    print(f"  {row['artboard']:<28} {'draws':<14} ref {row['ref_draw']:>4} ours {row['ours_draw']:>4}  ({row['ours_draw']-row['ref_draw']:+d})")
                else:
                    print(f"  {row['artboard']:<28} {row['status']:<14} {row.get('layer','')}: {row.get('detail','')}")
    else:
        for r in results:
            if r["status"] != "divergent":
                print(f"{r['status']:<16} {r['file']}: {r.get('detail', '')}")
                continue
            print(f"divergent        {r['file']}  [{r.get('artboard', '?')}]")
            print(f"                 layer: {r['layer']} — {r['detail']}")
            # Compact summary only: dumping the full digest buries the line that
            # matters (and once filled a terminal). --json has the detail.
            for side in ('ref', 'ours'):
                d = r.get(side)
                if not d:
                    continue
                cols = d.get('colors', [])
                print(f"                 {side:4}: draws {d['draw']:>4}  clips {d['clip']:>3}  "
                      f"fills/strokes {sum(1 for s in d.get('styles', []) if s == 1)}/"
                      f"{sum(1 for s in d.get('styles', []) if s == 0)}  "
                      f"colours {cols[:6]}{'...' if len(cols) > 6 else ''}")

    compared = [r for r in results if r["status"] in ("op-identical", "divergent")]
    return 0 if compared and all(r["status"] == "op-identical" for r in compared) else 1


if __name__ == "__main__":
    sys.exit(main())
