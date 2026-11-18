# Eyeball audit — readiness check and first vision pass

Date: 2026-11-17. Auditor: DeepSeek vision pass (this session).
Package: `oracle/eyeball_package/` (README contract, 33 gates, 33 pairs,
`verdicts_swe2_ascii.jsonl` as the non-visual baseline).

## Bottom line

The package is **executable as an audit, but was not quite unambiguous
enough to run cold**. Three points in the contract would have changed
verdicts, so they are resolved explicitly below and the missing
deliverable — `verdicts.jsonl` — is now produced (33 lines, validated).

The audit itself finds **12 MATCH / 5 MINOR / 16 MISMATCH / 0
UNREADABLE**. Every non-vacuous oracle FAIL is confirmed visually. No
oracle PASS hides a content MISMATCH; the only soft PASS is `kn_cl1`
(~12 % less white ink in the card text, judged MINOR).

Three calls differ from the ASCII baseline — `kn_clip`, `knm_clip`
(MATCH → MINOR) and `mesh` (MINOR → MISMATCH). Those are the cases the
ASCII pass explicitly marked low-confidence.

## What is solid

Checked mechanically against the package and the repo:

| property | result |
|---|---|
| `gates.json` entries | 33 |
| `images/pair_*.png` | 33, every gate's `pair` file exists |
| baseline verdict lines | 33, valid JSON, README schema |
| gate sets (package / repo verdicts / baseline) | identical |
| metric verdicts and `failed_checks` vs `../gate_verdicts.json` | identical, no drift |
| labels in every composite | `OURS` left, `REF (browser rive_canvas)` right |
| halves | native-resolution, 1:1, no resampling (except the native canvas size itself) |

The hard part of the contract — what to compare, how to name the
difference, what counts as MINOR vs MISMATCH — is clear for the 27
non-vacuous, adequately-sized gates. The pair images are self-contained;
no renderer or oracle run is needed to judge them.

## Gaps that change verdicts (resolved in this pass)

### 1. `vacuous` has no rule

Six gates carry `vacuous: true` in `gates.json` (`cin`, `iba`, `lwti`,
`deam`, `hff`, `dcpo`), but the README never mentions the field.
`UNREADABLE` means "image broken/blank/corrupt on either side", which is
not the same as a deliberately empty fixture.

Resolved rule, applied here:

- `vacuous` = no content to compare; judge what *is* visible.
- Both halves blank with the **same** frame colour → `MATCH`,
  `diff_kind: none`, note says vacuous.
- Both halves blank with a **different** frame colour → `MISMATCH`,
  `diff_kind: backdrop`, note says vacuous. A white-vs-dark frame is a
  visible whole-frame difference even with no ink.
- A pair too small to support any other judgement (`dcpo`, 64×64 per
  side) stays `MATCH` vacuously with low confidence, not `UNREADABLE`.

This reproduces the baseline's split (`cin`/`lwti`/`dcpo` MATCH,
`iba`/`deam`/`hff` backdrop MISMATCH), but now as a stated rule.

### 2. The text rule contradicts the layout rule

README says: "Small text may legitimately differ if font rasterization
differs — note it as `text` diff_kind rather than MISMATCH unless content
differs." But it also says MISMATCH includes "wrong layout". `cl2`'s
digit is the same glyph in the same cell, just ~10–15 px left of centre;
under the first rule that could be MINOR, under the second it is
MISMATCH. The baseline calls it MISMATCH, and visually it is a layout
error, not a font difference.

Resolved rule, applied here:

- **Rasterization only** (AA, hinting, stroke weight, sub-pixel phase) →
  `MINOR` with `diff_kind: edge-aa` or `text`.
- **Placement, content, scale** of text → `MISMATCH` with `diff_kind:
  text` or `transform`.
- Content replacement (`THREE` vs `text`, `knm_cl1` blobs) is always
  `MISMATCH` regardless of font.

### 3. "33 gates" is not 33 independent observations

33 gates, **26 unique composites**. Six composites are shared:

