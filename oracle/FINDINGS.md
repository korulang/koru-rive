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
