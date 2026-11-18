# Koru Rive renderer — current state

Snapshot document. For the chronological evidence log (per-round measurements,
including the dead ends), see [`oracle/FINDINGS.md`](oracle/FINDINGS.md).
This file answers "where do things stand right now and what can I trust?"

Harness status at time of writing: **`oracle/verify_harness.py` → 8/8 PASS**.

---

Provenance: oracle/provenance.py stamps .prov.json sidecars {driver,commit,ts}; run_gates flags fresh|stale|unprovenanced per ours asset (all 33 currently unprovenanced -- render->stamp->freeze going forward). vacuous_px=200 boundary mutant-pinned in selftest.

## 1. One-paragraph summary

We have a from-scratch Rive `.riv` runtime (decode → player → flat ops stream →
canvas replay → raster) in `rive/index.kz`, replayed by Oshun's canvas. Tier-1
verified: `component_list_follow_path`, `hello_world`, `component_list_default_
state_machine` row, clfp Tier-1 14/30 stream-equal, corpus 61 stream-equal.
Tier-2 pixel-oracle arc (this session's end-state): **9 pixel-PASS + clip_tests
pixel-exact** (clip defect chain fixed across both repos), mesh placement-exact
(mass 0.71 — AA honest negative, degenerate guard landed), image decode LIVE
and spec-correct (alpha-verified vs PNG texels), systematic bg-fill divergence
FIXED (artboard-child Fill arms removed — KORU112 resolved upstream @ koru
439af385c). Corpus expansion exhausted: remaining fixtures classified
oracle-limitation (hosted-404, type-544 formula tokens, VM-data-unbound,
browser-vacuous SM-input) or feature-limitation (image decode now closed;
formula eval/VM binding = t4f lane). `component_list_1` list-binding/layout
solving remains the primary unverified gap.

---

## 2. What the oracle is

There is no golden-image file in this repo. The oracle is **two independent Rive
renderers**, both driven by `oracle/render_browser.mjs` in headless Chrome with a
deterministic clock:

| backend | package | version |
|---|---|---|
| Canvas2D | `rive_canvas` (alias of `@rive-app/canvas`) | 2.37.0 |
| WebGL2 (SwiftShader) | `rive_webgl` (alias of `@rive-app/webgl`) | 2.37.0 |

They are version-locked to each other and pinned; the renderer refuses to run if
the versions differ or do not match `RIVE_EXPECT`.

`oracle/render_ref.mjs` (node-canvas, `@rive-app/canvas` 2.39) exists but is
marked **OUTLIER — do not use as the oracle**. It disagrees with both browser
backends (wave-apex stroke 1.50 px vs 1.00 / 0.98). Every reference image in
`/tmp/rive_oracle` was produced by it, which is the origin of several wrong
conclusions in this project's history.

**Verdicts come from `oracle/band.py`, not from a chosen number.** It requires

    d(A, ours) <= max(1.25 * d(A, B), floor)
    d(B, ours) <= max(1.25 * d(B, A), floor)

where `A` and `B` are the two backends. If the two oracles (or the three input
files) disagree beyond a usable limit, it refuses to issue a verdict (exit 2)
rather than inventing one.

---

## 3. What is verified

All results below use `--inset 2` (the reference renderer draws a 1 px light
frame that is cropped from both sides before analysis).

| fixture | pose | result |
|---|---|---|
| `component_list_follow_path` (Main) | ticks 1–6 | **PASS** every tick |
| same, card path 320×320 (`rive_card.kz` transform) | tick 1 | **PASS** (0 magenta surviving) |
| `hello_world` ("New Artboard") | static | **PASS**, band ≈ 0 |
| `component_list_default_state_machine` (Main) | 1 row | **exact**: 4000 px, x[0..99] y[0..39], 100×40 |

Two details worth keeping, because they show the measurements are real rather
than lucky:

- **Our distance to Canvas2D is flat across the whole animation.** Over ticks
  1–6: `pixdiff` 0.63–0.66 %, `mean_abs` 0.25–0.26. No pose-dependent defect.
- **What grows is the two oracles disagreeing with each other**: their
  `coverage_gap` band goes 0.93 → 21.32 across those same ticks, as strokes
  become more diagonal and Canvas2D/WebGL2 AA profiles diverge. `band.py`
  excludes that metric once it exceeds the usable limit and says so.

---

## 4. Defects found and fixed

| # | defect | visible as | root cause | fix |
|---|---|---|---|---|
| 1 | Contour truncation | artboard backdrop rendered as a 45° triangle; rings 3/4; curve short | `buildPath` popped each contour's terminal point to match a lossy golden *text* format | keep the point in geometry; suppress it only when printing (`printPathGolden`) |
| 2 | Colour management | backdrop `#404040` instead of `#313131` | `CGColorCreateGenericRGB` (γ 1.8) drawn into a DeviceRGB (γ ≈ 2.2) bitmap context | `CGColorCreate` in the context's own colour space |
| 3 | Component-list rows at host frame | row 150 px wide instead of 100 | rows pass passed the animation frame into the embedded artboard, applying a keyframe Rive does not apply in list items | collect rows at the base pose (`-1`) |

Defect 2 is worth noting for how it was confirmed: `49/255 = 0.1921 → ^1.8 =
0.0513 → sRGB encode = 0.2511 → 64`, i.e. exactly the observed value, with white
(1.0) unchanged. The prediction matched before the fix was made.

Fix 1 shipped with a property that matters: the **golden text dump is
byte-identical before and after** — the fix moved pixels only, which is what
proved the bug was in the renderer rather than in the golden.

---

## 5. Claims that were retracted

Listed because they are instructive, and because you may remember them.

| claim | why it was wrong |
|---|---|
| "stroke weight is 36 % light / a phantom (both ways)" | measured against the node-canvas outlier. Against both browser backends ours is within 1 %. |
| "17.2 % of reference content is missing" | the outlier again, plus a binary ink mask: two renders agreeing to `meanAbsDiff 0.81/255` scored 16.8 % "missing" because a 1 px stroke straddles the threshold. Replaced by a symmetric, blurred coverage gap. |
| "the band is zero" (three versions of `@rive-app/canvas`) | three builds of **one** renderer measure version drift, not implementation independence. |

Also corrected: `ref_f8.png` is not 8 ms. It matches **tick 4** (mean diff 0.16);
`ref_f500.png` ≈ tick 15. The old harness's wall-clock race let four rAF ticks
fire, which is why the corpus is mislabelled ~4× and why several comparisons
were between different animation times.

---

## 6. Known gaps — not verified, not fixed

**1. ViewModel list binding (primary blocker).** Our rows pass draws *every*
`ViewModelInstanceListItem` (427) in the file. Rive draws the list of the
artboard's **bound ViewModel instance**. On
`component_list_default_state_machine` the two coincide (1 item, so it passes);
on `component_list_1` they diverge badly — 24 file items vs ~6 rows drawn.

**2. Layout solving.** `LayoutComponent` width/height/style are decoded but no
layout is ever solved: no positions, no flex stacking, no clipping, and sizing
only works where the base pose already carries it. This is what blocks:
multi-row lists, row placement, and correct clipping.

**3. `component_list_1` overall.** Rive draws 47,557 green px over
x[0..199] y[0..289]; ours draws 9,761 px confined to a single 200×50 box. The
box size is now *correct* (validating "sizing units 3 = fill parent"), but all 24
wrong-count rows land at the origin. **Not verified, visibly different.**

**4. Gallery at GUI level.** SUPERSEDED 2026-11-16: the component now lives on
`omni/rough/gallery_live.k` (real `libs/canvas` window, `fr: world.frame`) —
`/tmp/lantern_live.bmp` snap verified: card region 160,000 nonzero px, 0
fallback pixels, ~1,200 frames stable. The old `canvas/tests/gallery.k`
surface is retired. Tier-1 at frame 0: transforms/styles/colors/V-coords
match the clfp golden (draw order of the two strokes swapped — cosmetic,
non-overlapping).

**5. Other fixtures.** SUPERSEDED 2026-11-17: corpus sweep + Tier-2 gates
classified the viable set — 9 pixel-PASS + clip_tests PASS; the rest are
oracle-limitation (hosted assets, type-544 formula tokens, unbound VM data,
browser-vacuous state-machine inputs) or feature-limitation classes now
mostly closed (image decode landed `koru-rive@8d1a31b`+`oshun@6190fac`). See
`PHASE4_SCOPE.md` for the full classification log.

---

## 7. How to run it

Dependencies live in `/tmp/rive_oracle/node_modules`; `oracle/node_modules` is a
symlink to it. **This is not vendored** — the harness will not run on a clean
checkout until that is fixed.

```sh
export DSH_NODE=<path to node>

# the gate: everything, with negative controls
python3 oracle/verify_harness.py

# individual pieces
python3 oracle/selftest.py       --ref /tmp/vh_ref_t1.png --inset 2
python3 oracle/band_selftest.py  --a A_t1.png --b B_t1.png --inset 2
python3 oracle/band.py           --a A_t1.png --b B_t1.png --ours ours_t1.bmp --inset 2
python3 oracle/pixel_oracle.py   --ref A_t1.png --ours ours_t1.bmp --inset 2

# render a reference (tick = exact 1/30 s steps)
node oracle/render_browser.mjs rive_canvas 1 /tmp/ref_t1.png 500 Main "State Machine 1"
node oracle/render_browser.mjs rive_webgl  1 /tmp/refw_t1.png 500 Main "State Machine 1"
```

Rendering our side: the probe `.k` files at the repo root
(`render_clfp.k`, `render_card.k`, `render_row.k`, `render_dsm_main.k`,
`render_cl1.k`) each clear to **magenta** so any uncovered area is unmissable, and
snap to a BMP. Build with
`ZIG_GLOBAL_CACHE_DIR=$PWD/.zig-global koruc run <probe>.k`.

---

## 8. Residual risks inside the harness itself

Documented rather than hidden:

- **`--inset` and `--ring` are per-fixture, chosen by hand.** A wrong inset biases
  every metric; a wrong ring makes the ring check meaningless.
- **Frame ↔ tick mapping is empirical and per-fixture** (`2*(tick-1)` for clfp;
  frame 0 matched tick 1 for dsm). It is *not* enforced by the harness.
- **`band.py` floors** (`coverage_gap 2.0`, `mass_dev 0.02`, `pixdiff 2.0`,
  `mean_abs 1.0`) are hand-chosen. They can only ever *loosen* the criterion; the
  oracle-vs-oracle band supplies the tolerance whenever the oracles agree.
- **The selftest's reference** is one fixture (clfp tick 1). It validates the
  check logic, not every content type.

---

## 9. Recommended next steps, in order

1. **Vendor the harness dependencies** (or add a setup script). Until then no one
   else can reproduce any of the above.
2. **ViewModel instance binding** for component-list rows — decide which 427
   items belong to the bound instance. Without this the rows pass renders the
   wrong *set* no matter how good the layout is.
3. **Layout solver** for `LayoutComponent`: positions, flex stacking, clipping.
   This unblocks multi-row lists and generalises the round-6 row sizing beyond
   the base-pose case.
4. ~~**Re-check the gallery at GUI level**~~ DONE 2026-11-16 — gallery_live.k
   live-verified (see §6.4).
5. **Widen fixture coverage** — run the band check across the other
   component-list fixtures as a batch.

---

## 10. File map

| path | role |
|---|---|
| `rive/index.kz` | decoder + player + ops emitter (3 fixes from §4) |
| `oshun/canvas/index.macos.kz` | `rasterizePath` colour-space fix (§4.2) |
| `oracle/pixel_oracle.py` | the checks; assert vs report split |
| `oracle/band.py` | self-calibrating verdict; refuses bad pairings |
| `oracle/selftest.py` | 19 mutation cases for the checks |
| `oracle/band_selftest.py` | 6 cases for the verdict logic (pass/fail/refuse) |
| `oracle/verify_harness.py` | the gate (8 properties, each with a control) |
| `oracle/render_browser.mjs` | canonical reference renderer (pinned, deterministic, blank-guarded) |
| `oracle/render_ref.mjs` | node-canvas path — **OUTLIER**, not for use |
| `oracle/FINDINGS.md` | chronological evidence log, rounds 1–9 |
| `render_*.k` | our-side probes (magenta clear, snapped BMP) |

Working tree: `rive/index.kz` carries the §4 fixes (uncommitted at time of
writing). Sibling repos: `oshun@0d973eb` (probe stroke-channel routing —
the live-garble root cause), `oshun@97cab7e` (path-handle leak),
`koru-rive@f372fd8` (animated color/opacity + diagnostics). The gallery
component lives in `omni/rough/` (`rive_card.kz`, `gallery_live.k`,
`lantern_card.kz` — `libs/metal` renamed `libs/canvas`).


---

## 11. Native raster arc — koru-native + Metal (end-state)

Two freestanding raster surfaces now exist under `--build=koru-native`,
both consuming the same OpRec stream via `kr/probe:step`, both verified
against the browser oracle. **No oshun canvas bridge** — the host-link
census (`opsdump_clip.k`) proved the runtime core links clean with zero
`_koruos_*`/`_koru_kbd_*` undefined symbols; the only host ABI is the
11-symbol `koruos-darwin/shim.c` (surface map, kbd poll, frame timing).

### 11.1 Software scanline surface (`oshun/canvas/index.koru-native.kz`)

`window.*`/`frames`/`draw.*`/`path.*`/`transform.*`/`clip.*` verbs over a
u32 pixel backing. Path fills = flatten→supersampled scanline; strokes =
quads+joint discs; path clips = binary coverage masks; images = loud-err
(no codec in kernel ABI — superseded on darwin, see 11.2).
**5/5 pixel gates PASS**: cl2, hw, cl1, clv, clip_tests (nested path
clips). Root causes fixed en route: `fillContours` bypassed `clipCov`
(routed through `pxBlend`), clip_tests artboard bg `(26,26,38)`, shim
ABI conventions (map nonzero=ok, kbd_poll −1=empty).

### 11.2 Metal surface (same file, `metal.*` verbs)

`metal.paths(on:1)` routes `draw.path` fills+strokes through Metal;
`draw.image` is always- Metal. Architecture:

- ObjC-runtime message sends (`mtlSend*`) — no bridge, no canvas verbs.
- Buffer-fetch vertex path (`vertex_id` + `[[buffer(0)]]`), 32B-stride
  `MVtx` (pos + premul col, 16B-aligned float4).
- Fills: flatten→earClip (winding-aware, `vbase` global indices)→tri
  soup→`drawPrimitives`→`getBytes`→CPU `clipCov`/`blendInto` composite.
- evenodd: two-pass stencil parity (invert mask → test-equal-1 →
  fullscreen emit). Fixed by `loadAction DontCare→Load`.
- Strokes: quad-per-segment + 8-seg round joint/cap fans (miter/bevel
  named delta).
- Images: `image.decode.data` = CFData→CGImageSource→CGImage→
  CGBitmapContext (bitmapInfo `2|(2<<12)`)→RGBA registry→RGBA8
  `MTLTexture`+linear sampler→textured-quad pipeline. cin renders ink;
  residual = shared cross-arm rect-semantics class (intrinsic 15×15 vs
  browser ~8×8 + alpha composite), NOT a Metal defect.
- Frame batch: consecutive unclipped draws record into
  `g_mbatch`/`g_msegs`; flush = ONE texture + ONE command buffer + ONE
  readback, ordered seg draws, per-eo-seg stencil sub-passes. Ordering
  contract: every px-writer/clip-verb/snap flushes first.

**5/5 pixel gates PASS, all-GPU for fills/strokes/eo**: cl2, cl1, clv,
clip_tests, hw. Per-call (unbatched) remainders: clipped draws, images.

### 11.3 Named deltas (honest, standing)

- Clip masks stay CPU-side (`clipCov` composite) — stencil path clips
  not yet implemented.
- Stroke joins/caps: round-only approximation (miter/bevel delta).
- evenodd batching: per-eo-seg stencil sub-passes (correct, not merged).
- cin image rect semantics: shared macOS+native residual (not Metal).
- lwti/type-544, VM-data, hosted-404 fixtures: unchanged oracle-limitation
  classes from §6.

### 11.4 Verification commands

```
KORU_BACKEND_LIBPATH=~/src/oshun/canvas/koruos-darwin   ~/src/koru/zig-out/bin/koruc build render_knm_<gate>.k   --build=koru-native -o /tmp/render_knm_<gate>
KN_TAG=knm_<gate> /tmp/render_knm_<gate>
uv run --with numpy --with pillow python oracle/pixel_oracle.py   --ref <ref> --ours /tmp/kn_surface_knm_<gate>.bmp   --bg <r>,<g>,<b> --comp <r>,<g>,<b> --allow-missing-time
```

Gallery: `oracle/gallery.html` carries `kn_*` (software) and `knm_*`
(Metal) pairs — 33 gates, regenerated per visual change.


---

## 12. Fidelity tier — the oracle now certifies agreement, not only feature classes (2026-11-17)

`oracle/pixel_oracle.py` asserts six new checks, all ours-vs-reference:
`backdrop-px`, `ink-colour`, `registration`, `frame-diff`, `anti-aliasing`,
`local-fidelity` (definitions in the module docstring). `oracle/selftest.py`
carries one mutant aimed at each, on a thin-stroke and a filled reference, and
prints a calibration table (worst legitimate control / tolerance / aimed
mutant); a control above a tolerance or a mutant below it fails the selftest.

Gates are no longer hand-labelled. `oracle/gates.json` names both files of
every gate (in `oracle/images/` only — no `/tmp`, no newest-mtime-wins);
`oracle/run_gates.py` computes verdicts into `oracle/gate_verdicts.json`;
`oracle/gallery.py` reads both.

**Re-run: 11 PASS, 22 FAIL of 33.** Fifteen gates previously hand-labelled
PASS now FAIL (the commit message of 062030f says sixteen; fifteen is the count):

| gates | failed checks | what is wrong |
|---|---|---|
| dsm | bbox, mass, gap, registration, frame-diff, local | ours 100x40 on magenta vs ref 250x100: render scale mismatch |
| clfp_item, clfp_hover, kn_sm_input, kn_clfp_item | frame-diff, local-fidelity | the "0" glyph is at the card's top-left; ref centres it |
| cl1_item | frame-diff, local-fidelity | ours draws "THREE" where ref draws "text" |
| cl2, kn_cl2 | frame-diff | grid-cell digits sit ~19 px left of where ref centres them (same text-placement family as the list-item glyph) |
| cl2_t10, kn_cl2_t10 | frame-diff, local-fidelity | same digits, at t10 |
| knm_cl1 | ink-colour, frame-diff, anti-aliasing, local | Metal: row text is an illegible filled blob |
| knm_cl2 | frame-diff, anti-aliasing, local | Metal: digits + no anti-aliasing |
| knm_hw, knm_clip, kn_clip | anti-aliasing | zero blended edge pixels (ref 1097 / 394 / 394) |

kn_clip.bmp and knm_clip.bmp are byte-identical files. The six LIMIT gates
and the mesh NOTE gate FAIL as their notes already said they would; lwti and
dcpo fail only because both sides are empty (vacuous, not a mismatch).
PASS: hw, cdo, dsm_row, clfp, cl1_main, clv, clip, kn_hw, kn_cl1, kn_clv,
knm_clv.

Named, bounded residuals the tier still allows: edge-phase disagreement on
colour edges present on both sides (bounded by registration <= 0.75 px,
ink-mass, anti-aliasing >= 0.5x ref); softer-than-reference edges are NOT
asserted; `band.py` is unchanged (its `pixdiff`/`mean_abs` already compare
ours to both oracles); cdo's gate artifact is `ours_cdo_child_r2_t1.bmp`
(the older `ours_cdo_child_t1.bmp` is an unscaled render and fails).

Eyeball audit (ASCII-instrumented, `verdicts_swe2_ascii.jsonl`): no oracle
PASS hides a visible mismatch; 15 FAILs confirmed; 5 FAILs are vacuous or
AA-only (cin/lwti/dcpo empty-vs-empty, kn_clip/knm_clip AA staircase).
Candidates for oracle growth: vacuous verdict class, ink-coverage check.


Oracle growth by audit (2026-11-17, second landing): two checks added from
the eyeball audit's candidates. `ink-coverage` asserts ref ink signal
inside the shared ink zone that ours paints as backdrop <= 3% (kn_hw's
139-px notch defect, invisible to anti-aliasing's blended-px count).
Vacuous agreement: both sides <200 ink px -> ink checks pass vacuous,
flagged `vacuous` in gate_verdicts.json and gallery notes; backdrop/size/
pairing/alpha still assert (iba/deam/hff still FAIL on backdrop).
Re-run: 13 PASS / 20 FAIL. Flips vs prior run: cin/lwti/dcpo FAIL->PASS
(vacuous), kn_hw PASS->FAIL (ink-coverage). Selftest: notch mutant +
empty-vs-content mutant + blank-vs-blank vacuous flag case; calibration
worst-ok 2.54% vs tol 3.0%, mutant 9.18%. Eyeball package re-synced:
33 post-fix composites, extras/ holds 5 superseded tick pairs, gates.json
regenerated from gate_verdicts.json, RUNBOOK updated.


Text-placement fix (2026-11-18): two renderer defects closed the
eyeball-audit text clusters. `textDrawPath` ignored
`Text.alignValue(281)/sizing(284)/width(285)/height(286)` — fixed-width
centred text (cl2's 50-wide number cells) drew from the box's left edge,
~19 px left; the glyph path now takes the alignment slack (right/centre,
and vertical align is wired for completeness). Separately,
`effectiveWorld` baked `(pad - artboardOrigin)` for layout-managed
artboards, but `collectOps` does not emit the origin wrapper; the layout
offsets already carry the pad, so leaf text was shifted left/up. The
boundary translation is removed. `render_clfp_item_hover.k` now renders
frame 8, the pose the browser hover reference actually captures (same as
`kn_sm_input`), instead of frame 10.

Re-run: **21 PASS / 12 FAIL** (was 13/20). Flips: cl2, cl2_t10,
clfp_item, clfp_hover, kn_clfp_item, kn_sm_input, kn_cl2, kn_cl2_t10.
Remaining FAILs are the named classes only: dsm scale; cl1_item
VM-bound row text (`THREE` vs `text`); the knm_* Metal artifacts (the
headless window path dumps a blank surface, so they were not
re-rendered); kn_hw/knm_hw ink-coverage; kn_clip/knm_clip AA; mesh
stroke; iba/deam/hff vacuous backdrop. `oracle/gallery.html` and
`oracle/gate_verdicts.json` are regenerated. The eyeball package's `verdicts.jsonl` remains the
pre-fix audit snapshot and is annotated in `AUDIT_NOTES.md`.


Seam instrumentation, first slice (2026-11-18): `kn_clip` now has a
four-layer first-divergence report instead of a pixel-only verdict.
`oshun/canvas/index.koru-native.kz` emits a `KORUTRACE` line per path-clip
push under `KORU_TRACE_CLIP` (mask w/h, inside, edge, intermediate `mid`,
bbox, path hash). `oracle/trace_kn_clip.sh` captures the C++ stream
(`oracle/dump`), our ops (`opsdump_clip0.k`), the mask trace, and the
pixels; `oracle/first_divergence.py` writes
`oracle/first_divergence_kn_clip.md` from the data.

Result: scene/ops **MATCH** (2 clip pushes, 1 draw, color ff880000,
transform 258.9/176.3; C++ `5/3`, `6/12`, draw `6/4`); mask **DIVERGES**
(`mid=0` binary 0/255, inside 23094, edge 483, bbox 274,146-445,317;
ref 394 blended edge px); pixels anti-aliasing ours=0 ref=394,
frame-diff 0.000%. First divergent layer: **raster / clip coverage**;
missing surface: **fractional clip-mask coverage** (`rasterizeClipMask`
writes 255/0, `clipCov` samples `!=0`). The design and work split live in
`oracle/INSTRUMENTATION.md`. Next: fractional mask coverage, then the
compiler-realization seam.


Fractional clip-mask coverage (2026-11-18): the `kn_clip` slice's missing
surface landed. `oshun/canvas/index.koru-native.kz` now rasterizes path
clips with 4×4 supersampling (0..255 coverage) and `clipCov` multiplies
the fractional mask coverage into the fill alpha instead of sampling
`!= 0`. Nested clip coverage is multiplied, not min-ed. The probe clears
were set to the gate comp (`26,26,38`) so the raw surface is comparable.

Verification: trace `mid` went 0 → 515 (inside 23350, edge 486, same
bbox/hash). **`kn_clip` PASS** (AA ours=298 / ref=394, ratio 0.76;
frame-diff 0.000%; registration 0.00) and **`knm_clip` PASS** on the same
fractional mask. Full gate table: **23 PASS / 10 FAIL** (was 21/12).
`oracle/first_divergence_kn_clip.md` now reports "none at the instrumented
seams"; `oracle/INSTRUMENTATION.md` carries the before/after. Next seam:
compiler realization.


Pose/probe and fill-coverage slices (2026-11-18): `dsm` was a stale probe,
not a renderer scale bug — `render_dsm_main.k` opened `ab: 9` at 1:1
while the reference is the row (`ab: 20`) at 2.5×. It now renders
`ab: 20` with the 2.5× transform at y=0 and **PASSes**. `fillContours`
moved from 2×2 to 4×4 supersampling for thin glyph strokes; `kn_hw`'s
`ink-coverage` fell from the notch defect to 1.33% and **PASSes**
(AA 968/1097, ratio 0.88; frame-diff 0.000%).

ViewModel binding slice (2026-11-18): `boundRunText` no longer falls back
to the first instance of a ViewModel when there is no row scope. A
data-bound run now keeps its **template text** unless a row scope or an
explicit `kr/rive:vm.bind` is active; `vm.bind` was added, and the
`clfp_item` probes bind VM 2 instance 0. `cl1_item` renders the template
`text` and **PASSes** (frame-diff/local clean); the clfp group
(`clfp_item`, `clfp_hover`, `kn_clfp_item`, `kn_sm_input`) was re-rendered
with the explicit binding and re-verified.

Full gate table: **26 PASS / 7 FAIL** (from 13/20 at the start of this
arc). Remaining: `iba`/`deam`/`hff` vacuous backdrops, `knm_cl1`/
`knm_cl2`/`knm_hw` Metal text/AA, and `mesh` (NOTE, dashed stroke).


Stale-artifact correction (2026-11-18): the `iba`/`deam`/`hff`
"renderer bug" ruling was a stale-artifact false positive. Fresh
`render_iba.k`/`render_deam.k`/`render_hff.k` produce the spec backdrop
((49,49,49), (40,40,40), (49,49,49)); the committed `ours_*_t1.bmp`
files were 100% white. Refreshed artifacts make all three **PASS**; no
renderer fix is needed. The macOS clip trace shows a full 504×504 mask
(inside 250000, mid 0), so the clip was not eating the fill. Full gate
table: **29 PASS / 4 FAIL**; remaining are `knm_cl1`/`knm_cl2`/`knm_hw`
Metal text/AA and `mesh` (NOTE). `oracle/FINDINGS.md` carries the
correction; the lesson is to refresh and hash the artifact before
attributing a first-divergence layer.


Metal text seam (2026-11-18): glyph fills are now forced to evenodd
(`textFillRule=2`), so the Metal stencil-parity path subtracts counters
instead of filling them; the per-call EO path renders at 4× and
box-downsamples for geometric AA. `knm_cl1`'s white blobs are gone
(ink-mass 0.99, ink-coverage 0.12%, frame-diff 0.002%); `knm_hw`'s
ink-coverage falls to 2.65%. Both still fail `anti-aliasing`
(0.38 / 0.39 of ref blended edge px) and `ink-colour`: the browser's
font AA/hinting distributes ink over more edge pixels than our outline
glyph raster, a named text-raster residual, not a path-fill hole.
`knm_cl2`'s headless Metal probe still dumps an all-white surface; its
artifact remains stale. Full table stays **29 PASS / 4 FAIL** (three
Metal text/AA + mesh NOTE).