| composite | gates |
|---|---|
| `pair_clfp_item.png` | `clfp_item`, `kn_clfp_item` |
| `pair_clfp_hover.png` | `clfp_hover`, `kn_sm_input` |
| `pair_cl2_t10.png` | `cl2_t10`, `kn_cl2_t10` |
| `pair_clv.png` | `clv`, `kn_clv`, `knm_clv` |
| `pair_iba.png` | `iba`, `hff` |
| `pair_kn_clip.png` | `kn_clip`, `knm_clip` |

This is not a renderer bug: the underlying ours files really are
byte-identical across those arms (documented in `STATE.md` for
`kn_clip`/`knm_clip`). But the audit must still emit one line per gate
per the schema. The notes name the shared composite, and triage should
count the composite once. The 16 MISMATCH calls include 4 exact
duplicates (`clfp_item`/`kn_clfp_item`, `clfp_hover`/`kn_sm_input`,
`cl2_t10`/`kn_cl2_t10`, `iba`/`hff`), so the independent MISMATCH count
is 12 composites, not 16. (`cl2` and `kn_cl2` are separate composites
but show the same digit-placement defect.)

## Package hygiene (not verdict-changing)

- **`pair_dcpo.png` is 136×82** — 64×64 content per side. It cannot
  support more than "both blank". Fine as a vacuous gate, but it should
  not be cited as visual evidence.
- **`extras/` is only documented in RUNBOOK**, not README. README's
  "images/ (33 total)" scope is clear enough, but a model handed the
  package root sees 38 `pair_*.png` files.
- **No output validator.** The README pins the schema but nothing checks
  33 lines / enums / one-line-per-gate. Added as
  `validate_verdicts.py`.
- **Baseline is not ground truth.** `verdicts_swe2_ascii.jsonl` has
  internal inconsistencies (`kn_clip`/`knm_clip` are `MATCH` but with
  `diff_kind: edge-aa`; `kn_cl1` is `MINOR` with low confidence). Diffing
  against it is useful; treating it as labels is not.
- **No per-gate expected-defect column.** `failed_checks` is the cue, and
  it is sufficient for the hard gates, but `dsm`'s scale mismatch and the
  vacuous backdrop classes are not stated as the *expected* visual
  finding.

## Vision verdicts

`verdicts.jsonl` — 33 lines, package order, README schema, validated by
`validate_verdicts.py` (PASS; 26 unique composites reported).

| gate | oracle | ASCII | vision | delta |
|---|---|---|---|---|
| hw | PASS | MATCH | MATCH | |
| cdo | PASS | MATCH | MATCH | |
| dsm | FAIL | MISMATCH | MISMATCH | |
| dsm_row | PASS | MATCH | MATCH | |
| clfp | PASS | MATCH | MATCH | |
| clfp_item | FAIL | MISMATCH | MISMATCH | |
| cl1_item | FAIL | MISMATCH | MISMATCH | |
| cl1_main | PASS | MATCH | MATCH | |
| clv | PASS | MATCH | MATCH | |
| cl2 | FAIL | MISMATCH | MISMATCH | |
| cl2_t10 | FAIL | MISMATCH | MISMATCH | |
| clfp_hover | FAIL | MISMATCH | MISMATCH | |
| kn_sm_input | FAIL | MISMATCH | MISMATCH | |
| kn_clfp_item | FAIL | MISMATCH | MISMATCH | |
| kn_cl2_t10 | FAIL | MISMATCH | MISMATCH | |
| clip | PASS | MATCH | MATCH | |
| cin | PASS | MATCH | MATCH | |
| iba | FAIL | MISMATCH | MISMATCH | |
| lwti | PASS | MATCH | MATCH | |
| deam | FAIL | MISMATCH | MISMATCH | |
| hff | FAIL | MISMATCH | MISMATCH | |
| dcpo | PASS | MATCH | MATCH | |
| kn_cl2 | FAIL | MISMATCH | MISMATCH | |
| kn_hw | FAIL | MINOR | MINOR | |
| kn_cl1 | PASS | MINOR | MINOR | |
| kn_clv | PASS | MATCH | MATCH | |
| kn_clip | FAIL | MATCH | MINOR | **MATCH → MINOR** |
| knm_cl2 | FAIL | MISMATCH | MISMATCH | |
| knm_cl1 | FAIL | MISMATCH | MISMATCH | |
| knm_clv | PASS | MATCH | MATCH | |
| knm_clip | FAIL | MATCH | MINOR | **MATCH → MINOR** |
| knm_hw | FAIL | MINOR | MINOR | |
| mesh | FAIL | MINOR | MISMATCH | **MINOR → MISMATCH** |

