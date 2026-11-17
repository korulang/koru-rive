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

FIDELITY TIER (asserted; ours vs the REFERENCE, never vs a caller-supplied
colour). The checks above prove a feature class works; these certify that
what was drawn agrees with the reference. Every allowed difference is named:
    backdrop-px     away from all ink, at most --backdrop-px-frac of pixels
                    may differ by more than --backdrop-px-tol levels.
    ink-colour      (a) direction of the summed ink colour (ink minus
                    backdrop, per channel) agrees within --ink-hue-tol --
                    phase- and gain-invariant, so it also covers 1px strokes;
                    (b) on flat ink (ink on both sides, >1px from any colour
                    edge of the REFERENCE) mean and 95th-percentile channel
                    delta within --ink-core-mean / --ink-core-p95.
    registration    the sub-pixel translation that best aligns ours to the
                    reference is within --reg-tol px per axis. The only check
                    that notices a systematic 1px offset.
    frame-diff      pixels differing by more than --frame-px-tol that are NOT
                    on a colour edge present on BOTH sides may be at most
                    --frame-max of the frame. Edge-phase disagreement is the
                    one class excused here, and its size is printed; what it
                    excuses is bounded by registration (where the edge is),
                    ink-mass (how heavy) and anti-aliasing (how hard).
    anti-aliasing   ours has at least --aa-min of the reference's count of
                    blended edge pixels (a pixel sitting between the extremes
                    of its 3x3 neighbourhood). A render with no anti-aliasing
                    has edges in the right place with the right mass and is
                    invisible to every other check. One-sided on purpose:
                    softer-than-reference is indistinguishable from legitimate
                    sub-pixel phase and is NOT asserted (named gap).
    ink-coverage   ref ink signal inside the shared ink zone that ours
                    paints as backdrop is at most --notch-max of the
                    signal. The hole check anti-aliasing misses: the
                    blended-px COUNT can stay >= --aa-min while backdrop
                    notches open inside glyphs (kn_hw).

Vacuous agreement: when both sides carry < --vacuous-px ink, ink-dependent
checks pass as vacuous (empty-vs-empty fixtures); backdrop, size, pairing
and alpha still assert, so a white-vs-dark empty pair still fails.
    local-fidelity  the signed ours-minus-ref delta averaged over any
                    --local-window square may not exceed --local-tol levels.
                    The only check that notices a small element displaced
                    inside a large one: a whole-frame budget cannot separate
                    that from edge noise, a local signed mean can.

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


def erode(mask, radius):
    return ~dilate(~mask, radius)


def box_mean(a, r):
    """Mean over a (2r+1)^2 window, zero-padded (H,W,C) -> (H,W,C)."""
    h, w = a.shape[0], a.shape[1]
    pad = np.pad(a, ((r + 1, r), (r + 1, r), (0, 0)), mode="constant")
    c = pad.cumsum(axis=0).cumsum(axis=1)
    k = 2 * r + 1
    return (c[k:k + h, k:k + w] - c[0:h, k:k + w] - c[k:k + h, 0:w] + c[0:h, 0:w]) / float(k * k)


def colour_edge(rgb, thresh):
    """Pixels whose 3x3 neighbourhood spans more than `thresh` levels in any
    channel. Unlike an ink mask this sees edges INSIDE ink (text on a fill)."""
    f = rgb.astype(np.float64)
    pad = np.pad(f, ((1, 1), (1, 1), (0, 0)), mode="edge")
    h, w = f.shape[0], f.shape[1]
    hi, lo = f.copy(), f.copy()
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            v = pad[dy:dy + h, dx:dx + w]
            hi, lo = np.maximum(hi, v), np.minimum(lo, v)
    return (hi - lo).max(axis=2) > thresh


def shift2d(a, sx, sy):
    """Sample `a` at (x+sx, y+sy), bilinear, edge-clamped."""
    out = a
    for axis, sft in ((1, sx), (0, sy)):
        i = int(np.floor(sft))
        f = sft - i
        n = out.shape[axis]
        width = [(0, 0), (0, 0)]
        width[axis] = (4, 4)
        pad = np.pad(out, width, mode="edge")
        lo = np.take(pad, np.arange(4 + i, 4 + i + n), axis=axis)
        hi = np.take(pad, np.arange(5 + i, 5 + i + n), axis=axis)
        out = lo * (1 - f) + hi * f
    return out


