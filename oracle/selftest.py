#!/usr/bin/env python3
"""Validate the oracle before trusting it.

A test that has never been shown to fail is not a test. This suite pins the
oracle's tolerances from both directions using mutants synthesised from a
reference render -- no renderer involved, so nothing here can be tuned to
flatter our output:

  MUST PASS  (false-positive control)  mutants that differ from the reference
             only in ways any independent correct rasteriser differs:
             sub-pixel registration, +/-1% intensity gain. If these fail, the
             oracle is too strict and would reject a correct renderer.

  MUST FAIL  (false-negative control)  mutants carrying one specific defect
             each. Every one must be caught, and by the check that names it.

Calibration rule: tune only until this matrix is correct. A tolerance that
makes a mutant slip through is a hole in the harness, not a rendering bug.

  python3 oracle/selftest.py --ref /tmp/rive_oracle/ref_f8.png [--inset 2]
Exit 0 = the oracle behaves; 1 = the oracle is broken. Do not read any
renderer result until this is green.
"""
import argparse
import os
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixel_oracle as po  # noqa: E402


def as_rgba(path):
    return np.asarray(Image.open(path).convert("RGBA")).astype(np.float64)


def save(arr, path):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA").save(path)


def shift(arr, dx, dy):
    """Bilinear sub-pixel shift with edge clamping.

    Edge-clamped, NOT np.roll: rolling wraps the border to the far side and
    manufactures ink that was never in the image, which would let a mutant
    fail for the wrong reason.
    """
    ix, iy = int(np.floor(dx)), int(np.floor(dy))
    fx, fy = dx - ix, dy - iy
    pad = np.pad(arr, ((16, 16), (16, 16), (0, 0)), mode="edge")
    h, w = arr.shape[0], arr.shape[1]
    def r(sy, sx):
        return pad[16 + sy:16 + sy + h, 16 + sx:16 + sx + w]
    return (r(iy, ix) * (1 - fx) * (1 - fy) + r(iy, ix + 1) * fx * (1 - fy)
            + r(iy + 1, ix) * (1 - fx) * fy + r(iy + 1, ix + 1) * fx * fy)


def gain(arr, bg, g):
    out = arr.copy()
    out[:, :, :3] = np.clip(bg + (arr[:, :, :3] - bg) * g, 0, 255)
    return out


def erase(arr, bg, box):
    out = arr.copy()
    x0, y0, x1, y1 = box
    out[y0:y1, x0:x1, :3] = bg
    return out


