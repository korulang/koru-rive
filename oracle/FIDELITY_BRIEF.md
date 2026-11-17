# FIDELITY_BRIEF — harden the pixel oracle into a fidelity-tier gate suite

Commission: make `oracle/pixel_oracle.py` (and `band.py` where it shares
the verdict path) assert what it currently only reports, so that visual
discrepancies between ours and the browser reference **cannot pass**.

## The defect being fixed

The asserted set verifies geometry and coverage — size, alpha, clear,
modal backdrop color, ink-bbox, ring, ink-mass, ref-gap, stale. Two
fidelity classes are computed but **reported, not asserted**:

- ink RMSE / ink-union proximity — ink can be the wrong *color* and pass
- backdrop RMSE — backdrop can disagree per-pixel and pass, because the
  asserted `backdrop` check compares the modal color to a caller-supplied
  `--bg`, not ours-vs-ref

Observed consequence: a render with a white backdrop against a black
reference can pass; ink shifted a few RGB units passes; small systematic
misalignment inside tolerance passes. The suite was built to prove
feature classes work — it was never built to certify fidelity. That is
the gap this brief closes.

## Requirements

1. **Per-pixel backdrop agreement** — ours vs ref on non-ink pixels,
   asserted with a calibrated tolerance. Not vs `--bg`: the reference is
   the ground truth.
2. **Ink color fidelity** — on pixels classified as ink on both sides,
   assert mean-abs / percentile RGB delta within tolerance. Catches
   "off by a little but visible."
3. **Full-frame diff budget** — total disagreeing-pixel fraction
   (both ink and backdrop) asserted, so no discrepancy class escapes
   between the specialized checks.
4. **Keep the iron law** — the module docstring's own warning: an oracle
   that cannot fail is worthless (the /tmp RMSE scripts it replaced could
   not fail). Every new asserted check MUST have a `selftest.py` mutant
   that fails it: color-shift mutant, backdrop-shift mutant,
   sub-threshold-offset mutant. If selftest can't prove the new check
   rejects, the check doesn't ship.
5. **Honest bar, not "perfect"** — browser rasterization has irreducible
   differences (AA phase, font hinting, gamma). Tolerances are calibrated
   so legitimate AA-phase renders still pass and deliberate mutants
   fail. The goal is: every remaining allowed difference is *named and
   bounded*, not zero.
6. **Re-run all 33 gallery gates** after landing. PASS verdicts flipping
   to FAIL is the expected, honest outcome — report the new verdict table
   as-is. Do NOT tune tolerances to make flips disappear; tune only with
   selftest evidence that the tolerance is miscalibrated.

## Files

- `oracle/pixel_oracle.py` — the asserted/reported split lives here
- `oracle/band.py` — FLOORS/UNUSABLE thresholds may need the new metrics
- `oracle/selftest.py` — mutant suite; extend, don't weaken
- `oracle/gallery.py` — GATES table verdicts refresh after re-run
- `STATE.md` — record the fidelity tier landing

## Deliverable

Tightened oracle + extended selftest (all mutants proven) + re-run gate
verdicts + STATE.md note. Receipt names every gate whose verdict changed
and why the tolerance is calibrated the way it is.

## What this is NOT

Not a renderer fix — do not touch `rive/`, `canvas/`, or drivers. The
oracle is the instrument; instrument first, then the fleet fixes renderers
against gates that can actually fail. A MISMATCH the new oracle catches is
the deliverable, not a problem to tune away.

## Sequencing

This lands BEFORE the DeepSeek eyeball audit
(`oracle/eyeball_package/`) runs — audit verdicts get triaged against a
hardened oracle, and every confirmed visual mismatch the metrics still
miss becomes a candidate new check. The oracle grows by audit.
