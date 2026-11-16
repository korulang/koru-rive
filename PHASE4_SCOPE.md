# Phase 4 scoping — GPU polygon path coverage (koru-native + i915)

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
- i915 thin-subset (`gpu-render-path.md` spike): BCS blitter does 2D
  copies/fills today; polygon fill needs either tessellated triangles
  or a coverage-capable pipe — the spike's open question.

## Per-backend coverage matrix

| backend | polygon path today | phase-4 work |
|---|---|---|
| Metal via `libs/canvas` | DONE — draw.path verbs, live-verified | none (reference) |
| koru-native GPU (non-canvas) | MISSING — SDF fillShape only | tessellate OpRec paths → triangle mesh → GPU draw; or Metal-layer path reuse |
| i915 thin-subset | MISSING — BCS 2D only | tessellated triangle soup → BCS/RCS draw calls; scoped by gpu-render-path spike |
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
- Metal-via-canvas is the reference implementation — koru-native and
  i915 outputs must match it within AA tolerance.

## Recommended order

1. **Tessellation core** (backend-agnostic): OpRec path → flattened
   polygon → triangle soup with fill-rule. Pure geometry, Tier-1-adjacent
   (can be unit-verified against canvas output).
2. **Stroke expansion** — corpus stroke fixtures already stream-equal.
3. **koru-native GPU path** — consume triangle soup on the native backend;
   Tier-2 verify vs canvas reference on stream-equal fixtures.
4. **i915** — gated on `gpu-render-path.md` spike; consumes the same
   triangle soup → BCS/RCS.

## What this is NOT

- Not a CPU rasterizer — struck entirely. Flattening/tessellation math on
  CPU is fine; pixel coverage happens on GPU.
- Not decoder work — ops stream is done and gate-verified.
- Not claiming coverage exists — Metal-via-canvas works today; native +
  i915 polygon paths do not. This doc is scope, not status.
