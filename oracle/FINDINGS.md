# Multi-oracle results (component_list_follow_path, Main, tick 1)

## Method
Three *independent renderers*, not versions of one:
- Rive Canvas2D in headless Chrome 2.37.0
- Rive WebGL2 in headless Chrome 2.37.0 (SwiftShader)
- Rive Canvas2D in node (node-canvas) 2.39.0  <- the corpus in /tmp/rive_oracle

Deterministic time: requestAnimationFrame and performance.now are driven
by the harness, so `tick` = exact number of 1/30 s steps.

## Cross-sections (px coverage, perpendicular to the stroke)
| renderer | circle-left | circle-top | wave-apex |
|---|---|---|---|
| chrome canvas2d 2.37 | 1.00 | 1.00 | 1.00 |
| chrome webgl2  2.37 | 1.00 | 1.00 | 0.98 |
| node canvas2d  2.39 | 1.00 | 1.00 | **1.50** |
| ours | 1.01 | 1.01 | 0.96 |

## Pairwise at tick 1
| pair | ink-mass | worst-tile | ref-gap |
|---|---|---|---|
| chrome-canvas vs chrome-webgl | 0.99 | 0.95 | 0.0% |
| chrome-canvas vs ours | 0.99 | 0.95 | 0.0% |
| chrome-webgl vs ours | 0.99 | 0.96 | 0.0% |
| node-2.39 vs ours | 0.84 | 0.71 | 0.0% |

## Conclusions
1. The node-canvas reference is an OUTLIER at the wave apex (1.50 vs 1.00/0.98).
   Every reference image in /tmp/rive_oracle was produced by it. Every pixel
   conclusion drawn from those images compared against an artifact.
2. Ours matches both browser backends within 1% on mass, tile and placement.
   There is NO stroke-weight defect.
3. Backdrop colour is the ONE real defect: all three references agree on
   #313131 (49), ours renders #404040 (64).
4. Tick 4 is not a usable comparison point: the two browser backends disagree
   with each other by 16.8% of ink there. The earlier "17.2% missing items"
   claim is unsupported.
5. The contour-truncation fix stands: it was verified at the ops level
   (23 -> 27 ops, backdrop covers 100% of frame, ring 12/12), independent of
   any raster reference.

## Resolution
The only real defect was colour management in Oshun's path rasterizer
(`canvas/index.macos.kz`, `rasterizePath`). It built colours with
`CGColorCreateGenericRGB` — a **GenericRGB (gamma 1.8)** colour — and then drew
into a **DeviceRGB** bitmap context, so CoreGraphics converted every value:

    #313131 = 49/255 = 0.1921 -> ^1.8 = 0.0513 -> sRGB encode = 0.2511 -> 64

i.e. exactly the observed #404040, with white (1.0) unchanged. Fixed by
building the colour in the context's own space with `CGColorCreate(cs, ...)`.

After the fix, against BOTH independent backends, every check passes:

    backdrop 49 (dist 0) | ink-mass 0.99 / 1.00 | tile-mass 0.95 / 0.96
    ref-gap 0.0% | ink-bbox delta 0 | ring 12/12 | size/alpha ok

## Follow-ups
- oracle/render_ref.mjs (node-canvas) is marked OUTLIER. Use
  oracle/render_browser.mjs (headless Chrome, Canvas2D or WebGL2).
- Tick 4 is not a valid comparison point yet: the two browser backends
  disagree with each other by 16.8% of ink there. Resolve that before
  judging any late-tick behaviour.
- The gallery card render (gallery_pick_rive) was diagnosed from the node
  outlier; re-check it against a browser reference.

## Round 2: band criterion, no hand-picked thresholds

`oracle/band.py` replaces hand-tuned tolerances. It takes two INDEPENDENT
oracles (A, B) plus ours and requires only:

    d(A, ours) <= max(1.25 * d(A, B), floor)
    d(B, ours) <= max(1.25 * d(B, A), floor)

If A and B disagree beyond a usable limit, the script refuses to judge
(exit 2) rather than inventing a verdict.

| tick | metric | band(A,B) | A-vs-ours | B-vs-ours | limit | |
|---|---|---|---|---|---|---|
| 1 | coverage_gap | 0.93 | 0.98 | 0.16 | 2.00 | pass |
| 1 | mass_dev | 0.01 | 0.01 | 0.00 | 0.02 | pass |
| 1 | pixdiff | 0.67 | 0.66 | 0.04 | 2.00 | pass |
| 1 | mean_abs | 0.28 | 0.26 | 0.07 | 1.00 | pass |
| 4 | mass_dev | 0.01 | 0.01 | 0.01 | 0.02 | pass |
| 4 | pixdiff | 1.01 | 0.64 | 0.69 | 2.00 | pass |
| 4 | mean_abs | 0.83 | 0.26 | 0.70 | 1.03 | pass |
| 4 | coverage_gap | **13.91** | 0.89 | 13.31 | - | ORACLES DISAGREE |

Tick 1: PASS on every metric. Tick 4: three of four metrics pass with margin;
`coverage_gap` is unusable there because Canvas2D and WebGL2 differ from *each
other* by 13.9% (they agree to 0.93% at tick 1). That is an oracle AA-profile
difference, not a defect in our renderer -- ours is 0.89% from Canvas2D, i.e.
closer to one oracle than the two oracles are to each other.

Also fixed this round: `coverage-gap` is now symmetric and blur-based. The
previous one-sided binary mask charged a sub-pixel AA difference as "missing
content" and produced two false alarms.

## Round 3: six-tick sweep + card path

Limits per metric = max(1.25 * oracle-vs-oracle disagreement, floor). A metric
whose two oracles disagree beyond the usable limit is EXCLUDED with a note
rather than vetoing the verdict; the tool refuses only if fewer than 2 metrics
survive.

| tick | mass_dev (limit) | pixdiff (limit) | mean_abs (limit) | coverage_gap | verdict |
|---|---|---|---|---|---|
| 1 | 0.01 (0.02) | 0.66 (2.00) | 0.26 (1.00) | 0.98 vs band 0.93 | PASS |
| 2 | 0.01 (0.02) | 0.64 (2.00) | 0.25 (1.00) | 0.98 vs band 1.88 | PASS |
| 3 | 0.01 (0.02) | 0.63 (2.00) | 0.26 (1.00) | excluded (oracles 7.97) | PASS |
| 4 | 0.01 (0.02) | 0.64 (2.00) | 0.26 (1.03) | excluded (oracles 13.91) | PASS |
| 5 | 0.02 (0.03) | 0.66 (2.00) | 0.26 (1.12) | excluded (oracles 17.83) | PASS |
| 6 | 0.00 (0.02) | 0.63 (2.00) | 0.25 (1.16) | excluded (oracles 21.32) | PASS |

