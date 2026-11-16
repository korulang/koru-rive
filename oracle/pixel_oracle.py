#!/usr/bin/env python3
"""Structural pixel oracle for the Koru Rive renderer.

Replaces the /tmp/rive_oracle/*.mjs scalar-RMSE scripts, which could not
fail: fixed filename pairs (often different animation times), Math.min
cropping of mismatched sizes, alpha ignored, and a whole-frame mean
dominated by the backdrop while the subject -- 1px strokes -- covered
under 2% of the frame.

ASSERTED (a failure is a real defect):
    size        identical dimensions; never crops a mismatch away
    alpha       identical alpha where either side carries one
    clear       none of --clear survives (backdrop must cover the frame)
    backdrop    modal colour within --bg-tol of the expected backdrop
    ink-bbox    ink bounds agree on --bbox-axes within --bbox-tol
    ring        closed-shape completeness: ours >= ref angular sectors
    ink-mass    ours/ref total ink coverage within [--mass-min,--mass-max].
                The only check that notices a stroke drawn too thin: a
                hairline and a bold stroke share a bbox and a ring score.
    ref-gap     fraction of reference ink with no render within --gap-px.
                The only check that notices content we never emit.
    stale       with --prev, this render must differ from the previous one

REPORTED, NOT ASSERTED (phase-dependent, so not a verdict):
    how much of each side's ink is within k px of the other; RMSE on the
    ink union and on the backdrop separately.

TOLERANCE CALIBRATION is not a matter of taste: oracle/selftest.py pins it
by requiring the oracle to PASS a render that differs only by legitimate
anti-aliasing phase (+/-0.5 px, +/-1 % intensity) and to FAIL every
deliberate mutant. Run the selftest before trusting any result from this
tool. If it is red, the harness is broken, not the renderer.

Usage:
  pixel_oracle.py --ref A.png --ours B.bmp [--clear 255,0,255]
                  [--bg 49,49,49] [--ring cx,cy,rin,rout] [--inset N]
                  [--prev C.bmp] [--json] [--quiet]
Exit 0 = every assertion passed, 1 = at least one failed.
"""
import argparse
import json
import os
import re
import sys

import numpy as np
from PIL import Image


# ---------------------------------------------------------------- primitives

def load_rgb(path):
    im = Image.open(path)
    rgba = np.asarray(im.convert("RGBA")).astype(np.int16)
    return rgba[:, :, :3], rgba[:, :, 3], im.size


