# Koru Rive renderer — current state

Snapshot document. For the chronological evidence log (per-round measurements,
including the dead ends), see [`oracle/FINDINGS.md`](oracle/FINDINGS.md).
This file answers "where do things stand right now and what can I trust?"

Harness status at time of writing: **`oracle/verify_harness.py` → 8/8 PASS**.

---

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