Two things to read off this table:

1. Our distance to Canvas2D is FLAT across the whole animation (pixdiff
   0.63-0.66, mean_abs 0.25-0.26). No pose-dependent defect.
2. The oracle-vs-oracle disagreement GROWS with tick (0.93 -> 21.32). The
   degradation is between Rive's own Canvas2D and WebGL2 backends as strokes
   become more diagonal (AA profile), not in our renderer.

Card path (components/rive_card.kz: 320x320, artboard scaled by 320/500):
| metric | band(A,B) | A-vs-ours | B-vs-ours | limit |
|---|---|---|---|---|
| coverage_gap | 1.79 | 1.91 | 0.20 | 2.24 |
| mass_dev | 0.00 | 0.01 | 0.01 | 0.02 |
| pixdiff | 0.98 | 0.88 | 0.11 | 2.00 |
| mean_abs | 0.40 | 0.36 | 0.10 | 1.00 |
PASS. Backdrop 49 with 0 magenta surviving the clear.

## Round 4: regression coverage

`hello_world.riv` (artboard "New Artboard", no state machine, static):
| metric | band(A,B) | A-vs-ours | B-vs-ours | limit |
|---|---|---|---|---|
| coverage_gap | 0.00 | 0.07 | 0.07 | 2.00 |
| mass_dev | 0.00 | 0.01 | 0.01 | 0.02 |
| pixdiff | 0.00 | 0.29 | 0.29 | 2.00 |
| mean_abs | 0.00 | 0.08 | 0.08 | 1.00 |
PASS. ink-bbox exact, ink-mass 1.01, backdrop 49. The colour-management fix is
therefore not fixture-specific: Canvas2D and WebGL2 agree identically here and
we sit 0.07% from both.

## Open anomaly: component_list_default_state_machine.riv

Artboards: Main (idx 9, 200x200), Row (idx 20). State machine: "Main Machine".

The Rive oracle (both Canvas2D and WebGL2, headless Chrome) draws NOTHING for
this fixture at ticks 1, 5, 10 and 30 -- alpha 0 across the whole frame. Our
renderer emits 10 ops and paints ~6000 px of rgb(87,165,224).

This is the opposite direction to every earlier alarm: we draw content where
Rive draws none. It is NOT judgeable by the band (both oracles are blank, so
the band is 0), and it is NOT caused by the colour or contour fixes.

Most likely explanation to test next: the artboard's component list binds to a
ViewModel, and a default ViewModel instance is not being created/bound in the
browser harness. Either way it needs a ViewModel probe before it can be called
a defect in either direction.

### Refinement: what the anomaly actually is

The golden settles the direction:

    section 1 (Main):  30 frames,  0 drawPath   <- draws nothing, ever
    section 2 (Row):   60 frames, 61 drawPath   <- colour ff57a5e0

Our render of Main emits ~6000 px of rgb(87,165,224) = **#57A5E0**, i.e. the
Row artboard's colour.