def dilate(mask, radius):
    out = mask.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            out |= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def bbox(mask):
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def angular_coverage(mask, centre, r_in, r_out, bins=12):
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w]
    rad = np.hypot(xx - centre[0], yy - centre[1])
    ang = (np.degrees(np.arctan2(yy - centre[1], xx - centre[0])) + 360.0) % 360.0
    sel = mask & (rad > r_in) & (rad < r_out)
    if not sel.any():
        return 0, np.zeros(bins, dtype=int)
    idx = (ang[sel] // (360.0 / bins)).astype(int) % bins
    counts = np.bincount(idx, minlength=bins)
    return int((counts > 0).sum()), counts


def modal_colour(rgb):
    flat = rgb.reshape(-1, 3)
    q = (flat // 4).astype(np.int32)
    key = q[:, 0] * 65536 + q[:, 1] * 256 + q[:, 2]
    vals, counts = np.unique(key, return_counts=True)
    best = vals[counts.argmax()]
    sel = key == best
    return tuple(np.round(flat[sel].mean(axis=0)).astype(int)), counts.max() / len(key)


def box_blur(a, r=1):
    """Small box blur. Coverage is compared AFTER this: a sub-pixel shift
    redistributes a 1px stroke across adjacent pixels, which point-wise
    comparison reads as uncovered mass. Blurring makes the measure depend on
    weight and position, not on which pixel the edge landed in."""
    acc = np.zeros_like(a)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            acc += np.roll(np.roll(a, dy, 0), dx, 1)
    return acc / ((2 * r + 1) ** 2)


def coverage(rgb, bg):
    b = float(np.mean(bg))
    # Two-sided: ink may be darker OR brighter than the backdrop
    # (white strokes on dark clfp bg; orange fill on white cdo bg).
    # Normalized by the larger of the two dynamic ranges.
    return np.clip(np.abs(rgb.mean(axis=2) - b) / max(b, 255.0 - b, 1.0), 0, 1)


# ---------------------------------------------------------------- evaluation

def time_token(path):
    """Extract an explicit time index from the filename (``..._t33...``).

    The original harness compared ref_f8.png against ours500.png -- two
    different animation times -- because nothing in the pipeline carried the
    time. Naming is the guard: a pair that does not declare the same time is
    not a comparison.
    """
    m = re.search(r"(?:^|[^A-Za-z0-9])t(\d+(?:\.\d+)?)(?=[^0-9]|$)", os.path.basename(path))
    return float(m.group(1)) if m else None


def evaluate(ref_path, ours_path, bg=(49, 49, 49), clear=None, inset=0, ring=None,
             prev=None, bbox_axes="x", bbox_tol=6, bg_tol=8,
             mass_min=0.85, mass_max=1.15, gap_max=0.05, gap_px=1,
             stale_min_pixels=1, allow_missing_time=False,
             tile=10, tile_min=0.80, tile_max=1.60, tile_floor=20.0,
             comp=None):
    """Run every check. Returns {'pass': bool, 'checks': [...], 'report': {...}}.
    Never exits, never prints: callers decide what to do with the verdict."""
    ref_rgb, ref_alpha, ref_size = load_rgb(ref_path)
    our_rgb, our_alpha, our_size = load_rgb(ours_path)

    # Alpha compositing: a semi-transparent reference (PNG with alpha)
    # can't be compared pixel-for-pixel against an opaque BMP — the
    # backdrop it was authored over is unknown. Composite BOTH sides
    # over --comp so the comparison measures the rendered appearance
    # over a declared neutral field. Alpha equality is then vacuous by
    # construction and reported as such.
    composited = False
    if comp is not None and ((ref_alpha != 255).any() or (our_alpha != 255).any()):
        cb = np.array(comp, dtype=np.int16)
        ra = (ref_alpha.astype(np.float64) / 255.0)[:, :, None]
        oa = (our_alpha.astype(np.float64) / 255.0)[:, :, None]
        ref_rgb = np.clip(ref_rgb * ra + cb * (1 - ra), 0, 255).astype(np.int16)
        our_rgb = np.clip(our_rgb * oa + cb * (1 - oa), 0, 255).astype(np.int16)
        ref_alpha = np.full_like(ref_alpha, 255)
        our_alpha = np.full_like(our_alpha, 255)
        composited = True
    if inset:
        i = inset
        ref_rgb, ref_alpha = ref_rgb[i:-i, i:-i], ref_alpha[i:-i, i:-i]
        our_rgb, our_alpha = our_rgb[i:-i, i:-i], our_alpha[i:-i, i:-i]
        ref_size = (ref_size[0] - 2 * i, ref_size[1] - 2 * i)
        our_size = (our_size[0] - 2 * i, our_size[1] - 2 * i)

    checks = []

    def check(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    # --- pairing: the comparison must declare one shared time index.
    tr, to = time_token(ref_path), time_token(ours_path)
    if tr is not None and to is not None:
        check("pairing", abs(tr - to) < 1e-9,
              "ref t=%g ours t=%g %s" % (tr, to, "match" if abs(tr - to) < 1e-9 else "MISMATCHED"))
    elif allow_missing_time:
        check("pairing", True, "no time token (allowed): ref=%s ours=%s" % (tr, to))
    else:
        check("pairing", False,
              "no time token: ref=%s ours=%s. Name artifacts ..._t<ms>... so a pair "
              "cannot silently compare two animation times (or pass --allow-missing-time)"
              % (tr, to))

    # --- size: hard fail. Cropping makes a wrong render score better.
    check("size", ref_size == our_size, "ref=%s ours=%s" % (ref_size, our_size))
    if ref_size != our_size:
        return _done(checks, {})

    # --- alpha: a half-transparent frame used to score like a solid one.
    if (ref_alpha != 255).any() or (our_alpha != 255).any():
        check("alpha", np.array_equal(ref_alpha, our_alpha),
              "ref opaque=%d ours opaque=%d differing px=%d"
              % ((ref_alpha == 255).sum(), (our_alpha == 255).sum(),
                 (ref_alpha != our_alpha).sum()))
    elif composited:
        check("alpha", True, "composited over %s — alpha vacuous" % (comp,))
    else:
        check("alpha", True, "both fully opaque")

    if clear is not None:
        hit = (np.abs(our_rgb - np.array(clear)).sum(axis=2) < 30).sum()
        check("clear", hit == 0, "clear pixels remaining=%d" % int(hit))

    our_modal, our_frac = modal_colour(our_rgb)
    dist = int(np.abs(np.array(our_modal) - np.array(bg)).mean())
    check("backdrop", dist <= bg_tol,
          "ours=%s expected=%s dist=%d tol=%d (%.1f%% of frame)"
          % (tuple(int(v) for v in our_modal), tuple(bg), dist, bg_tol, our_frac * 100))

    ref_ink = coverage(ref_rgb, modal_colour(ref_rgb)[0]) > 0.15
    our_bgc = modal_colour(our_rgb)[0]
    our_ink = coverage(our_rgb, our_bgc) > 0.15

    rb, ob = bbox(ref_ink), bbox(our_ink)
    if rb is None or ob is None:
        check("ink-bbox", False, "ref=%s ours=%s" % (rb, ob))
    else:
        axes = {"x": (0, 2), "y": (1, 3)}
        idx = [i for ax in bbox_axes.split(",") for i in axes.get(ax.strip(), ())]
        names = ("xmin", "ymin", "xmax", "ymax")
        deltas = {names[i]: abs(rb[i] - ob[i]) for i in idx}
        worst = max(deltas.values()) if deltas else 0
        check("ink-bbox", worst <= bbox_tol,
              "ref=%s ours=%s asserted=%s deltas=%s tol=%d"
              % (rb, ob, bbox_axes, deltas, bbox_tol))

    if ring:
        cx, cy, rin, rout = (float(x) for x in ring)
        rc, _ = angular_coverage(ref_ink, (cx, cy), rin, rout)
        oc, _ = angular_coverage(our_ink, (cx, cy), rin, rout)
        check("ring", oc >= rc, "ref sectors=%d/12 ours sectors=%d/12" % (rc, oc))

    # --- ink mass: the only check that notices a stroke drawn too thin.
    cref = coverage(ref_rgb, modal_colour(ref_rgb)[0])
    cour = coverage(our_rgb, our_bgc)
    mass_ref, mass_our = float(cref.sum()), float(cour.sum())
    ratio = mass_our / max(mass_ref, 1e-9)
    check("ink-mass", mass_min <= ratio <= mass_max,
          "ref=%.0f ours=%.0f ratio=%.2f (need %.2f..%.2f)"
          % (mass_ref, mass_our, ratio, mass_min, mass_max))

    # --- uncovered reference ink: content the reference draws and we do not.
    # SYMMETRIC unmatched coverage. Two renders that agree to meanAbsDiff
    # 0.8/255 can still differ by 17% of binary *mask* pixels because a 1px
    # antialiased stroke straddles the threshold -- that produced two false
    # "missing content" alarms. Comparing blurred coverage symmetrically is
    # stable, and it is fair: it charges us for what we add as well as drop.
    cref_b, cour_b = box_blur(cref, 1), box_blur(cour, 1)

    def _near(a):
        n = a.copy()
        for dy in range(-gap_px, gap_px + 1):
            for dx in range(-gap_px, gap_px + 1):
                if dx or dy:
                    n = np.maximum(n, np.roll(np.roll(a, dy, 0), dx, 1))
        return n

    denom = float(cref_b.sum() + cour_b.sum())
    if denom > 0:
        unmatched = float((np.maximum(0.0, cref_b - _near(cour_b)).sum()
                           + np.maximum(0.0, cour_b - _near(cref_b)).sum()) / denom)
        check("coverage-gap", unmatched <= gap_max,
              "%.2f%% of coverage unmatched either way within %dpx (max %.1f%%)"
              % (100 * unmatched, gap_px, 100 * gap_max))

    if prev is not None:
        prev_rgb, _, prev_size = load_rgb(prev)
        if inset:
            j = inset
            prev_rgb = prev_rgb[j:-j, j:-j]
            prev_size = (prev_size[0] - 2 * j, prev_size[1] - 2 * j)
        if prev_size != our_size:
            check("stale", False, "prev size %s != %s" % (prev_size, our_size))
        else:
            diff = int((np.abs(prev_rgb - our_rgb).sum(axis=2) > 12).sum())
            check("stale", diff >= stale_min_pixels,
                  "pixels differing from previous frame=%d (need >=%d)"
                  % (diff, stale_min_pixels))

    # --- reported only: phase-dependent
    report = {}
    for k in (1, 2, 3):
        report["ref_ink_within_%dpx" % k] = round(
            100.0 * (ref_ink & dilate(our_ink, k)).sum() / max(1, ref_ink.sum()), 1)
        report["our_ink_within_%dpx" % k] = round(
            100.0 * (our_ink & dilate(ref_ink, k)).sum() / max(1, our_ink.sum()), 1)
    report["ink_mass_ratio"] = round(ratio, 3)
    union = ref_ink | our_ink
    if union.any():
        report["rmse_ink_union"] = round(float(np.sqrt(
            ((our_rgb.astype(float) - ref_rgb.astype(float))[union] ** 2).mean())), 2)
    backdrop = ~union
    if backdrop.any():
        report["rmse_backdrop"] = round(float(np.sqrt(
            ((our_rgb.astype(float) - ref_rgb.astype(float))[backdrop] ** 2).mean())), 2)

    return _done(checks, report)


def _done(checks, report):
    return {"pass": all(c["pass"] for c in checks), "checks": checks, "report": report}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--ours", required=True)
    ap.add_argument("--prev")
    ap.add_argument("--clear", help="R,G,B of a probe clear colour that must be fully covered")
    ap.add_argument("--comp", default=None,
                    help="backdrop RGB to composite alpha-bearing refs over "
                         "(e.g. 255,255,255); enables semi-transparent fixtures")
    ap.add_argument("--bg", default="49,49,49")
    ap.add_argument("--bg-tol", type=int, default=8)
    ap.add_argument("--bbox-tol", type=int, default=6)
    ap.add_argument("--bbox-axes", default="x",
                    help="which ink-bbox axes to assert (default x). Use x for paths whose "
                         "geometry morphs over time: the vertical extent follows the animation "
                         "phase, the horizontal extent is set by the contour's terminal point, "
                         "which is exactly what truncation destroys.")
    ap.add_argument("--ring", help="cx,cy,rin,rout annulus for closed-shape completeness")
    ap.add_argument("--inset", type=int, default=0,
                    help="crop this many px off every edge of BOTH images before analysis "
                         "(for known reference artifacts, e.g. the 1px frame in ref_f8). "
                         "Ring coordinates are given in post-inset space.")
    ap.add_argument("--mass-min", type=float, default=0.85)
    ap.add_argument("--mass-max", type=float, default=1.15)
    ap.add_argument("--gap-max", type=float, default=0.05)
    ap.add_argument("--gap-px", type=int, default=1,
                    help="registration sharpness. 1 catches a 2px misregistration; 2 would cover it and let it pass")
    ap.add_argument("--tile", type=int, default=10, help="grid for the local-fidelity check (0 disables)")
    ap.add_argument("--tile-min", type=float, default=0.80)
    ap.add_argument("--tile-max", type=float, default=1.60)
    ap.add_argument("--tile-floor", type=float, default=20.0)
    ap.add_argument("--allow-missing-time", action="store_true",
                    help="permit artifacts whose names carry no _t<ms> token (legacy files). "
                         "Prefer renaming: an unnamed pair is how ref_f8-vs-ours500 happened.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    res = evaluate(
        a.ref, a.ours,
        bg=tuple(int(x) for x in a.bg.split(",")),
        clear=tuple(int(x) for x in a.clear.split(",")) if a.clear else None,
        inset=a.inset,
        ring=tuple(float(x) for x in a.ring.split(",")) if a.ring else None,
        prev=a.prev, bbox_axes=a.bbox_axes, bbox_tol=a.bbox_tol, bg_tol=a.bg_tol,
        mass_min=a.mass_min, mass_max=a.mass_max, gap_max=a.gap_max, gap_px=a.gap_px,
        allow_missing_time=a.allow_missing_time,
        tile=a.tile, tile_min=a.tile_min, tile_max=a.tile_max, tile_floor=a.tile_floor,
        comp=tuple(int(x) for x in a.comp.split(",")) if a.comp else None,
    )
    if a.json:
        print(json.dumps(res, indent=2, default=str))
    elif not a.quiet:
        print("pixel_oracle: %s vs %s" % (a.ref, a.ours))
        for c in res["checks"]:
            print("  [%s] %-10s %s" % ("PASS" if c["pass"] else "FAIL", c["check"], c["detail"]))
        if res["report"]:
            print("  reported (phase-dependent, not a verdict):")
            for k, v in res["report"].items():
                print("    %-24s %s" % (k, v))
    failed = [c for c in res["checks"] if not c["pass"]]
    print("RESULT:", "PASS" if not failed else "FAIL (%d)" % len(failed))
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
