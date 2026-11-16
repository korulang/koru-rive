# Phase 4 scoping — koru-native rasterizer + i915 thin-subset

Commission item (rive-runtime.md phase 4, stretch): "The SDF rasterizer
has no polygon answer today; this is where the realization/variant stress
peaks." i915 thin-subset already scoped in `omni/commissions/gpu-render-path.md`.
This doc scopes both against the measured state, not aspiration.

## What the ops stream actually demands (measured)

`collectOps`/`collectArtboardOps` emits OpRec kinds 0–10:

- `0` pathBegin, `1` move, `2` line, `3` quad, `4` cubic, `5` close —
  arbitrary cubic beziers in local coords
- `6` pushmat (3×2 affine a,b,c,d,e,g), `7` popmat
- `8` draw (style fill/stroke, color u32, thick, join, cap, eo fill-rule)
- `9`/`10` clipPush/clipPop (clip = path geometry, not just rect)

Corpus measurement (TIER1_DEEP, 406 fixtures): the stream-equal set
proves our decoder emits the right *commands*; what no Koru code does
today is turn them into pixels without `libs/canvas` (CoreGraphics
backend). Phase 4 = a rasterizer that consumes this exact stream.

## A. koru-native rasterizer — path coverage

### Input contract (fixed, already gate-verified)
OpRec stream per frame per artboard. No new decoder work needed.

### Required coverage, ordered by corpus frequency

1. **Scanline polygon fill** — flatten cubics/quads to line segments
   (de Casteljau subdivision to tolerance), even-odd + nonzero winding
   (eo flag already on OpRec), 4×4 or 8×8 ordered-grid AA.
   *This is the irreducible core — every fixture needs it.*
2. **Stroke expansion** — thick/join/cap (miter/round/bevel) → outline
   path → fill. Rive stroke joins map to canvas joins; corpus shows
   join=999 defaults (miter) dominate.
3. **Affine transforms** — pushmat 3×2 compose; apply to flattened
   geometry or transform rasterizer space.
4. **Clip paths** — clipPush/clipPop as stencil/mask layer (offscreen
   coverage buffer AND-ed into frame) or scanline clip-list.
5. **Paint** — solid color only for v1 (corpus stream-equal set is
   overwhelmingly solid fills; gradients/image paints are named gaps).

### Explicitly out of scope (named gaps, not silent)
- Gradients, image paints, feathered shadows — separate commissions.
- Text — glyph paths arrive as ordinary path ops already (textDrawPath
  emits V-streams), so text *renders* once path fill exists; shaping
  stays in the decoder layer.
- Blend modes beyond source-over (blend=3 normal dominates corpus).

### Verification path (already built)
- Tier-1 unchanged: ops stream is the input contract — rasterizer must
  not alter it.
- Tier-2 pixels: render OpRec stream → RGBA buffer in Koru, compare
  against `oracle/render_browser.mjs` PNGs (already committed pairs in
  `oracle/images/`). RMSE/diff-pixel thresholds exist from the
  side-by-side work.
- Performance gate: 500×500 frame rasterize < ~8ms single-thread on
  M-series (measurement, not aspiration — set by canvas parity needs).

### Where it lives
`rive/index.kz` grows a `raster` section or a sibling `rive/raster.kz`;
output = `*Pixels<rasterized!>` custody type feeding `libs/canvas`
blit or headless compare. Koru-native means: no CoreGraphics calls in
the fill path — CG only at the final present/blit edge if at all.

### Honest unknowns
- Bezier flattening tolerance vs golden pixel parity — needs empirical
  tuning against Tier-2 pairs; too coarse = visible facets on curves.
- AA kernel choice (ordered grid vs supersample) — pick by measuring
  both against browser reference on the 20 stream-equal fixtures.
- Stroke join math (miter limit behavior) — Rive uses Skia semantics;
  corpus fixtures mostly exercise round joins, miter-limit edge cases
  rare.

## B. i915 thin-subset

Already commissioned separately (`gpu-render-path.md`): price full
pipeline vs thin subset on T590/HD620. koru-rive's stake is narrower:

- Rive's draw model is 2D affine + solid fills + alpha — squarely in
  "Lantern-sufficient GPU" territory IF the thin subset covers:
  transformed textured/solid quads, alpha blend, scissor/clip rects.
- Path fill is the problem: i915 has no fragment-shader-free polygon
  rasterizer in the thin model — either tessellate to triangles on CPU
  (rasterizer §A emits triangle soup instead of scanlines) or the thin
  subset needs a coverage/shader path → scope collision with the
  gpu-render-path spike's open question.
- **Dependency**: i915 work should consume the rasterizer's flattened
  geometry, not re-derive it. Order: §A first (correctness), i915 second
  (port the triangle-soup output to BCS/RCS).

## Recommended order

1. §A.1 scanline fill + AA (unblocks everything, pure Koru, Tier-2
   verifiable today)
2. §A.2 stroke expansion (corpus stroke fixtures already stream-equal)
3. §A.3 transforms + §A.4 clips (mostly plumbing — ops already carry them)
4. Tier-2 pixel gate across the 61 stream-equal sections
5. §B i915 — gated on gpu-render-path.md spike outcome; consumes §A
   triangle output

## What this is NOT

- Not a claim the rasterizer exists — it doesn't; this is scope.
- Not replacing `libs/canvas` — canvas stays the present/blit surface;
  the rasterizer is the fill engine underneath or beside it.
- Not phase-4-complete when scanline fill lands — strokes/clips/AA all
  required before "path coverage" is honest.