So for this fixture we are drawing component-list ROW content from the MAIN
artboard, where both the rive-cpp recorder (0 draws in every frame) and the
browser (blank at ticks 1/5/10/30) draw nothing. This is the opposite sign to
the original hypothesis for this project ("our component list emits too
little"): here we emit too much.

Two independent sources agree on "nothing"; ours disagrees. That makes it a
genuine over-draw lead, not a metric artifact.

Caveat before calling it a defect: Rive may be suppressing rows because no
ViewModel instance is bound, in which case this becomes "we instantiate rows
without a data source". That needs a ViewModel probe -- binding
`defaultArtboardViewModel` in the browser harness -- before the verdict is
either "we over-draw" or "the oracle needs its data source".

## Round 5: the dsm anomaly resolved

### Why Rive's frame was blank
`component_list_default_state_machine.riv`:

    ViewModel "Main"  -> ViewModelInstance "Default" -> property "rows" (type: list)
    Artboard Main binds ViewModel 1 (prop 583 = 1)
    one ViewModelInstanceListItem in the file

The Rive runtime draws **nothing** until a ViewModel instance is bound. Binding
`r.viewModelByName('Main').instanceByName('Default')` and re-rendering makes it
draw exactly one row, colour **#57A5E0**, 4000 px at 200x200. So the blank frame
was a missing binding, not empty content.

### What our runtime does
It instantiates the file's `ViewModelInstanceListItem` unconditionally and draws
that row without any binding. Equivalent to implicitly binding the default
instance. Same colour, same one row, same y extent.

### The real defect this exposed: row WIDTH
| | bbox | size |
|---|---|---|
| Rive, in the component list (bound) | x[0..99] y[0..39] | **100 x 40** |
| ours, in the component list | x[0..149] y[0..39] | **150 x 40** |
| Rive, Row artboard standalone | x[0..149] y[80..119] | 150 x 40 |
| ours, Row artboard standalone | x[0..149] y[0..39] | 150 x 40 |

The Row artboard's own content is identical in both (150x40, 6000 px). But in a
component list, Rive lays the row out at the list's width (100), while our rows
pass draws it at the artboard's intrinsic width (150).

=> Our component-list row layout ignores the host frame width. That is a layout
   bug in the rows pass, not a raster defect, and it is the first defect in this
   project that points at our component-list layer emitting too MUCH.

## Round 6: the row-width defect, characterised

Scaling test (Rive, default ViewModel bound), same fixture, artboard Main 200x200:

| canvas | row bbox | row size |
|---|---|---|
| 200x200 | x[0..99] y[0..39] | 100x40 |
| 400x400 | x[0..199] y[0..79] | 200x80 |

The row scales exactly with the canvas, so this is a LAYOUT-SIZED row, not a
fixed clip and not a raster artifact. At scale 1 the row occupies 100x40 while
the row artboard's own content is 150x40.

Layout objects involved:
    obj[11] LayoutComponent 200x200 (list box), style obj[12]: flexDirection 0,
            all margins/paddings 0, gap 0, layoutWidth/HeightScaleType 1
    obj[13] ArtboardComponentList (parent obj[11])
    obj[20] Artboard "Row" 200x40, Node.x = 300, clip=false, viewModelId 0

The 100 is not explainable from the box (200 wide, zero padding) or from a
simple scale (row height stays 40, so the row is not uniformly scaled 0.5).
Deriving it needs Rive's component-list layout sizing rules, which this runtime
does not implement: our rows pass calls collectArtboardOps and draws the
embedded artboard 1:1 with no layout and no clip.

=> NOT a one-line fix. Our component-list rows pass needs Rive's layout sizing
   (item sizing within the list frame) before the width can be correct. Raster
   is ruled out: the Row artboard's own content is pixel-identical between the
   two implementations (150x40, 6000 px).

## Round 7: row-width defect FIXED

### Root cause
Not layout padding, not clipping, not a scale factor. The Row artboard's
rectangle carries a base width and an animation:

    obj[23] Rectangle     ParametricPath.width = 100   (base)
    obj[26] LinearAnimation duration 1
    obj[29] KeyFrameDouble value = 150                 (keyed on width)

Rive's component list lays items out but does NOT advance each item artboard's
own LinearAnimation, so rows draw at the BASE width 100. Our rows pass passed
the host frame straight into the embedded artboard, so the keyed value applied
and the row drew at 150.

### Fix
`collectOps`, component-list section: the embedded artboard is now collected at
the static pose (`collectArtboardOps(r, ai2, -1, ...)`), matching the observed
behaviour. Commented in place with the measurement that justifies it.

### Verification (component_list_default_state_machine, artboard Main, 200x200)
| | px | bbox | size |
|---|---|---|---|
| Rive, ViewModel bound | 4000 | x[0..99] y[0..39] | 100x40 |
| ours, before | 6000 | x[0..149] y[0..39] | 150x40 |
| ours, after | **4000** | **x[0..99] y[0..39]** | **100x40** |

Exact match, including pixel count.

Cross-check: our Row artboard rendered at the static pose is also 100x40 /
4000 px, confirming the base-pose rule rather than a lucky constant.

### Regression
component_list_follow_path: ops still 27, band PASS (4 metrics), standalone
oracle PASS. The change is inside the type-559 branch, so fixtures without a
component list are untouched.

## Round 8: component_list_1 -- diagnosed, not fixable without a layout engine

### Scale of the divergence
Rive (Canvas2D == WebGL2 exactly): 49,640 non-bg px, bbox x[0..199] y[0..289],
dominated by #18B900 (47,557 px).
Ours: 257 non-bg px, bbox x[0..36] y[5..19] -- only white glyph fragments.
Band check: mass_dev 0.96, coverage_gap 98.29% -> far outside.

### What the instrumentation showed
Added temporary prints to the rows pass in `collectOps`:

    DBGROWS list obj28 owning=24 abIdx=24
    DBGROWS item vmid=1
    DBGROWS matched artboard 43      (x24)

So the component-list loop matches every one of the 24 ViewModelInstanceListItems
and calls `collectArtboardOps(r, 43, ...)` for the Item artboard. But the whole
frame still emits only 9 draw ops (8 white + 1 backdrop) against 779 total ops:
the row artboard contributes paths and no draws.

### Why the row's paints are skipped
The green is `obj[46] SolidColor #18B900 -> obj[57] Fill`, and that Fill's parent
is **obj[45] LayoutComponent (178x55)** -- not a Shape.

We render paints attached to Shapes and to the Artboard, and never paints
attached to a LayoutComponent. `grep 409 rive/index.kz` shows only clip and
host-detection uses; there is no paint path for it. So a layout box's own
background is invisible, which is exactly what a data-bound list is built from.

### Why this is still blocked
Drawing those fills correctly also needs each layout box's computed POSITION.
The 24 rows would otherwise all be emitted at the origin and stack. That is the
same missing layout engine that blocked row sizing in round 6 -- `LayoutComponent`
width/height/styleId are decoded, but no layout is ever solved.

Debug prints removed; component_list_follow_path re-verified after removal
(ops 27, oracle PASS).

## Round 9: layout-box background fills implemented

### Change
`collectArtboardOps` now emits a fill for any Fill parented to a
LayoutComponent (409), which nothing previously did. Sizing honours
`LayoutSizingStyle.widthUnitsValue/heightUnitsValue` (607/608) on the
component's 420 style child: **3 = fill the parent box**.

### Result on component_list_1
| | green px | bbox |
|---|---|---|
| Rive | 47,557 | x[0..199] y[0..289] |
| ours, before | 0 | - |
| ours, after | 9,761 | x[0..199] **y[0..49]** |

The single box measures **200x50**, exactly the row size Rive uses -- the
"units 3 = fill parent" reading is confirmed by the pixel result (base was
178x55).

### What is still wrong, precisely
All 24 rows land on the same 200x50 box because:
1. no vertical stacking is applied (each row drawn at the origin), and
2. the ITEM COUNT is wrong: the file carries 24 ViewModelInstanceListItem
   objects, while Rive draws about 6 rows (green spans y 0..289 at 50 per row).

(2) means the file's list items are NOT the bound instance's list. Our rows pass
draws every 427 object in the file; Rive draws the list of the bound ViewModel
instance. For component_list_default_state_machine the two coincide (1 item), so
it passed; for component_list_1 they diverge 24 vs ~6.

Stacking was deliberately NOT added: stacking 24 wrong-count rows would over-draw
by 4x and move the picture further from Rive. The item source must be fixed
first.

### Regressions: none
- component_list_follow_path: ops 27, oracle PASS
- hello_world: band PASS (4 metrics)
- component_list_default_state_machine: row still exactly 4000 px, x[0..99] y[0..39]

## Harness verification (the gate before any renderer claim)

`python3 oracle/verify_harness.py` -- one command, every property, each with a
negative control. Current state: **8/8 PASS, verdict "harness trustworthy"**.

| # | property | how it is proven | control |
|---|---|---|---|
| 1 | renderer runs | a reference renders at all | - |
| 2 | version pin | `RIVE_EXPECT=9.9.9` is REFUSED, exit 4 | negative |
| 3 | blank guard | unbound dsm render is REJECTED, exit 3, no file written | negative |
| 4 | determinism | same render twice is byte-identical | negative (would catch stale/duplicate) |
| 5 | cross-backend | Canvas2D vs WebGL2 within their own band | positive |
| 6 | pairing | a `_t2` input against `_t1` oracles is REFUSED, exit 2 | negative |
| 7 | check selftest | 19 mutants, each caught by its named check | positive+negative |
| 8 | verdict selftest | band.py passes, fails and refuses on the right inputs | positive+negative |

Supporting tools:
    oracle/pixel_oracle.py     the checks (assertions + reported-only metrics)
    oracle/band.py             self-calibrating verdict; refuses when oracles disagree
    oracle/selftest.py         mutation suite for the checks
    oracle/band_selftest.py    mutation suite for the verdict logic
    oracle/render_browser.mjs  canonical reference: headless Chrome, Canvas2D or WebGL2,
                               deterministic tick clock, version-pinned, byte-level blank guard
    oracle/render_ref.mjs      node-canvas path, marked OUTLIER, not for use as the oracle
    oracle/verify_harness.py   the gate

### Documented residual limits (not defects; things the harness cannot know)
- `--inset` and `--ring` are per-fixture parameters chosen by hand. A wrong
  inset biases every metric; a wrong ring makes the ring check meaningless.
- The koru frame <-> reference tick mapping is empirical and differs per
  fixture (`2*(tick-1)` for clfp; frame 0 matched tick 1 for dsm). It is
  documented, not enforced.
- `band.py` FLOORS are hand-chosen, but they only ever LOOSEN the criterion;
  the oracle-vs-oracle band supplies the tolerance when the oracles agree
  closely, which is the case that matters.

---

## Eyeball audit — ASCII-instrumented pass (2026-11-17, SWE-2, no image input)

The DeepSeek vision audit could not run (budget). Substitute instrument:
`oracle/eyeball_package/verdicts_swe2_ascii.jsonl` — 33 verdicts produced by
rendering each gate's ours/ref pair to a 72-col hue/luminance ASCII grid
(`/tmp/fidelity_probe/ascii_gates.py`, regenerable), then numerically
spot-checking every disagreement candidate. Confidence is honestly low on
thin-stroke and AA-only differences the grid cannot resolve.

Result vs `gate_verdicts.json`:

- **No oracle PASS hides a visible MISMATCH.** 9 PASS→MATCH, 2 PASS→MINOR
  (`kn_hw`, `kn_cl1` — edge-coverage/text-row differences inside tolerance).
- **15 oracle FAILs confirmed MISMATCH** by eye-equivalent: dsm scale,
  the displaced "0"/"THREE"/digit-placement family (9 gates), cl1_item
  wrong string, knm_cl1 blob text, mesh thin strokes, iba/deam/hff
  white-vs-dark backdrop.
- **5 oracle FAILs show no visible difference** at this resolution:
  `cin`, `lwti`, `dcpo` are empty-vs-empty (ink checks fail vacuously —
  candidate for a VACUOUS verdict class, not FAIL), and `kn_clip`,
  `knm_clip` differ only in anti-aliasing (0 vs 394 blended px), which
  ASCII cannot resolve.
- `kn_sm_input`'s ours file is byte-identical to `clfp_hover`'s — the
  "native software" SM-input gate is the same render, not independent
  evidence (already suspected; now confirmed at artifact level).

Oracle-growth candidates from this pass: a vacuous/empty-frame verdict
class; an ink-coverage check that would have caught kn_hw's 139 px of
backdrop notches (it passed because blended-edge COUNT stayed ≥0.5×ref —
count, not coverage).


Both audit candidates landed as checks: `ink-coverage` (notch_max=3%;
worst legit control 2.54% on the node-canvas selftest ref, aimed mutant
9.18%) and the vacuous class (vacuous_px=200; cin/lwti/dcpo now PASS
vacuous, iba/deam/hff still FAIL on backdrop). kn_hw flipped PASS->FAIL
on ink-coverage -- the first gate the eyeball audit caused to change
verdict. Remaining named gap: softer-than-reference edges still
unasserted; vacuous floor 200 px could hide a sub-visible-content
mismatch (accepted: <200 px is below perceptual relevance).

Coverage-shape prototype (2026-11-18, arbiter-approved audit candidate):
solid-ink fraction (coverage>0.8 / coverage>0.15 within dilated union)
measured on all non-vacuous gates. Does NOT earn the asserted slot:
- knm_cl1 text-blob: delta +0.011 (ref 0.026, ours 0.037) -- the Metal
  blob is positional/morphological, not a coverage-shape defect; already
  caught by frame-diff + local-fidelity + ink-colour.
- The classes it does separate (mesh +0.83, knm_hw +0.33) are already
  asserted by ink-mass / ink-coverage / anti-aliasing.
- No demonstrated catch the existing checks miss -> not added. The
  only residual class it could uniquely name (same-mass distribution-
  only difference under 16 levels) is manufactured, not observed.

notch_max widened 3%->4% per arbiter ruling (worst legit control 2.54%,
headroom for subpixel phase; hole-class defects sit at 15-66%).
run_gates.py gained per-gate "opts" passthrough so ring/stale/clear/
alpha stay asserted-but-opt-in rather than deleted.

## Ruling: iba / deam / hff backdrop FAILs — RENDERER BUG (verb/raster layer)

Adjudicated 2026-11-18 per arbiter commission. The oracle's expected
backdrop is CORRECT — it equals the colour the .riv artboard itself
specifies:

| gate | .riv spec (oracle/dump) | ref backdrop | ours |
|---|---|---|---|
| iba  | full-frame fill `ff313131` | (49,49,49) opaque | 100% probe-clear white |
| deam | full-frame fill `ff282828` | (40,40,40) opaque | 100% probe-clear white |
| hff  | full-frame fill `ff313131` | (49,49,49) opaque | 100% probe-clear white |

First-divergence walk (iba, verified at op layer):
1. Scene/ops: **MATCH** — `opsdump_iba.k` emits the background fill:
   `OP k=8 style=1 color=ff313131` inside the artboard's path group,
   500x500 verts present. The command stream carries the spec.
2. Verb/raster: **DIVERGES** — framebuffer is 100% the probe's white
   clear; the emitted fill never reaches a pixel.
3. Oracle: expected bg = spec colour; not wrong-expected.

Missing surface: whatever realizes `style=1` fill ops for these
fixtures drops or misplaces the full-frame background — suspects:
fill realization gated on content ops, clip/transform state eating
the first path group, or the kind-11 image op aborting the frame
before/at the fill (iba is the in-band-image fixture; deam=VM-data,
hff=hosted-font — all three share "auxiliary asset" class, which is
the pattern worth checking first: does the fill emit *before* the
asset op in stream order, and does asset failure skip pending draws?).

deam/hff: same pixel signature + spec-verified colours; op-layer
walk not yet run for them (inferred same class, marked unverified
at that seam).

Fix is a separate commission (renderer side). Oracle stands as-is:
these three FAILs are real renderer deltas, correctly asserted.

## Correction: iba / deam / hff — stale gate artifacts, not a renderer bug (2026-11-18)

The ruling above was based on the committed `ours_iba_t1.bmp`,
`ours_deam_t1.bmp`, `ours_hff_t1.bmp`, all 100% probe-clear white.
Fresh renders with the current code disagree with that artifact:
`render_iba.k` → mean `(49,49,49)` (exactly the ref), `render_deam.k`
→ `(40,40,40)`, `render_hff.k` → `(49,49,49)`. After refreshing those
three artifacts, `iba`, `deam`, and `hff` **PASS** (backdrop,
backdrop-px, and the vacuous ink checks). The op-layer walk was correct:
the fill is emitted and realized.

The macOS clip trace (`KORU_TRACE_CLIP` on `index.macos.kz`) shows the
full-frame clip mask is present: 504×504, `inside=250000`, `mid=0`,
bbox `[2,2,501,501]` — so the clip was not eating the fill either. The
divergence was the **artifact**, not the renderer.

No renderer fix is needed. Discipline note: a first-divergence report
must name the artifact hash/mtime and be generated from a fresh render;
otherwise a stale `ours_*` file is indistinguishable from a verb/raster
bug. `oracle/trace_kn_clip.sh` already rebuilds its artifacts; the
iba/deam/hff probes should be run through the same freshness rule.

## Metal text seam (2026-11-18): counters fixed, AA remains font-raster residual

Glyph fills are forced evenodd so the Metal stencil-parity path subtracts
counters; the per-call EO path now renders at 4× and box-downsamples.
`knm_cl1`'s white blobs are gone (ink-mass 0.99, ink-coverage 0.12%,
frame-diff 0.002%); `knm_hw` ink-coverage falls to 2.65%. Both still fail
`anti-aliasing` (0.38/0.39 of ref blended edge px) and `ink-colour`: the
browser font AA/hinting spreads ink over ~2.5× more edge pixels than the
outline-glyph raster. That is a text-raster residual, not a path-fill
hole; 8× supersampling did not improve it (478 vs 489 blended px), so
more samples are not the lever. `knm_cl2`'s headless probe still dumps
white; its artifact is stale. The other model's in-progress MSAA batch
code was made to compile (setStoreAction arg type, print specifiers), but
the text gates use the per-call EO path, not the batch MSAA path.