### Defect clusters (triage order)

Grouping the MISMATCH/MINOR lines by what would fix them:

| cluster | gates | likely one fix |
|---|---|---|
| card-item text placement (`0` at top-left) | `clfp_item`, `clfp_hover`, `kn_sm_input`, `kn_clfp_item` | item text anchor/transform |
| grid-cell digit placement (~10–15 px left) | `cl2`, `cl2_t10`, `kn_cl2`, `kn_cl2_t10` | cell text centring |
| Metal text path | `knm_cl1`, `knm_cl2` | text quad/atlas path: blobs / lost glyphs |
| wrong row content | `cl1_item` | VM-bound row string (`THREE` vs `text`) |
| render scale | `dsm` | ours 100×40 vs ref 250×100 |
| AA / stroke coverage | `kn_hw`, `knm_hw`, `kn_clip`, `knm_clip`, `kn_cl1` | edge AA / coverage |
| stroke continuity | `mesh` | dashed wave (~41 % ink) |
| vacuous backdrop only | `iba`, `deam`, `hff` | fixture/compositing policy, not content |

The two text-placement clusters account for 8 of the 16 MISMATCHes with
two fixes, which is the cheapest path to moving the gate table.

## The three disagreements, and why

- **`kn_clip` / `knm_clip` — MINOR, not MATCH.** At 1:1 the disc edge is
  a visible staircase against a smoothly anti-aliased reference. The
  oracle's `anti-aliasing` FAIL is correct; the ASCII pass marked these
  low confidence and could not resolve the edge. This is an AA-quality
  MINOR, not a content mismatch. (The two composites are byte-identical;
  it is one defect seen through two gates.)
- **`mesh` — MISMATCH, not MINOR.** The wave is not merely thinner: it
  has missing segments, a dashed/dotted stroke where the reference is
  continuous, at ~41 % of the reference ink mass. A viewer sees a broken
  line. The oracle's `ink-mass` / `coverage-gap` / `ink-coverage` FAILs
  are catching a real visual break, not an AA fringe.

### What the pass confirms