def best_shift(ref_cov, our_cov, reach=2.0, step=0.25, margin=3):
    """(dx, dy) such that our_cov sampled at (x+dx, y+dy) best matches
    ref_cov, i.e. how far ours is displaced. Coordinate descent on L1 error;
    ties resolve toward zero so a direction with no edges reports 0."""
    cand = np.arange(-reach, reach + 1e-9, step)
    m = margin
    tgt = ref_cov[m:-m, m:-m]

    def err(sx, sy):
        return float(np.abs(shift2d(our_cov, sx, sy)[m:-m, m:-m] - tgt).sum())

    sx = sy = 0.0
    e0 = err(0.0, 0.0)
    for _ in range(2):
        for axis in (0, 1):
            es = [err(c, sy) if axis == 0 else err(sx, c) for c in cand]
            emin = min(es)
            ok = [c for c, e in zip(cand, es) if e <= emin + 0.05 * max(e0 - emin, 0.0) + 1e-9]
            pick = float(min(ok, key=abs))
            if axis == 0:
                sx = pick
            else:
                sy = pick
    return sx, sy


def blended_px(rgb, span_min=32.0, lo_t=0.2, hi_t=0.8):
    """Count pixels that sit strictly between the extremes of their 3x3
    neighbourhood (in the channel with the widest local span): the pixels
    anti-aliasing produces and a hard-edged raster does not."""
    f = rgb.astype(np.float64)
    pad = np.pad(f, ((1, 1), (1, 1), (0, 0)), mode="edge")
    h, w = f.shape[0], f.shape[1]
    hi, lo = f.copy(), f.copy()
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            v = pad[dy:dy + h, dx:dx + w]
            hi, lo = np.maximum(hi, v), np.minimum(lo, v)
    span = hi - lo
    ch = span.argmax(axis=2)[:, :, None]
    sp = np.take_along_axis(span, ch, 2)[:, :, 0]
    t = (np.take_along_axis(f, ch, 2)[:, :, 0] - np.take_along_axis(lo, ch, 2)[:, :, 0]) / np.maximum(sp, 1e-9)
    return int(((sp > span_min) & (t > lo_t) & (t < hi_t)).sum())


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
    # Two-sided AND channel-aware: ink may be darker OR brighter than
    # the backdrop, and mean-luminance alone misses colored fills whose
    # channels average out (dark green rows scored ~0.10 < 0.15 ink
    # threshold -> invisible to the metric). Per-channel max diff
    # catches any single-channel divergence; normalized by the larger
    # of the two dynamic ranges like before.
    bgc = np.asarray(bg, dtype=np.float64)
    chan = np.abs(rgb.astype(np.float64) - bgc).max(axis=2)
    b = float(np.mean(bgc))
    return np.clip(chan / max(b, 255.0 - b, 1.0), 0, 1)


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
             comp=None,
             backdrop_px_tol=2, backdrop_px_frac=0.005,
             ink_hue_tol=0.008, ink_core_mean=3.0, ink_core_p95=8, ink_core_min=64,
             reg_tol=0.75, frame_px_tol=16, frame_max=0.001, aa_min=0.5, aa_floor=64,
             local_window=33, local_tol=10.0, vacuous_px=200, notch_max=0.03):
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

    # Vacuous agreement: both sides carry ~no ink (empty-vs-empty fixtures
    # like cin/lwti/dcpo). Ink-dependent checks pass as vacuous; backdrop,
    # size, pairing and alpha still assert -- a white-vs-dark empty pair
    # (iba/deam/hff) still fails on those.
    ink_ref_n, ink_our_n = int(ref_ink.sum()), int(our_ink.sum())
    vacuous = ink_ref_n < vacuous_px and ink_our_n < vacuous_px

    rb, ob = bbox(ref_ink), bbox(our_ink)
    if vacuous:
        check("ink-bbox", True, "vacuous: both sides ~empty (ref=%d our=%d ink px)" % (ink_ref_n, ink_our_n))
    elif rb is None or ob is None:
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
    if vacuous:
        check("ink-mass", True, "vacuous: both sides ~empty (ref=%.0f ours=%.0f)" % (mass_ref, mass_our))
    else:
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
    if vacuous:
        check("coverage-gap", True, "vacuous: both sides ~empty")
    elif denom > 0:
        unmatched = float((np.maximum(0.0, cref_b - _near(cour_b)).sum()
                           + np.maximum(0.0, cour_b - _near(cref_b)).sum()) / denom)
        check("coverage-gap", unmatched <= gap_max,
              "%.2f%% of coverage unmatched either way within %dpx (max %.1f%%)"
              % (100 * unmatched, gap_px, 100 * gap_max))

    fid = {}
    # --- ink-coverage: ref ink signal inside the shared ink zone where ours
    # shows backdrop. anti-aliasing counts blended px; this catches holes --
    # ours painting backdrop where the reference still carries signal
    # (kn_hw: 139 such px passed every other check).
    if vacuous:
        check("ink-coverage", True, "vacuous: both sides ~empty")
    else:
        zone = dilate(ref_ink | our_ink, 2)
        ref_sig = zone & (cref > 0.10)
        nden = int(ref_sig.sum())
        if nden:
            notch = int((ref_sig & (cour < 0.05)).sum())
            nfrac = notch / nden
            fid["ink_coverage_notch_pct"] = round(100 * nfrac, 3)
            check("ink-coverage", nfrac <= notch_max,
                  "%.2f%% of %d ref-signal px inside shared ink zone are backdrop on ours (max %.1f%%)"
                  % (100 * nfrac, nden, 100 * notch_max))
        else:
            check("ink-coverage", True, "no shared ink zone -- vacuous")

    # ------------------------------------------------------- fidelity tier
    rf, of = ref_rgb.astype(np.float64), our_rgb.astype(np.float64)
    sd = of - rf                                  # signed, per channel
    d = np.abs(sd).max(axis=2)                    # per-pixel worst channel
    union = ref_ink | our_ink
    npx = float(d.size)

    # --- backdrop-px: ours vs ref where neither side has ink nearby.
    back = ~dilate(union, 2)
    if back.any():
        bfrac = float((d[back] > backdrop_px_tol).mean())
        fid["backdrop_px_pct_over_tol"] = round(100 * bfrac, 3)
        fid["backdrop_px_mean"] = round(float(d[back].mean()), 3)
        fid["backdrop_px_max"] = int(d[back].max())
        check("backdrop-px", bfrac <= backdrop_px_frac,
              "%.2f%% of %d backdrop px differ by >%d levels (max %.2f%%); mean %.2f, worst %d"
              % (100 * bfrac, int(back.sum()), backdrop_px_tol, 100 * backdrop_px_frac,
                 float(d[back].mean()), int(d[back].max())))
    else:
        check("backdrop-px", True, "no backdrop region away from ink -- vacuous")

    # --- ink-colour
    ref_bgc = np.asarray(modal_colour(ref_rgb)[0], dtype=np.float64)
    our_bgf = np.asarray(our_bgc, dtype=np.float64)
    near = ~back
    vr = (rf - ref_bgc)[near].sum(axis=0) if near.any() else np.zeros(3)
    vo = (of - our_bgf)[near].sum(axis=0) if near.any() else np.zeros(3)
    lr, lo = float(np.abs(vr).sum()), float(np.abs(vo).sum())
    parts, colour_ok = [], True
    if lr > 0 and lo > 0:
        hue = float(np.abs(vr / lr - vo / lo).max())
        fid["ink_hue_delta"] = round(hue, 4)
        colour_ok &= hue <= ink_hue_tol
        parts.append("hue delta %.4f (max %.3f)" % (hue, ink_hue_tol))
    else:
        parts.append("no ink on %s -- hue vacuous" % ("either side" if lr == lo == 0 else "one side"))
    edge_r = colour_edge(ref_rgb, frame_px_tol / 2.0)
    edge_o = colour_edge(our_rgb, frame_px_tol / 2.0)
    core = ref_ink & our_ink & ~dilate(edge_r, 1)
    ncore = int(core.sum())
    if ncore >= ink_core_min:
        cmean, cp95 = float(d[core].mean()), float(np.percentile(d[core], 95))
        fid["ink_core_px"], fid["ink_core_mean"], fid["ink_core_p95"] = ncore, round(cmean, 2), round(cp95, 1)
        colour_ok &= cmean <= ink_core_mean and cp95 <= ink_core_p95
        parts.append("flat ink %d px: mean %.2f (max %.1f) p95 %.0f (max %d)"
                     % (ncore, cmean, ink_core_mean, cp95, ink_core_p95))
    else:
        parts.append("flat ink %d px < %d -- thin ink, per-pixel colour vacuous" % (ncore, ink_core_min))
    check("ink-colour", colour_ok, "; ".join(parts))

    # --- registration: the translation that best aligns ours to the reference.
    if not vacuous and mass_ref > 0 and mass_our > 0:
        dx, dy = best_shift(cref, cour)
        fid["registration_dx"], fid["registration_dy"] = dx, dy
        check("registration", max(abs(dx), abs(dy)) <= reg_tol,
              "ours best aligns to ref when displaced dx=%+.2f dy=%+.2f px (max %.2f per axis)"
              % (dx, dy, reg_tol))
    else:
        check("registration", True, "vacuous: %s" % ("both sides ~empty" if vacuous else "no ink on at least one side"))

    # --- frame-diff: disagreement that edge phase cannot explain.
    if vacuous:
        check("frame-diff", True, "vacuous: both sides ~empty")
        fid["frame_disagree_pct"] = fid["frame_unexplained_pct"] = 0.0
    else:
        explained = dilate(edge_r, 1) & dilate(edge_o, 1)
        disagree = d > frame_px_tol
        unexplained = disagree & ~explained
        ufrac = float(unexplained.sum() / npx)
        fid["frame_disagree_pct"] = round(100 * float(disagree.sum() / npx), 3)
        fid["frame_unexplained_pct"] = round(100 * ufrac, 3)
        check("frame-diff", ufrac <= frame_max,
              "%.3f%% of frame differs by >%d levels off shared colour edges (max %.2f%%); "
              "total disagreeing %.3f%%, excused edge band %.2f%% of frame"
              % (100 * ufrac, frame_px_tol, 100 * frame_max,
                 100 * float(disagree.sum() / npx), 100 * float(explained.sum() / npx)))

    # --- anti-aliasing: a hard-edged raster has no blended edge pixels.
    aa_r, aa_o = blended_px(ref_rgb), blended_px(our_rgb)
    fid["aa_px_ref"], fid["aa_px_ours"] = aa_r, aa_o
    if aa_r >= aa_floor:
        fid["aa_ratio"] = round(aa_o / float(aa_r), 3)
        check("anti-aliasing", aa_o >= aa_min * aa_r,
              "blended edge px ours=%d ref=%d ratio %.2f (min %.2f)" % (aa_o, aa_r, aa_o / float(aa_r), aa_min))
    else:
        check("anti-aliasing", True, "reference has %d blended edge px < %d -- vacuous" % (aa_r, aa_floor))

    # --- local-fidelity: signed mean delta over a sliding window.
    if vacuous:
        check("local-fidelity", True, "vacuous: both sides ~empty")
    elif local_window:
        loc = np.abs(box_mean(sd, local_window // 2)).max(axis=2)
        ly, lx = np.unravel_index(int(loc.argmax()), loc.shape)
        lmax = float(loc.max())
        fid["local_max"] = round(lmax, 2)
        check("local-fidelity", lmax <= local_tol,
              "worst %dpx-window mean signed delta %.1f levels at x=%d y=%d (max %.1f)"
              % (local_window, lmax, int(lx), int(ly), local_tol))

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
    report["vacuous"] = 1 if vacuous else 0
    report.update(fid)
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
    ap.add_argument("--backdrop-px-tol", type=int, default=2)
    ap.add_argument("--backdrop-px-frac", type=float, default=0.005)
    ap.add_argument("--ink-hue-tol", type=float, default=0.008)
    ap.add_argument("--aa-min", type=float, default=0.5)
    ap.add_argument("--ink-core-mean", type=float, default=3.0)
    ap.add_argument("--ink-core-p95", type=int, default=8)
    ap.add_argument("--reg-tol", type=float, default=0.75)
    ap.add_argument("--frame-px-tol", type=int, default=16)
    ap.add_argument("--frame-max", type=float, default=0.001)
    ap.add_argument("--local-window", type=int, default=33,
                    help="side of the sliding window for local-fidelity (0 disables)")
    ap.add_argument("--local-tol", type=float, default=10.0)
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
        backdrop_px_tol=a.backdrop_px_tol, backdrop_px_frac=a.backdrop_px_frac,
        ink_hue_tol=a.ink_hue_tol, ink_core_mean=a.ink_core_mean, ink_core_p95=a.ink_core_p95,
        reg_tol=a.reg_tol, frame_px_tol=a.frame_px_tol, frame_max=a.frame_max, aa_min=a.aa_min,
        local_window=a.local_window, local_tol=a.local_tol,
        comp=tuple(int(x) for x in a.comp.split(",")) if a.comp else None,
    )
    if a.json:
        print(json.dumps(res, indent=2, default=str))
    elif not a.quiet:
        print("pixel_oracle: %s vs %s" % (a.ref, a.ours))
        for c in res["checks"]:
            print("  [%s] %-14s %s" % ("PASS" if c["pass"] else "FAIL", c["check"], c["detail"]))
        if res["report"]:
            print("  reported (measurements behind the checks; the checks are the verdict):")
            for k, v in res["report"].items():
                print("    %-24s %s" % (k, v))
    failed = [c for c in res["checks"] if not c["pass"]]
    print("RESULT:", "PASS" if not failed else "FAIL (%d)" % len(failed))
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