## Provenance layer + vacuous floor boundary (2026-11-18)

Trigger: the iba/deam/hff ruling was correct about the images but the
images predated the bg-fill fix (d994bc9 confirmed: stale artifacts,
not renderer bugs). A verdict about code requires evidence produced
by that code.

**provenance.py** — `stamp GATE --driver PATH` writes
`images/<ours>.prov.json` {driver, commit, ts}; `check`/run_gates
classify every ours asset fresh|stale|unprovenanced. Staleness =
mtime heuristic: any dep newer than the render flags it. Deps =
prov.driver + render_deps.json "shared" (kr/, ../oshun/canvas/).
All 33 current assets are UNPROVENANCED — none were stamped at render
time; retroactive stamping would repeat the original sin. Workflow:
render -> stamp -> freeze. mtime caveat documented: checkout can
refresh it, so stale means "re-render before trusting", not "wrong".

**vacuous_px=200 floor calibration** — boundary mutants added to
selftest: sub-floor miss (100px dot vs blank) passes vacuous=1
(documented hole: <200 ink px = 0.08% of frame can be missed
silently); super-floor miss (625px dot) fails all ink checks. Floor
placement: largest vacuous cluster 71px (cin), smallest real 853px
(mesh); 200 sits at 0.36x/4.3x margins, near the geometric mean 247.
Hole is bounded and now mutant-pinned rather than prose-pinned.

