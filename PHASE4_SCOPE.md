# Phase 4 scoping — GPU polygon path coverage (koru-native)

Commission item (rive-runtime.md phase 4, stretch): "The SDF rasterizer
has no polygon answer today." Correction applied: **no CPU scanline
rasterizer** — the pipeline is Metal/GPU end-to-end. "Path coverage"
means polygon fill on the GPU backends, Tier-2-verified.

## The actual gap (measured)

- `libs/canvas` verbs (`draw.path` etc.) already rasterize arbitrary
  paths **on Metal** — gallery_live proves it live (Rive ops replay
  through canvas verbs, pixels correct).
- The gap is **koru-native GPU coverage**: the SDF `fillShape` path has
  no polygon answer — it handles signed-distance shapes, not bezier
  outlines. Rive's OpRec stream (kinds 0–10: move/line/quad/cubic/close,
  pushmat/popmat, draw, clipPush/clipPop) needs a GPU polygon path on
  backends that lack the canvas-verb route.

## Per-backend coverage matrix

| backend | polygon path today | phase-4 work |
|---|---|---|
| Metal via `libs/canvas` | DONE — draw.path verbs, live-verified | none (reference) |
| koru-native GPU (non-canvas) | MISSING — SDF fillShape only | tessellate OpRec paths → triangle mesh → GPU draw; or Metal-layer path reuse |
| CPU reference | n/a — deliberately out of scope | none |

## What "coverage" must handle (from the ops stream)

1. **Flattening** — cubic/quad → polyline at GPU-appropriate tolerance
   (can happen on CPU cheaply; it's math, not rasterization).
2. **Tessellation** — flattened polygon → triangle soup (ear-clipping or
   monotone partition; fill-rule even-odd vs nonzero already on OpRec).
3. **Stroke expansion** — thick/join/cap → outline geometry before
   tessellation (same math regardless of backend).
4. **Transforms** — pushmat 3×2 affine; apply in vertex shader or bake
   into tessellated coords.
5. **Clips** — clipPush/clipPop as scissor rects where possible, stencil
   or mask texture for arbitrary path clips.
6. **Paint** — solid fills v1 (corpus stream-equal set is overwhelmingly
   solid); gradients/image paints remain named gaps.

## Verification (Tier-2, per regime)

- Input contract unchanged: OpRec stream (61 stream-equal sections are
  the gate's proof the commands are right).
- Pixel oracle: render same OpRec stream through each backend → compare
  vs `oracle/render_browser.mjs` reference PNGs (`oracle/images/` pairs
  committed). Backend parity = pixel-diff within threshold, not prose.
- Metal-via-canvas is the reference implementation — koru-native output
  must match it within AA tolerance.

## Recommended order

1. **Tessellation core** (backend-agnostic): OpRec path → flattened
   polygon → triangle soup with fill-rule. Pure geometry, Tier-1-adjacent
   (can be unit-verified against canvas output).
2. **Stroke expansion** — corpus stroke fixtures already stream-equal.
3. **koru-native GPU path** — consume triangle soup on the native backend;
   Tier-2 verify vs canvas reference on stream-equal fixtures.
4. **Backend consume** — koru-native GPU path draws the triangle soup;
   Tier-2 verify vs canvas reference on stream-equal fixtures.

*i915 excluded from current work per Lars ruling 2026-11-16; named future forcing-function target for the GPU pipeline — revisit when Metal-side coverage lands.*

## What this is NOT

- Not a CPU rasterizer — struck entirely. Flattening/tessellation math on
  CPU is fine; pixel coverage happens on GPU.
- Not decoder work — ops stream is done and gate-verified.
- Not claiming coverage exists — Metal-via-canvas works today; the
  koru-native polygon path does not. This doc is scope, not status.

## Consume surface — uniform realization contract (Lars 2026-11-16)

The interface Omni consumes must be UNIFORM across realizations —
Metal first, then koru-native — with variant/realization surfaces
monomorphizing to static calls. Phase-0 law applies: the koru-native
part declares identical signatures or refuses loudly at compile.
Deliverable is that uniform surface, not a second API.

Concretely: `draw.path`-equivalent verbs take the OpRec stream (or the
tessellated Tri soup) identically on both backends; realization choice
is a compile-time variant, not a runtime branch. Stroke/fill/clip
semantics must match canvas-verb behavior bit-for-bit where the Tier-2
gate measures.

## Tier-2 pixel gate — first measured results (2026-11-16)

Oracle: `oracle/pixel_oracle.py` vs `oracle/images/ref_*_c_t*.png`
(render_browser.mjs headless-Chrome references, Rive 2.37.0 canvas
backend). Ours: path-verb replay (`probe:step` → draw.path) — the
Metal/CG realization, NOT the mesh path (mesh consume blocked on the
koruc emit defect, t4b).

| pair | verdict | ink-mass | coverage-gap |
|------|---------|----------|--------------|
| clfp t1 | PASS | 0.99 | 0.98% |
| clfp t5 | PASS | 0.98 | 0.89% |
| clfp t10 | PASS | 0.99 | 0.91% |
| hello_world t1 | PASS | 1.01 | 0.07% |
| dsm t1 | FAIL — artboard mismatch | — | — |

dsm: ref ink=(0,0,249,99) @500²; our ab:9 Main is a vacuous container
(0 drawPaths golden-side — known); Row content lives at ab:20. The
ref was rendered against the browser's default artboard — needs the
correct ab mapping before a verdict, not a renderer defect claim.

Mesh consume status: ops→tessellate/strokeVerbs→Tri events→mesh.*
verbs→GPU pixels works end-to-end (bg fill exact, stroke geometry
emitted) but pixel-correctness is BLOCKED on koruc emit defect —
`mtri(tv)` inside ~proc silently emitted loop var `t` (consumer
binding-name collision; t4b owns the fix). CTM bake + clip events
committed producer-side (`ff18735`).

### Gate extension attempts (same session)

- `clipping_and_draw_order [child]` ab:84 @786² — **PASS** after two
  real fixes: (1) pixel_oracle gained `--comp` alpha compositing +
  two-sided ink coverage; (2) the "parent-context gap" was actually
  viewport FIT — browser uses Fit.Contain+Center (render_browser.mjs
  Layout), our driver drew 1:1 top-left. Child ab is 176×176 in a 786
  canvas → scale 4.4659. With transform.push(4.4659) wrapper:
  ink-bbox EXACT, mass 1.00, coverage-gap 0.21%. Child artboards
  render standalone correctly — no component-list expansion needed
  for single-artboard refs; dsm/clfp-Item sections likely same fix.
- `databind_external_artboard_main [Main]` ab:15 @500² — vacuous for
  pixels: solid backdrop only, zero ink both sides (ink-mass 0/0);
  backdrop delta 9 vs tol 8 was a wrong --bg guess (fixture bg is
  40,40,40). Not a useful gate fixture.
