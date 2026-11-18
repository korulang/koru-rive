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

FIDELITY TIER. Each fidelity check (backdrop-px, ink-colour, registration,
frame-diff, local-fidelity) has at least one mutant that only it is required
to catch, on two references: a thin-stroke fixture (--ref) and a filled one
with text inside fills (--ref-fill). The run ends with a calibration table:
per check, the worst value any MUST-PASS control reached, the tolerance, and
the value of the mutant aimed at it. A tolerance is miscalibrated exactly when
that table shows a control above it or a mutant below it -- that table, not a
renderer result, is the only licence to move a number.

  python3 oracle/selftest.py [--ref strokes.png --inset N] [--ref-fill fills.png]
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
HERE = os.path.dirname(os.path.abspath(__file__))
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


def ink_mask(arr, bg, thresh=40):
    return np.abs(arr[:, :, :3] - np.asarray(bg, dtype=np.float64)).max(axis=2) > thresh


def tint(arr, bg, rgb_gain):
    """Scale ink (distance from backdrop) per channel: a hue error."""
    out = arr.copy()
    out[:, :, :3] = np.clip(bg + (arr[:, :, :3] - bg) * np.asarray(rgb_gain), 0, 255)
    return out


def build_fidelity(ref, outdir, bg, prefix, filled):
    """Mutants for the fidelity tier. `aimed` names the one check each mutant
    exists to trip and the report metric that measures it."""
    rgba = as_rgba(ref)
    bgf = np.asarray(bg, dtype=np.float64)
    cases = []

    def add(name, arr, expect, must_fail=(), opts=None, aimed=None):
        p = os.path.join(outdir, prefix + name + ".png")
        save(arr, p)
        cases.append((prefix + name, p, expect, tuple(must_fail), opts or {}, aimed))

    add("ok_identity", rgba, "pass")
    add("ok_shift_x_0.5", shift(rgba, 0.5, 0.0), "pass")
    add("ok_shift_xy_0.5", shift(rgba, 0.5, 0.5), "pass")
    add("ok_gain_0.99", gain(rgba, bgf, 0.99), "pass")
    add("ok_gain_1.01", gain(rgba, bgf, 1.01), "pass")

    back = ~ink_mask(rgba, bgf, 3)
    # backdrop off by 4 levels: inside the modal `backdrop` tolerance (8), so
    # only a per-pixel ours-vs-ref check can see it.
    m = rgba.copy()
    m[:, :, :3][back] += 4
    add("bad_backdrop_shift4", m, "fail", ["backdrop-px"], aimed=("backdrop-px", "backdrop_px_pct_over_tol"))
    # the brief's headline case: opposite backdrop, with the caller passing a
    # --bg that matches OURS, which is how it used to pass.
    m = rgba.copy()
    m[:, :, :3][back] = 255.0 - bgf
    add("bad_backdrop_inverted_bg_matches_ours", m, "fail", ["backdrop-px"],
        opts={"bg": tuple(int(v) for v in (255.0 - bgf))})
    # hue error: ink loses 10% of its blue. Same geometry, same mass class.
    add("bad_ink_tint_blue90", tint(rgba, bgf, (1.0, 1.0, 0.90)), "fail", ["ink-colour"],
        aimed=("ink-colour", "ink_hue_delta"))
    # systematic 1px offset: inside ink-bbox tolerance and coverage-gap reach.
    add("bad_offset_1px", shift(rgba, 1.0, 0.0), "fail", ["registration"],
        aimed=("registration", "registration_dx"))
    add("bad_offset_1px_y", shift(rgba, 0.0, 1.0), "fail", ["registration"],
        aimed=("registration", "registration_dy"))
    if not filled:
        # no anti-aliasing: every pixel snapped to full ink or backdrop.
        inkc = np.asarray(po.modal_colour(rgba[:, :, :3][ink_mask(rgba, bgf, 150)].reshape(-1, 1, 3).astype(np.int16))[0],
                          dtype=np.float64)
        cov = np.abs(rgba[:, :, :3] - bgf).max(axis=2) / max(1.0, float(np.abs(inkc - bgf).max()))
        m = rgba.copy()
        m[:, :, :3] = np.where((cov >= 0.5)[:, :, None], inkc, bgf)
        add("bad_aliased_no_aa", m, "fail", ["anti-aliasing"], aimed=("anti-aliasing", "aa_ratio"))
    if filled:
        ink = ink_mask(rgba, bgf)
        # "off by a little but visible": every ink pixel 6 levels darker.
        m = rgba.copy()
        m[:, :, :3][ink] -= 6
        add("bad_ink_shift6", m, "fail", ["ink-colour"], aimed=("ink-colour", "ink_core_mean"))
        # speckle: 8% of deep ink pixels 12 levels off. Mean stays under the
        # mean tolerance and 12 is under the frame-diff pixel tolerance, so
        # only the percentile bound sees it.
        rng0 = np.random.default_rng(11)
        ys0, xs0 = np.nonzero(po.erode(ink, 3))
        pk = rng0.choice(len(ys0), size=int(0.08 * len(ys0)), replace=False)
        m = rgba.copy()
        m[ys0[pk], xs0[pk], :3] -= 12
        add("bad_ink_speckle12", m, "fail", ["ink-colour"], aimed=("ink-colour", "ink_core_p95"))
        # pinholes: isolated wrong pixels deep inside fills, 0.2% of the frame.
        rng = np.random.default_rng(7)
        deep = po.erode(ink, 3)
        ys, xs = np.nonzero(deep)
        pick = rng.choice(len(ys), size=int(0.002 * ink.size), replace=False)
        m = rgba.copy()
        m[ys[pick], xs[pick], :3] = bgf
        add("bad_pinholes_0.2pct", m, "fail", ["frame-diff"], aimed=("frame-diff", "frame_unexplained_pct"))
        # a small element displaced inside a large one: the block holding the
        # most non-dominant ink (text on a fill) moves 14px; its old place is
        # filled with the surrounding fill colour.
        dom = np.asarray(po.modal_colour(rgba[:, :, :3][ink].reshape(-1, 1, 3).astype(np.int16))[0], dtype=np.float64)
        detail = ink & (np.abs(rgba[:, :, :3] - dom).max(axis=2) > 40)
        best, bw, bh = None, 48, 40
        for y0 in range(0, rgba.shape[0] - bh, 4):
            for x0 in range(0, rgba.shape[1] - bw - 20, 4):
                blk = ink[y0:y0 + bh, x0:x0 + bw + 14]
                if not blk.all():
                    continue
                n = int(detail[y0:y0 + bh, x0:x0 + bw].sum())
                if best is None or n > best[0]:
                    best = (n, x0, y0)
        if best is None or best[0] < 100:
            raise SystemExit("selftest: --ref-fill has no small element inside a fill to displace")
        _, x0, y0 = best
        m = rgba.copy()
        blk = rgba[y0:y0 + bh, x0:x0 + bw].copy()
        m[y0:y0 + bh, x0:x0 + bw, :3] = dom
        m[y0:y0 + bh, x0 + 14:x0 + 14 + bw] = blk
        add("bad_element_displaced_14px", m, "fail", ["local-fidelity"], aimed=("local-fidelity", "local_max"))
    # notch: backdrop-coloured holes inside ink -- the class anti-aliasing's
    # blended-px count cannot see (kn_hw). 15% of strong-ink pixels.
    ink = ink_mask(rgba, bgf, 100)
    ys, xs = np.nonzero(ink)
    if len(ys):
        rng = np.random.default_rng(23)
        pick = rng.choice(len(ys), size=max(1, int(0.15 * len(ys))), replace=False)
        m = rgba.copy()
        m[ys[pick], xs[pick], :3] = bgf
        add("bad_notches_15pct", m, "fail", ["ink-coverage"],
            aimed=("ink-coverage", "ink_coverage_notch_pct"))
    # empty-vs-content: a blank ours must still fail the ink checks.
    blank = rgba.copy()
    blank[:, :, :3] = bgf
    blank[:, :, 3] = 255
    add("bad_ours_empty", blank, "fail", ["ink-bbox", "ink-mass"])
    return cases


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
    ap.add_argument("--ref", default=os.path.join(HERE, "images", "ref_clfp_c_t1.png"),
                    help="thin-stroke reference (clfp Main tick 1)")
    ap.add_argument("--inset", type=int, default=0)
    ap.add_argument("--ref-fill", default=os.path.join(HERE, "images", "ref_cl1_main_t1.png"),
                    help="filled reference with a small element (text) inside a fill")
    ap.add_argument("--bg-fill", default="49,49,49")
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

    # vacuous agreement: blank vs blank passes AND is flagged vacuous --
    # the flag is what keeps an empty PASS honest in gate_verdicts.json.
    im0 = Image.open(a.ref)
    blank = np.zeros((im0.size[1], im0.size[0], 4))
    blank[:, :, :3] = bg
    blank[:, :, 3] = 255
    blankp = os.path.join(tmpdir, "blank_vacuous.png")
    save(blank, blankp)
    res = po.evaluate(blankp, blankp, bg=bg, inset=a.inset, allow_missing_time=True)
    vac_ok = res["pass"] and res["report"].get("vacuous") == 1
    rows.append(("ok_empty_both_vacuous", "pass", "pass" if res["pass"] else "fail",
                 vac_ok, "vacuous=%s" % res["report"].get("vacuous")))
    if not vac_ok:
        failures.append("ok_empty_both_vacuous")

    # vacuous floor boundary: a sub-floor miss passes vacuous (the
    # documented hole -- <200 ink px is 0.08% of a 500x500 frame), a
    # super-floor miss must fail the ink checks.
    for name, box, expect in (("vacuous_subfloor_miss_ok", (10, 10, 20, 20), "pass"),
                              ("vacuous_superfloor_miss_fail", (10, 10, 35, 35), "fail")):
        dot = blank.copy()
        x0, y0, x1, y1 = box
        dot[y0:y1, x0:x1, :3] = 200
        dotp = os.path.join(tmpdir, name + ".png")
        save(dot, dotp)
        res = po.evaluate(dotp, blankp, bg=bg, inset=a.inset, allow_missing_time=True)
        got = "pass" if res["pass"] else "fail"
        ok = got == expect
        rows.append((name, expect, got, ok, "vacuous=%s" % res["report"].get("vacuous")))
        if not ok:
            failures.append(name)

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

    # ------------------------------------------------------- fidelity tier
    # Tolerances are read from evaluate()'s own defaults, so this table cannot
    # drift from what the oracle actually asserts.
    import inspect
    dflt = {k: v.default for k, v in inspect.signature(po.evaluate).parameters.items()}
    TOL = {"backdrop_px_pct_over_tol": ("backdrop-px", 100.0 * dflt["backdrop_px_frac"]),
           "ink_hue_delta": ("ink-colour", dflt["ink_hue_tol"]),
           "ink_core_mean": ("ink-colour", dflt["ink_core_mean"]),
           "ink_core_p95": ("ink-colour", float(dflt["ink_core_p95"])),
           "registration_dx": ("registration", dflt["reg_tol"]),
           "registration_dy": ("registration", dflt["reg_tol"]),
           "frame_unexplained_pct": ("frame-diff", 100.0 * dflt["frame_max"]),
           "local_max": ("local-fidelity", dflt["local_tol"]),
           "ink_coverage_notch_pct": ("ink-coverage", 100.0 * dflt["notch_max"])}
    worst_ok = {k: (0.0, "-") for k in TOL}
    aa_seen = []
    aimed_vals = {}
    bg_fill = tuple(int(x) for x in a.bg_fill.split(","))
    for refp, rbg, inset, prefix, filled in ((a.ref, bg, a.inset, "s_", False),
                                             (a.ref_fill, bg_fill, 0, "f_", True)):
        for name, path, expect, must_fail, opts, aimed in build_fidelity(refp, tmpdir, rbg, prefix, filled):
            kw = dict(bg=rbg, inset=inset, bbox_axes="x", allow_missing_time=True)
            kw.update(opts)
            res = po.evaluate(refp, path, **kw)
            got = "pass" if res["pass"] else "fail"
            aa_seen.append((name, res))
            failed = {c["check"] for c in res["checks"] if not c["pass"]}
            detail = ", ".join(sorted(failed)) or "-"
            ok = got == expect
            if ok and must_fail and set(must_fail) - failed:
                ok = False
                detail += "  MISSING:%s" % ",".join(sorted(set(must_fail) - failed))
            rows.append((name, expect, got, ok, detail))
            if not ok:
                failures.append(name)
            if expect == "pass":
                for k in TOL:
                    v = abs(float(res["report"].get(k, 0.0)))
                    if v > worst_ok[k][0]:
                        worst_ok[k] = (v, name)
            if aimed:
                aimed_vals.setdefault(aimed[1], []).append((abs(float(res["report"].get(aimed[1], 0.0))), name))
    calib = []
    for k, (chk, tol) in TOL.items():
        mut = min(aimed_vals[k]) if k in aimed_vals else (None, "-")
        calib.append((chk, k, worst_ok[k][0], worst_ok[k][1], tol, mut[0], mut[1]))

    aa_ok = min((float(r["report"].get("aa_ratio", 1.0)), n) for n, r in aa_seen if n.split("_", 1)[1].startswith("ok_"))
    aa_bad = max((float(r["report"].get("aa_ratio", 1.0)), n) for n, r in aa_seen if "aliased" in n)
    calib_lower = [("anti-aliasing", "aa_ratio (lower bound)", aa_ok, dflt["aa_min"], aa_bad)]

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
    print("FIDELITY CALIBRATION  (a control above its tolerance, or a mutant below it, is the")
    print("only evidence that licenses moving a tolerance)")
    print("%-15s %-25s %10s %9s %10s  %s" % ("check", "metric", "worst-ok", "tolerance", "mutant", "mutant case"))
    for chk, k, wv, wn, tol, mv, mn in calib:
        bad = wv > tol or (mv is not None and mv <= tol)
        print("%-15s %-25s %10.3f %9.3f %10s  %s%s" % (chk, k, wv, tol, "-" if mv is None else "%.3f" % mv, mn,
                                                        "   **MISCALIBRATED**" if bad else ""))
        if bad:
            failures.append("calibration:" + k)
    for chk, k, (wv, wn), tol, (mv, mn) in calib_lower:
        bad = wv < tol or mv >= tol
        print("%-15s %-25s %10.3f %9.3f %10.3f  %s%s" % (chk, k, wv, tol, mv, mn, "   **MISCALIBRATED**" if bad else ""))
        if bad:
            failures.append("calibration:" + k)
    print()
    if failures:
        print("SELFTEST: FAIL -- %d case(s) behaved wrong: %s" % (len(failures), ", ".join(failures)))
        print("The oracle is not trustworthy. Fix the oracle before reading any renderer result.")
        sys.exit(1)
    print("SELFTEST: PASS -- oracle catches every mutant and tolerates legitimate AA phase.")


if __name__ == "__main__":
    main()