- All 15 baseline MISMATCHes reproduce. The worst are `knm_cl1` (text
  rendered as white blobs), `cl1_item` (`THREE` vs `text`), `dsm`
  (2.5× scale), `cl2`/`kn_cl2` (all digits displaced left), `knm_cl2`
  (digits partly lost as well as displaced),
  `clfp_item`/`clfp_hover`/`kn_sm_input`/`kn_clfp_item` (`0` at the
  card's top-left instead of centre), and the backdrop-only
  `iba`/`deam`/`hff`.
- All 13 oracle-PASS gates hold visually: 12 are MATCH, and `kn_cl1` is
  a MINOR text-weight residual. No oracle PASS hides a missing shape,
  wrong color, wrong layout, or garbage region.
- The hardened oracle's AA check is doing real work: the two clip gates
  are visibly aliased and the ASCII baseline missed that.
- The 139-px `kn_hw` notch is real but not a content change: MINOR
  edge-aa is the right human verdict.

## Triage for the tightening pass

1. **No new oracle check is demanded by a PASS-hidden MISMATCH.** The
   hardened tier already catches the confirmed defects via `frame-diff`,
   `local-fidelity`, `ink-coverage`, `anti-aliasing`, and `ink-mass`.
   This audit is a calibration pass, not a source of new checks.
2. **The vacuous backdrop class needs a decision, not a new check.**
   `iba`/`deam`/`hff` differ only in frame colour because the fixtures
   are oracle-limitation classes (1×1 PNG, VM-data, hosted font 404).
   Decide whether "ours clear" vs "ref opaque backdrop" is a harness
   compositing policy or a renderer defect before promoting these to
   bug reports. They are not content mismatches.
3. **`mesh` is the strongest candidate for a dedicated check** if
   `ink-mass` alone is too blunt: a stroke-continuity / gap-count check
   would name the dashed-stroke class directly. It is already FAIL, so
   this is prioritisation, not a hole.
4. **Do not add a check for `kn_cl1`.** ~12 % text ink delta with
   identical strings and layout is below the actionable bar; a check
   tuned to it would risk rejecting legitimate font rasterisation.
5. **Carry the duplicate map into `gallery.py`/triage.** Counting the
   four `0`-placement gates (`clfp_item`, `clfp_hover`, `kn_clfp_item`,
   `kn_sm_input`) as four independent confirmations overstates the
   evidence 2×: they are two byte-identical composites.

## Reproduce

```sh
# contract check (schema, completeness, duplicate-composite map)
python3 oracle/eyeball_package/validate_verdicts.py

# oracle verdicts feeding the package
python3 oracle/run_gates.py
```

The audit itself is human/vision judgement over
`oracle/eyeball_package/images/pair_*.png`; the package is self-contained
and needs no renderer to reproduce the pairs.

## Post-fix status (2026-11-18)

This audit was run against the pre-fix pairs; the verdicts above are the
snapshot that motivated the fix, not the current gate table. Two
text-placement defects were fixed in `rive/index.kz`:

- `textDrawPath` now honours `Text.alignValue` / `sizing` / `width` /
  `height` (fixed-width centred text, `cl2`'s ~19 px left digit offset);
- `effectiveWorld` no longer bakes the artboard `(pad - origin)`
  translation that `collectOps` never emits (the `clfp_item` `0` at the
  card's top-left).

`render_clfp_item_hover.k` now renders frame 8, the pose the browser
hover reference captures. Eight gates flipped to PASS: `cl2`, `cl2_t10`,
`clfp_item`, `clfp_hover`, `kn_clfp_item`, `kn_sm_input`, `kn_cl2`,
`kn_cl2_t10`; the full gate table is **21 PASS / 12 FAIL**. `cl1_item`
still fails on its `THREE` vs `text` VM-bound content, so the card-item
text-placement cluster is closed but the row-content cluster is not.
The `knm_*` gates still carry stale Metal artifacts.

**Follow-up (2026-11-18):** the seam instrumentation slice on
`kn_clip` found the binary native clip mask (`mid=0`, AA `0/394`) and
drove the fractional-coverage fix in the native canvas (4×4 supersampled
mask, coverage multiplied into the fill alpha). `kn_clip` and `knm_clip`
now **PASS** (AA `298/394`, ratio `0.76`, frame-diff `0.000%`); the full
table is **23 PASS / 10 FAIL**. The audit's `MINOR edge-aa` calls on the
two clip gates were correct: the gap was real, and it was the clip mask
rather than the path. See `oracle/INSTRUMENTATION.md` and
`oracle/first_divergence_kn_clip.md`.

**Further follow-up (2026-11-18):** the remaining instrumentation slices
closed three more audit findings. `dsm` was a stale probe (`ab: 9` at
1:1 instead of the row at 2.5×), not a renderer scale bug; `kn_hw`'s
glyph-edge notches were the 2×2 fill sampler and are fixed by 4×4
supersampling; `cl1_item` was the first-instance VM fallback, replaced
by template text unless a row scope or explicit `vm.bind` is active.
Full gate table: **26 PASS / 7 FAIL**. Remaining: `iba`/`deam`/`hff`
vacuous backdrops, `knm_cl1`/`knm_cl2`/`knm_hw` Metal text/AA, and
`mesh` (NOTE, dashed stroke).