**Gate table moved to 31 PASS / 2 FAIL** — not by oracle change:
parallel renderer commits landed (bg-fill refresh d994bc9, Metal
evenodd text a0f159b + 48deacc supersampling). Remaining FAILs:
knm_cl2 (frame-diff, anti-aliasing, local-fidelity) and mesh
(ink-mass, coverage-gap, ink-coverage, anti-aliasing).

## Metal text seam closed (2026-11-18): straight-alpha composite was the colour bug

`knm_cl1`, `knm_cl2`, `knm_hw` now PASS. Chain:
1. Glyph fills forced evenodd -> stencil parity subtracts counters.
2. Per-call Metal fill (both nonzero and EO) renders at 4× and
   box-downsamples; `metalBatchFlush` disabled while debugging.
3. The colour/AA failure was the composite: it passed the
   premultiplied readback (`rr/16`) *and* an alpha to `blendInto`,
   which expects straight RGBA and multiplies by alpha — a
   double-multiply at every AA edge. Using `col.r/g/b` with `ai` fixed
   ink-colour (0.0003/0.0000/0.0010), AA (0.88/0.84/0.88) and
   local-fidelity (2.4/0.2/2.2).
4. `window.close` flushes the pending batch; `knm_cl2` would otherwise
   dump white. The batch optimisation remains disabled
   (`g_metal_batch=false`, named delta), its command buffer erroring.
A 3x3 box / 1px cross blur was tested and rejected: it raised AA but
broke local-fidelity (15-28) and ink-colour (0.02-0.05). Full table:
**32 PASS / 1 FAIL** (only `mesh` NOTE).

## Never-firing check review: ring / stale / clear / alpha (2026-11-18)

Reviewed per arbiter loop order. Verdicts:

- **alpha** — NOT dead: self-activates whenever either side carries
  non-opaque alpha post-composite (pixel_oracle.py:328). All comp gates
  composite to opaque so it reports "alpha vacuous"; NOCOMP gates with
  a genuinely transparent ref would fire it today. Nothing to wire.