def build(ref, outdir, bg=49):
    rgba = as_rgba(ref)
    cases = []

    def add(name, arr, expect, must_fail=()):
        p = os.path.join(outdir, name + ".png")
        save(arr, p)
        cases.append((name, p, expect, tuple(must_fail)))

    # ---- MUST PASS: legitimate variation between correct rasterisers
    add("ok_identity", rgba, "pass")
    add("ok_shift_x_0.5", shift(rgba, 0.5, 0.0), "pass")
    add("ok_shift_xy_0.5", shift(rgba, 0.5, 0.5), "pass")
    add("ok_gain_0.99", gain(rgba, bg, 0.99), "pass")
    add("ok_gain_1.01", gain(rgba, bg, 1.01), "pass")

    # ---- MUST FAIL: one defect each, caught by the check that names it
    add("bad_stroke_thin26", gain(rgba, bg, 0.74), "fail", ["ink-mass"])
    add("bad_circle_missing", erase(rgba, bg, (155, 268, 345, 458)), "fail", ["ring", "coverage-gap"])
    add("bad_items_missing", erase(rgba, bg, (25, 145, 130, 240)), "fail", ["coverage-gap"])
    add("bad_shift_8px", shift(rgba, 8, 0), "fail", ["ink-bbox"])
    add("bad_misregister_2px", shift(rgba, 2, 0), "fail", ["coverage-gap"])
    wb = rgba.copy()
    wb[:, :, :3][np.all(np.abs(wb[:, :, :3] - bg) < 3, axis=2)] = 64
    add("bad_backdrop_colour", wb, "fail", ["backdrop"])
    ha = rgba.copy()
    ha[:, :, 3] = 128
    add("bad_alpha_halved", ha, "fail", ["alpha"])
    add("bad_size_cropped", rgba[10:-10, 10:-10], "fail", ["size"])
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="/tmp/rive_oracle/ref_f8.png")
    ap.add_argument("--inset", type=int, default=2)
    ap.add_argument("--bg", default="49,49,49")
    ap.add_argument("--ring", default=None, help="cx,cy,rin,rout in post-inset space")
    ap.add_argument("--independent", default=None,
                    help="path to the same content rasterised differently (e.g. rendered at 2x "
                         "and area-downsampled). MUST PASS: it is how the tolerance band is "
                         "pinned against a real second rasterisation instead of a synthetic shift.")
    ap.add_argument("--prev-identical", action="store_true", default=True,
                    help="also assert the staleness check rejects a duplicate frame")
    a = ap.parse_args()

    bg = tuple(int(x) for x in a.bg.split(","))
    ring = a.ring
    if ring is None:
        ring = "%.1f,%.1f,80,98" % (250 - a.inset, 363.5 - a.inset)

    tmpdir = tempfile.mkdtemp(prefix="oracle_selftest_")
    cases = build(a.ref, tmpdir, bg)

    rows, failures = [], []
    for name, path, expect, must_fail in cases:
        res = po.evaluate(a.ref, path, bg=bg, inset=a.inset,
                          ring=tuple(float(x) for x in ring.split(",")),
                          bbox_axes="x", allow_missing_time=True)
        got = "pass" if res["pass"] else "fail"
        failed = {c["check"] for c in res["checks"] if not c["pass"]}
        detail = ", ".join(sorted(failed)) or "-"
        ok = (got == expect)
        if ok and must_fail:
            missing = set(must_fail) - failed
            if missing:
                ok = False
                detail += "  MISSING:%s" % ",".join(sorted(missing))
        rows.append((name, expect, got, ok, detail))
        if not ok:
            failures.append(name)

    # staleness: a duplicate frame must be rejected
    if a.prev_identical:
        ident = os.path.join(tmpdir, "ok_identity.png")
        res = po.evaluate(a.ref, ident, bg=bg, inset=a.inset, prev=ident,
                          allow_missing_time=True)
        stale_failed = any(c["check"] == "stale" and not c["pass"] for c in res["checks"])
        ok = stale_failed
        rows.append(("bad_stale_duplicate", "fail", "fail" if stale_failed else "pass",
                     ok, "stale" if stale_failed else "-"))
        if not ok:
            failures.append("bad_stale_duplicate")

    # --- pairing guard: an unnamed pair must be refused, a mismatched time too
    import shutil
    ref_tagged = os.path.join(tmpdir, "ref_t33.png")
    shutil.copy(a.ref, ref_tagged)
    same = os.path.join(tmpdir, "render_t33.png")
    shutil.copy(os.path.join(tmpdir, "ok_identity.png"), same)
    other = os.path.join(tmpdir, "render_t66.png")
    shutil.copy(os.path.join(tmpdir, "ok_identity.png"), other)
    unnamed = os.path.join(tmpdir, "render_no_time.png")
    shutil.copy(os.path.join(tmpdir, "ok_identity.png"), unnamed)
    for name, refp, ourp, opts, expect in [
        ("ok_pair_t33_t33", ref_tagged, same, {}, "pass"),
        ("bad_pair_t33_t66", ref_tagged, other, {}, "fail"),
        ("bad_pair_unnamed", ref_tagged, unnamed, {}, "fail"),
        ("ok_pair_unnamed_allowed", a.ref, unnamed, {"allow_missing_time": True}, "pass"),
    ]:
        res = po.evaluate(refp, ourp, bg=bg, inset=a.inset,
                          ring=tuple(float(x) for x in ring.split(",")), **opts)
        failed = {c["check"] for c in res["checks"] if not c["pass"]}
        got = "pass" if res["pass"] else "fail"
        ok = got == expect
        rows.append((name, expect, got, ok, ", ".join(sorted(failed)) or "-"))
        if not ok:
            failures.append(name)

    if a.independent:
        res = po.evaluate(a.ref, a.independent, bg=bg, inset=a.inset,
                          ring=tuple(float(x) for x in ring.split(",")),
                          allow_missing_time=True)
        failed = {c["check"] for c in res["checks"] if not c["pass"]}
        got = "pass" if res["pass"] else "fail"
        ok = got == "pass"
        rows.append(("ok_independent_sampling", "pass", got, ok,
                     ", ".join(sorted(failed)) or "-"))
        if not ok:
            failures.append("ok_independent_sampling")

    w = max(len(r[0]) for r in rows) + 2
    print("ORACLE SELFTEST  ref=%s inset=%d" % (a.ref, a.inset))
    print("%-*s %-6s %-6s %-6s %s" % (w, "case", "want", "got", "ok", "failed checks"))
    for name, expect, got, ok, detail in rows:
        print("%-*s %-6s %-6s %-6s %s" % (w, name, expect, got, "OK" if ok else "**BAD**", detail))
    print()
    if failures:
        print("SELFTEST: FAIL -- %d case(s) behaved wrong: %s" % (len(failures), ", ".join(failures)))
        print("The oracle is not trustworthy. Fix the oracle before reading any renderer result.")
        sys.exit(1)
    print("SELFTEST: PASS -- oracle catches every mutant and tolerates legitimate AA phase.")


if __name__ == "__main__":
    main()