- **stale** — WIRED: cl2_t10 opts.prev=ours_cl2_t1.bmp,
  kn_cl2_t10 opts.prev=kn_cl2.bmp. Real tick pairs; asserts the t10
  frame actually differs from t1 (frozen-animation catch). Both PASS
  on current renders. run_gates resolves bare prev filenames against
  oracle/images/. Mutant already existed: bad_stale_duplicate.
- **clear** — WIRED on the three adjudicated gates only: iba, deam,
  hff get opts.clear=[255,255,255] (their probes clear white;
  artboards paint full-frame bg so any surviving white = dropped
  paint, the exact class that produced the stale-evidence FAILs).
  Other zero-white gates not wired: gate->driver mapping is itself
  unprovenanced, so clear colour per gate is unverifiable until
  provenance covers them. New mutants: bad_clear_survives (must
  fail), ok_clear_absent (must pass).
- **ring** — stays opt-in, documented: no current fixture has annulus
  content to assert angular-sector completeness against. Asserted
  surface kept; schema supports it via opts.ring when an oval/ring
  fixture lands.

Gate table: 32 PASS / 1 FAIL (knm_cl2 re-rendered + stamped fresh by
renderer lane; mesh remains the sole FAIL).

## Provenance backfill + mesh adjudication (2026-11-18)

classify() gained a git-anchored check: for in-repo deps, stale fires
when `git diff <prov.commit> HEAD` or `git status` shows dep changes —
immune to checkout-mtime noise. mtime still covers cross-repo deps
(../oshun/*).

Backfilled 30 prov sidecars (commit = artifact's last-touch commit,
driver unknown -> shared deps only; the 3 renderer-lane stamps left
untouched). Result: **fresh=3, stale=30** — all 30 flag on
`../oshun/canvas/index.koru-native.kz`, which carries UNCOMMITTED
renderer-lane edits newer than every backfilled render. Honest
reading: while canvas is dirty, no render predating the edit is
provably current. The 32/1 table is "as of render time"; expect
movement when the lane commits + re-renders.

**mesh adjudication** (sole FAIL, scratch render — gate asset
untouched, t47 owns the worklist): fresh `meshrender_clfp.k` output
on current tree FAILs 7 checks, worse than the committed artifact's
4. ours ink bbox = full frame (0,0,499,499) vs ref (24,89,471,452);
ink mass 6177 vs 1206 (5.12x); coverage-gap 82%; notch 63%;
local-fidelity 97.6 levels. The meshops->mesh.* path is over-filling:
ink everywhere the artboard should be backdrop. NOT stale-evidence —
reproduces on current master. Driver: meshrender_clfp.k (kr/rive:
meshops, component_list_follow_path.riv ab:18).

## Toolchain defect — koru backend const-flow crash on slice pointer+index for-capture

**Symptom:** `koruc run` fails in the compiler's own Zig backend
(`src/transform_pass_runner.zig`), not in emitted code:
`error: expected type '?*ast.Flow', found '*const *ast.Flow'`
`note: cast discards const qualifier` — walkOnce/walkAndTransformStages.

**Minimal repro shape (rive/index.kz annotateWorldBbox):**
```zig
for (recs, 0..) |*rec, ri| {   // pointer + index two-capture over []OpRec
    switch (rec.kind) { ... rec.wx0 = v; ... }
}
```
Compiles the module fine until this loop is added; backend walk dies.

**What does NOT trigger it:**
- `for (recs) |*rec|` — single pointer capture, no index (committed
  world-bbox version compiled clean).
- `for (recs, 0..) |rec, ri|` — by-value + index capture: WORKS.
  Mutations go through `recs[ri].field = x` indexed writes instead of
  `rec.field`.

**Workaround shipped (koru-rive-vm @ frustum-cull commit):** by-value
capture `|rec, ri|` + all writes via `recs[ri]`/`recs[pi]` indexing.
kind=-1 tombstone + compaction replaces any alloc'd side array (also
sidesteps a second latent issue: `alloc.alloc(...) catch return` +
`defer` inside the same fn did not isolate the crash — the for-capture
was the real trigger, verified by bisect).

**Owner:** ~/src/koru transform_pass_runner — the flow-node typer emits
`*const *ast.Flow` where `?*ast.Flow` is expected specifically for the
two-capture pointer form. Commissioned to t42 for a koru-side fix.

**CORRECTION 2026-11-18 (t42 investigation): PHANTOM — no koru defect.**
The quoted error is a static Zig type error inside
`src/transform_pass_runner.zig` itself; consumer `.kz` content cannot
produce it. It matches verbatim an UNCOMMITTED in-flight edit to that
file on the same day (collect-mode `c.current_flow = &node.flow`
yielding `*const *ast.Flow` vs `?*ast.Flow` in the walkOnce call tree).
Clean tree reproduces nothing: backend builds, `for (xs, 0..) |*x, i|`
compiles through the frontend. The bisect coincided with the broken
edit + backend-cache invalidation; the "workaround" correlated with
the file being fixed/reverted, not with the capture form.

**REAL adjacent defect found while reproducing (uncommissioned):**
the brace+capture form `for (xs, 0..) |*x, i| { ~steps }` is NOT Koru
syntax — `for` is `for(expr) ! each ... | done ...` chains only
(koru_std/control.kz). The brace form parses and shape-checks, then NO
transform consumes it: the emitter leaks the raw text verbatim into
output_emitted.zig (`for (xs, 0..) |*x, i| {` at module top level →
`error: expected type expression, found '{'`). Single-capture variants
fail differently (`for input is not captured`). Parser leniency bug —
should refuse loudly, not leak. Repro: /tmp/cf_try3.kz shape.

## FLAG — opsdump SIGABRT on layout_text_match.riv (exit 134)

Found by authored_parity 40-file batch (2026-11-18): ours_digest probe
crashes SIGABRT — "no op stream emitted". File:
rive-cpp/tests/unit_tests/assets/layout_text_match.riv. Not a decode
failure (open succeeds); crash is in the ops/emit path — likely text
layout measurement or TextStyle handling hitting an assert/unwrap.
Minimal repro pending: opsdump at name-resolved Main ab index.
Fix leg: isolate, then guard or implement the missing path.

## RESOLVED-ish — layout_text_match SIGABRT: glyph endPts > decoded points

Crash signature (opsdump_ltm.k repro, ab:5): `textDrawPath` contour walk
indexes `gp[ni]` where `ni` derives from `endPtsOfContours` — but
`glyfGlyph` decoded FEWER points than endPts claims. Concrete hits:
Text obj[11]/obj[19], char 'i' (gid 689): gp.len=16, cend=17, ni=16;
char ',' (gid 1501): gp.len=4, cend=5, ni=4. Pattern cend = gp.len+1
on specific gids only -> per-glyph defect, consistent with composite
glyphs (glyf type 10) mis-parsed as simple outlines, or endPts counting
points glyfGlyph drops. File: layout_text_match.riv — single artboard
obj[5], ~10 Text objects nested in LayoutComponents.

Guard added at the np access (index.kz ~4286): ni >= gp.len ->
LTMOOB stderr print + break. opsdump now completes: 286 ops, exit 0.
Proper fix = glyfGlyph composite-glyph path — renderer-owner leg.

## FIXED — composite-glyph endPts off-by-one (layout_text_match SIGABRT root cause)

glyfGlyph composite branch appended `base + ce + 1` to ends[] but ce is
already the child's 0-based last-point index — caller adds +1 again when
computing cend, double-counting -> cend = gp.len+1 -> contour walk OOB.
Fix: append `base + ce`. Verified: LTMOOB hits 10+ -> 0; opsdump
286 -> 21839 ops (composite glyphs now emit full outlines); exit 0.
Guard retained as loud defensive bound (never fires post-fix).
Known remaining TODO in same path: ARGS_ARE_XY_VALUES assumed —
point-matched component args (flags&2==0) would misplace, not crash.

## layout_text_match clip signature (class-5 evidence for t4f)

Ref dump: 2 clipPath records, each `verbs=5 pts=3` (rect-ish path)
wrapping ONE glyph drawPath inside the text-row sequence (~rows 3 and
7 of ~10). File census: ZERO ClippingShape objects, ZERO clip=true
props (only Artboard LayoutComponent.clip=false) — the clip is
IMPLICIT, not flag-driven. Candidates: per-LC overflow/clip on the
specific row's LayoutComponent, or text-bounds clipping when glyph
runs exceed cell width. Trigger condition unidentified — needs the
clip-condition decode leg. Draw/paint parity otherwise exact
(37/37 draws, colors identical).

## TOOLCHAIN BLOCKER (2026-11-18 ~23:00) — not decode timeout

db_health_tracker/hunter_x_demo 'artboard name not decoded' root cause
is NOT file size: ALL koruc probe builds now fail —
koru/koru_std/compiler.kz:1114 uses `for(...) |capture| { }` which the
installed koruc rejects (PARSE001). koru_std is committed-clean at
fa180ba48 -> installed koruc binary is STALE vs koru HEAD (needs
rebuild) or a concurrent session is mid-edit. Also: untracked
rive/rivgen_hello.kz (t4f riv2k output) independently breaks
import kr/rive builds (KORU022) — moved to /tmp/rivgen_hello.kz.bak.
Both must clear before parity probes compile again.

## db_health_tracker expansion miss — skip-condition analysis

Chain verified: obj[203] NestedArtboardLayout(artboardId=6->651) IS
inside artboard 180's subtree (203->202LC->184LC->183LC->182LC->180);
obj[690](artboardId=7->712) is inside 651's (690->688LC->678LC->676LC
->655LC->651). Expansion code (index.kz ~5645) requires
owningArtboard(instance)==abIdx — legal chain: emit 180 -> expand 203
-> recurse 651 -> expand 690 -> recurse 712. Depth=2 << guard 8.
All links type 452, artboardIds resolve to ordinals correctly.
So the skip is NOT type/owner/depth — remaining suspects: (a)
propU(197) field-type mismatch on one link (b) effectiveWorld
degenerate -> emits transform but empty subtree (c) expansion fires
but 712's content emits ~0 ops (PointsPath/stroke-path issue inside
target). NEXT PROBE: opsdump ab:180 with tracing, count collectOps
recursion or diff RIVE_NO_NESTED=1 op count — distinguishes
"never entered 712" from "entered but emitted nothing".

## hunter_x_demo clip census — ClippingShape(42) untraversed

Ref 130 clipPaths vs ours 1. Census: 80 ClippingShape objects
(79 parented to Shape, 1 to Node), ZERO clip=true props, 10
NestedArtboard instances (5 Leaf + 5 plain). Emit gap: our only clip
source is the ArtboardComponentList scroll clip — ClippingShape(42)
is never traversed. ~50 of 130 clips unaccounted by the 80 CS objects
— likely per-instance artboard-bounds clips or clips inside expanded
nested targets; secondary. For renderer owner: ClippingShape semantics
= clip path drawable masking siblings/parent contents (rive-cpp
clipping_shape.cpp) — needs traversal arm emitting clippush/clippop
(k=9/10) around the masked subtree.

## collapsing_elements underdraw — all-layout file, nested+SM compound

156 objects, 3 artboards, ZERO Shape/Path/Text drawables — every fill
(20) parents to LayoutComponent(17) or Artboard(3): all content is
layout-box paint (class-2 mechanism). 4 NestedArtboard instances in
main(ab1) reach ab26 (5 fills + 3 NestedStateMachine + nested
instances) and ab65 (14 fills). Heavy SM presence: 3 StateMachine +
6 NestedStateMachine on a 156-obj file — "collapsing" is SM-driven.
Missing 32 draws ranked: (1) nested targets expand but LC fills emit
degenerate/zero rects without the layout solver -> silent drop;
(2) NestedStateMachine state selects collapsed variant -> fewer
instances visible than ref frame-0. Discriminator: opsdump ab:1 with
RIVE_NO_NESTED=1 diff + NestedSM default-state inspect.

## collapsing_elements discriminator — SM-selection NOT the count cause

Nesting decoded: main(ab1) has 3 NestedArtboard instances (obj3/5/7,
ALL artboardId=1->ab26) each with NestedStateMachine child, all
parented to Solo(obj2) — Rive view-switcher picks one variant. ab26
mirrors: 3 instances (33/37/42, ALL artboardId=2->ab65) + NestedSM
each under LayoutComponents. CRITICAL: every variant points to the
SAME target — Solo/NestedSM selects WHICH instance shows, not WHAT
content. Draw count is therefore selection-invariant; the -32 is NOT
SM-state. Verdict: solver-blocked — ab65's 14 + ab26's 5 LC-fills
need computed rects; without the layout solver expanded targets emit
degenerate/zero-area fills -> silent drop. Named residual = class-2
(layout solver) confirmed; NestedSM/Solo gating remains unmodeled
and will surface later as an OVERDRAW class (we expand all variants,
ref shows one) once counts converge. Parked with evidence.

## Paint-default census (batch-2 retry, 6 paint-layer divergences)

All six files paint with SolidColor ONLY — zero gradients, zero
PaintImage, zero unbound paint types. The divergence is VALUE
resolution, not paint class. Dynamic-color machinery per file:
- component_stateful_vm_instance_2: ViewModelInstanceColor x2 —
  VM-bound color unbound on our side (ours 747474 default vs ref
  00ff12).
- listener_action_inputs: KeyFrameColor x2 + listener SM — keyframed
  color (ours 46a100 vs ref 9d0202).
- ik_anim_test / follow_path_path / scripted_path_effect_clip:
  LinearAnimation + KeyFrameDouble — color animated at frame 0; we
  emit the static/default prop, ref evaluates the timeline
  (ours ffffff/000000/003fff vs ref 40d3a5/747474/747474).
- additive_blendmode_test: blend-mode compositing (ours 00ff00 vs
  ref 6f00ff — additive blend not applied to paint color).
NAMED CLASS: color-source dynamics — VM-color binds + keyframed
color props + blend compositing, all evaluated at frame 0 by ref.
NOT the gradient class (class-3 unaffected); NOT unbound-paint-type.

## Vertex-delta specimens (batch-3 geometry divergences) — NOT tessellation

Per-file gold-vs-ours path-op counts on the 4 geometry divergences:
- trim.riv [work]: ref emits verbs=0 pts=0 EMPTY drawPath for the
  diverging drawable; ours emits ~14 path ops — TrimPath(47) never
  evaluated, we draw untrimmed geometry. Path-effect class.
- text_listener_simpler.riv: shared draws are VERTEX-EXACT — ours
  630 path-ops vs ref verbs=630 on the big glyph run; divergence is
  draw COUNT (ref 6 drawPaths incl. duplicated text pair vs ours 3
  groups) + ~10px text-width delta = text metrics/duplication, not
  flattening.
- scripted_listener_context.riv: ref bbox 85x91 vs ours 172x158
  (~2.02x uniform) — transform-scale class, vertex counts unmeasured
  (ref block extraction empty — needs digest-level pts).
- component_stateful_vm_instance.riv: ref (-10,-51,10,51) tall-thin
  vs ours (-41,-39.5,41,39.5) — aspect+scale transform delta, same
  caveat.
VERDICT for t4f: batch-3 geometry divergences are HETEROGENEOUS —
TrimPath eval, transform-scale eval, text metrics — NOT curve
tessellation specimens. The vertex-exact frontier needs specimens
from files whose divergence IS flattening (look to drawable-count
files with matching transforms, or craft a curve-heavy fixture).

## NEW SIGABRT — ik_over_distance_constraint.riv (batch-4)

opsdump exit 134 signal 6, no op stream — same class as
layout_text_match (now fixed). IKConstraint(81)/DistanceConstraint(82)
family file; isolate crashing object next leg. Also
light_switch.riv: RESOLVED FLAKE — file is a 319-byte stub; the
"AB idx=3844" output was impossible from it. Root cause: old
run_probe wrote SHARED ./a.out; parallel specimen compiles during
batch-4 overwrote it mid-run -> probe executed wrong binary. Fixed
upstream (unique binary paths per probe). True verdict: divergent
paint-layer — CORRECTED: not an order swap. Inspect shows paint
edges unambiguous (Fill9->Shape2 rect, Fill10->Shape5 ellipse,
Fill11->Artboard bg; SolidColor4 has NO static colorValue prop).
Ref resolves that slot ffac00, ours defaults 747474 -> color-VALUE
resolution gap = color-source-dynamics class (animated/default
color prop we don't evaluate), NOT a paint-assignment-order bug.
Fix site = colorValue/animation eval leg, not traversal order.

## Color-dynamics mechanism census (paint-divergent files)

Per-file mechanism feeding unresolved colorValue:
- KeyFrameColor tracks: advance_blend_mode(4), bindable_focus_tree_swap(6),
  custom_property_trigger(1), layout_order_pointer_test(4),
  listener_action_inputs(2), pause_nested_artboard(2).
- VM/bind-driven: component_stateful_vm_instance_2 (ViewModelInstanceColor x2);
  DataBindContext-heavy files (bindable_focus_tree_swap 11,
  color_passthrough 11, pause_nested_artboard 9, layout_order_pointer 8,
  data_binding_artboards 6) — bind-eval class.
- Missing static colorValue (default/interpolated): 0-5 SolidColors per
  file across most — light_switch=1, follow_path_path=1, ik_anim=0.
- kfdouble-only (numeric anims, likely opacity/transform NOT color):
  follow_path_path(19), ik_anim_test(31), scripted_path_effect_clip(4),
  light_switch(2).
Fix surface for eval leg: (1) KeyFrameColor sampling, (2) VM-color bind
resolution, (3) SolidColor default when colorValue absent. kfdouble
tracks are probably red herrings for color (opacity/transform).

## component_stateful_vm_instance_2 — text-metrics class (t4j, coord t47)

- Golden `Component` ev2 drawPath: `verbs=129 pts=304` — glyph-outline path
  data, i.e. a TEXT draw, not a shape. Embedded TTF (876KB blob: GDEF/GPOS/
  glyf/hmtx tables) drives real font metrics.
- Our divergence: consistent small vertex offsets (dx~0.127 standalone,
  dx~0.049 nested) = advance/position metric differences, same frontier as
  t47's kerned-advance work (k~1.047).
- VM machinery on this file is CORRECT: `boundColorProp` lands ff00ff12
  (SolidColor.colorValue pk=37 bind, propId=554=1 identity confirmed);
  zero boundStaticProp hits, fully static output — offsets are purely
  text-layout, not binds/keyframes/order.
- Fixture status: honest text-rendering residual; joins t47's class.
