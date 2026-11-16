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

- `component_list_default_state_machine [Row]` ab:20 @500² — Fit.Contain
  wrapper (200x40 -> scale 2.5, y-offset 200) lands ink in the right band
  (y 200-299 both) but FAIL: ours x extends to 374 vs ref 249, mass 1.50.
  Browser ref ran with "State Machine 1 not found" (wrong SM name) ->
  bind-pose/static; our frame:0 eval differs. Verdict: content/state
  mismatch, not transform — needs correct SM name for a fair ref.

- `component_list_follow_path [Item]` ab:74 @500² — bind pose FAIL:
  ours covers full canvas with Item's green field (modal 18,161,0),
  ref ink concentrated (0,107,282,327). Browser bound "State Machine 1"
  SUCCESSFULLY for clfp (no SM error) -> animated state, not bind pose.
  Verdict: needs SM-eval parity, not fit — named, correct diagnosis.

- Mesh AA attempt: `[[barycentric_coord]]`+fwidth smoothstep in
  tri_fragment → ink-mass hit 1.00 but bbox exploded frame-wide
  (94% gap) — tessellated stroke micro-tris get ramps wide relative
  to tri size, painting partial-alpha haze. REVERTED (oshun tree
  clean). Proper AA needs per-tri edge varyings or supersampled
  offscreen pass — named, not attempted.

- SM binding for clfp Item (ab:74): stream-cluster membership —
  SMs are flat (parent=-1); an SM belongs to the artboard whose
  object-index range contains it. clfp layout: Main@18, Item@74,
  Artboard@114; SMs at 67 (Main's cluster), 98+121 (Item's cluster).
  Item prop236 defaultStateMachineId=0 -> first SM in cluster =
  obj 98 ("State Machine 1", Hover bool input + Row listeners).
  ops() has NO sm parameter — selection is implicit via cluster;
  eval gap = entering AnimationStates/transitions/inputs at frame.

- clfp Item frame:0 == bind-pose result (identical FAIL). Pixel diff
  narrows it precisely: green row-bg renders IDENTICALLY (18,161,0
  sampled both sides); the 88.8k diff px live in y107-392 = the row
  CONTENT region — component-instance children our ops stream doesn't
  expand for this artboard. Gap = component-content expansion inside
  Item, not bg alpha, not SM eval, not fit.

- clfp Item cluster dump (objs 74-113): content = LayoutComponents +
  Text obj 77 (TextValueRun 82, style paints/axes, SolidColors,
  Fills) + animations + SM 98. ZERO NestedArtboard/artboard-instance
  objects — the missing content is TEXT (glyph layout/emission),
  not component-instance expansion. Revised gap attribution.

- Text gap root cause: emitTextDraw/textDrawPath exist ONLY in the
  golden-dump print path (dumpDrawOps) — they emit drawPath text to
  stdout for golden comparison, never into the OpRec ops stream.
  collectOps has no text arm -> text objects contribute zero ops ->
  invisible in every renderer path (mesh AND path-verb). clfp Item's
  missing content = unwired text emission, not missing glyph tech.

- Text emission deep trace: text IS wired into collectOps already
  (glyph paths -> OpRec under world transform) — but textDrawPath
  returns false for Item's Text obj 77: it requires a TextStyle
  object (type_key 137, slot==styleId) which does NOT exist in
  Item's cluster. Item uses the newer TextStylePaint(78)/
  TextStyleAxis(80,81) style chain — legacy TextStyle lookup
  misses -> no font size/asset -> zero glyph ops. Gap = text
  STYLE MODEL (new paint/axis chain), not emission wiring.

- Text trace final: emission wired + style lookup may actually hit
  (137 IS TextStylePaint; run styleId=4 vs paint slot TBD) — next
  failure candidate is the FONT: textDrawPath needs type-106 font
  objects with SFNT bytes (prop 212); clfp may reference a non-embedded
  font asset -> font="" -> zero glyphs. Verify font presence next.

- Font verdict: clfp HAS embedded font — obj1 FontAsset "Inter",
  obj2 FileAssetContents carries full SFNT (glyf/hmtx/cmap/GPOS
  tables visible). textDrawPath looks for type_key==106 with prop
  212 bytes; FileAssetContents may carry a different type_key ->
  font lookup misses -> zero glyphs. Verify type_key next.

- Text emission CONFIRMED live: textDrawPath returns true for Item
  obj77 — 100 verbs/192 pts, color ffffffff (white), one eo-fill
  drawPath per frame (the "2 draws" = bg + all-glyphs path). Text
  ops ARE in the stream and DO replay. The pixel gap is CONTENT:
  TextValueRun holds literal "text" while the browser renders the
  ViewModel-bound label — data-binding gap, not emission/glyphs.

- VM-binding probe (clfp): decoded graph complete — 3 ViewModels
  (StarItemVM@6, MainVM@8, ItemVM@14), 3 ViewModelInstances
  (prop566 = VM index 0/1/2), typed props (ViewModelPropertyNumber,
  SymbolListIndex), DataBindContexts (21/25/83: prop586=bound
  property id, prop660=context slot, prop588=path bytes).
  TextValueRun obj82 text prop268="text" literal; DataBindContext
  obj83 prop586=268 binds that property id -> VM instance value.
  Split verdict: VM DECODE complete; BINDING RESOLUTION (prop586
  -> instance -> property -> value) is the missing eval step.

- VM value probe: instance property values DO decode —
  ViewModelInstanceNumber prop575=dbl (6, 10) + prop554=index.
  ItemVM's only prop is SymbolListIndex ("List Index") — the row
  text/icon resolves through a SYMBOL LIST, not a string prop.
  prop586=268 binding -> instance -> SymbolListIndex value ->
  list entry lookup. Numbers present; symbol-list contents are
  the next decode target.

- DataBindContext decoded: prop586=DataBind.propertyKey (268 =
  TextValueRun.text!), prop588=sourcePathIds bytes, prop660=
  converterId. obj83: propertyKey=268, sourcePathIds={2,0},
  converterId=2. Binding = propertyKey 268 on the text object <-
  sourcePathIds path -> VM instance property. {2,0} segment
  semantics next (index into instance prop list? nested path?).

- VM binding RESOLVED for clfp Item text (t42): clfp.riv has NO
  ManifestAsset(642)/DataBindPath(643)/flags(587) -> absolute path
  semantics. DataBindContext obj83 targets obj82 via lastBindableObject
  rule (nearest preceding non-DataBind in stream). sourcePathIds {2,0}
  = [viewModelId=2, propertyId=0] -> ItemVM instance obj16 -> value
  obj17 ViewModelInstanceSymbolListIndex propId=0 (prop814 absent -> 0).
  converterId=2 -> 3rd DataConverter in stream order = obj5
  DataConverterToString -> symbolListIndex -> "0". Implemented in
  boundRunText/vmScalarOf/vmScalarToString (rive/index.kz); textDrawPath
  substitutes before glyph emission. Measured: text-swap zone
  (5,107)-(95,147) ref-mismatch 1282/1308px -> 13/1308px; content-zone
  diff>60 3352->2083px, mean 53.8->33.2. Residual FAIL = pre-existing
  layout overdraw (ours green covers 57% frame vs ref ink x0-155
  y107-327) — layout-solving gap, not binding. render_browser.mjs gained
  RIVE_VM env for binding a named ViewModel (ItemVM needed; default
  byIndex(0)=StarItemVM binds nothing for Item — bound==unbound bytes).

- Layout fill-parent fix (t42 cont.): Layout-box bg pass now resolves
  units==3 against artboardIntrinsicSize when parent is the artboard —
  Item's style obj87 intrinsicallySized=true makes its layout box
  content-bounds+padding (~27x40pt), not declared 91x52. Also
  artboardContentBounds now measures boundRunText (was literal 'text',
  4 chars -> box 2x too wide). Result: ours content bbox (0,107)-(157,327)
  vs ref (0,107)-(156,327) — ink-bbox PASS exact. Residual: ink-mass
  2.84x + coverage-gap 49% — likely cornerRadiusTL=8 rounded corners
  (obj85) we draw square + text edge detail. Named, smaller than before.

- Rounded layout-box corners (t42 cont.): Fill-under-409 pass reads
  cornerRadiusTL-643 off the component's own 420 style (TL-inherit,
  clamp min(w,h)/2), emits op-kind-4 cubics; zero radii keep sharp
  rect. clfp Item gate now PASS (--comp 255,255,255 --bg 255,255,255):
  ink-bbox exact, ink-mass 1.05, coverage-gap 2.64%, within_1px ~96-99%.
  cl1/dsm check: dsm has no triggers (only pk=800 binds, no 606/640)
  -> ours_dsm_row_fit.bmp byte-identical, no regression. cl1 HAS
  triggers: pk=268 bind {1,0} resolves to first vmId=1 instance
  'Instance 3' -> text 'THREE' (per-item instance selection via
  ViewModelInstanceListItem is the remaining gap — all rows would show
  the same string until list replication lands); style TL=10 radius
  now rounds its layout box. cl1 was already FAIL-scope (list binding).

- Per-item VM resolution (t42 cont.): listRowItems resolves 559 -> pk800
  bind -> path -> instance -> 441 list -> contiguous 427s (was: all 427s
  per list). g_rowVmid/g_rowInstOrd scope each row's emission;
  boundRunText picks Nth instance of bind's vmId on match. cl1 rows now
  ONE/TWO/THREE/THREE/THREE/THREE/TWO/ONE (verified rowbind print).
  clfp Item gate unaffected (no 427s); dsm ops identical.

- cl1 row layout (t42 cont.): ref re-rendered with RIVE_FIXTURE=cl1
  (prior "ref" was clfp — missing env var, falsifier caught it). True
  cl1 ref: 5 visible rows 200x50 at x0, y=0/60/120/180/240 (pitch 60 =
  50+gapV10, column). listRowSlot = 559 world x main-axis offset;
  kind6/7 wrap per row in collectOps + emitOps. Ours now emits all 8
  rows at correct slots — green bands match ref exactly for y<300.
  Residuals: (a) no scroll clip — rows 6-8 overdraw y300-469 (ref
  clips at ScrollView 300px); (b) intra-row text x-position differs
  (ours ~x0-60 vs ref ~x66-128 — Item-internal alignment unsolved);
  (c) oracle ink metric is luminance-based — green rows (mean 69.7 vs
  bg 49) score 0.10 < 0.15 threshold, invisible to ink checks; gate
  FAIL reflects text/bright-ink deltas + unclipped rows, not row fills.

- cl1 scroll clip (t42 cont.): collectOps wraps each 559's rows in a
  clip rect from nearest clip=true(196) LayoutComponent ancestor
  (obj26 ScrollView 460x300 at origin -> y<300). Ours now shows exactly
  the ref's 5 green bands (47332 vs 47557 px, 99.5%). Gate: ink-mass
  1.60->1.00 PASS; remaining FAIL = ink-bbox x (text alignment) +
  coverage-gap, both from intra-row text x-position.
- NAMED ORACLE LIMITATION: pixel_oracle ink = luminance coverage
  |mean(bg)|>0.15 — green rows (mean 69.7 vs bg 49) score 0.10 and are
  invisible to ink-bbox/mass/gap. cl1 gate can only see text+bright
  ink; row fills need a color-aware ink channel (two-sided like the
  coverage() comment anticipates) before green-on-dark fixtures gate
  fairly.

- cl1 intra-row layout (t42 cont.): layoutSizeOf/layoutAvailOf/
  layoutOffsetOf — 409-parented nodes get layout position (alignment
  632==4 center, units 607/608, intrinsic 606 content bounds via
  measureTextSize) instead of Node.x/y, hooked into effectiveWorld +
  effectiveWorldRaw. cl1 gate now PASS: ink-bbox exact, mass 1.00,
  gap 0.05%. Text white-bbox ours (69,18,130,271) vs ref (69,18,129,271).
  clfp Item gate still PASS (no regression). Named gaps: alignments
  other than center(4) fall to top-left; nested-409 intrinsic content
  uses declared size (cycle guard); non-position local transforms on
  layout children ignored.

- clv (component_list_clipped_viewport) GATE PASS @HEAD: absolute
  positioning (positionType=2, edges 516-519 active via units 621-624,
  absent value=0, opposing edges stretch) in layoutOffsetOf+layoutSizeOf;
  409-with-artboard-parent seed rule extended; Fill box pass now uses
  effectiveWorldRaw translation (was raw Node.x/y). Viewport clips at
  (100,100,200,200), Overlay bottom bar, 4 green rows pitch 60 —
  ours==ref exactly (34000 green px, gap 0.00%). RECURSION FIX:
  effectiveWorldRaw layout hooks reach artboardIntrinsicSize->bounds->
  world = cycle -> SIGSEGV on clfp Item; artboardContentBounds now uses
  effectiveWorldNoLayout (transform-only). render_browser.mjs gained
  RIVE_VM_INST=N (instanceByIndex) — clv needed inst 0 (only instance)
  AND tick>=1 (list populates after first advance; tick=0 ref was EMPTY
  — second false-ref caught by green-px count). cl2 recon: needs
  flexWrap grid + NumberToList converter + SM listeners — new arc.

- koru-native real-target link: DEFERRED to koru-os build pipeline —
  koru-os is a bare-metal PID-1 userspace (MPMC rings + io_uring);
  _koruos_* symbols live in its runtime, not a macOS-linkable lib.
  Emit-clean under --build=koru-native is the achievable compile
  check on this host (measured: fillTri @as fix, native_mesh_smoke.k).

- clip_tests diagnosis: ops(ab:42) emits ~10 drawPaths ALL
  color=ff880000 (the red field) — hidden paths drawn as fills.
  Browser renders only the visible-path ink region. Our opacity-0
  cull (prop18) doesn't catch whatever flag marks these hidden —
  likely a separate hidden/isVisible drawable flag or the paths
  are clip sources mis-emitted as draws. Named: hidden-content
  culling gap.

- clip_tests refined: draw.clip.push.path EXISTS on macOS arm and
  probe.kz already maps kind-9 ops to it — path clips ARE wired.
  clip_tests still floods red -> failure is inside clip.push.path
  realization or clip-path coordinate space, not missing verb.
  Next diagnostic: clip path bounds vs expected ink region.

- clip_tests op-order finding: probe bridge correct (kind9 ->
  clip.push.path consumes accumulated hcell path, copies geometry).
  Suspect = op ORDER: clip path verbs emit, then k=6 transform push,
  then k=9 clip push — clip.push.path rasterizes at PUSH time under
  whatever CTM is current; if the clip path was authored in the
  post-transform space but pushed before/after the wrong transform,
  the mask lands wrong -> effective no-clip -> red flood. Next:
  verify clip path coords vs the k=6 transform ordering in collectOps.

- clip_tests ROOT CAUSE: Shape47 "Rectangle-clipped" has ClippingShape
  child (type42, sourceId=1 -> Shape43 "Ellipse-clipper" slot1).
  Clipper's own Fill51 isVisible=false (now culled by 969669c).
  Real clip = clipper's ELLIPSE geometry (~171x171 = ref ink bbox).
  Our ops emit a generic 500x500 clip instead — ClippingShape objects
  are never resolved to sourceId geometry. Bounded fix: shape with
  ClippingShape child -> emit kind-9 clip from SOURCE shape's path,
  wrap draws, pop.

- clip emission debug: clip path verbs emit correctly (ellipse
  cubics, radius 85.8 = 171.5/2 exact) under source world transform.
  Suspect: clipper's TWO ellipse children carry Node.x offsets
  (+150.1 / -89.1) forming left+right halves — clip path gather may
  miss child-node transforms -> mask shifted ~-150px left -> ink=0.
  Main draw path handles this somehow (passes elsewhere) — diff the
  transform composition for clip-source vs draw-source gathers.

- cl2 recon (component_list_2, commissioned arc): NO 427/441 objects —
  list is SYNTHETIC via DataConverter 'Number to List 1' (converterId=0,
  viewModelId=0) on MainVM 'ItemCount' (=12). listRowItems' 441->427
  chain absent -> ours renders pure bg (9 ops). Ref (BIND_VM=MainVM,
  RIVE_VM_INST=0, SM 'State Machine 1', tick=1): gray items
  0xcccccc ~96k px + white ellipses/text ~21k on 0x313131 bg.
  DECOMPOSITION: (1) NumberToList converter resolution in the pk=800
  path — generate N items from bound number; (2) flexWrap grid —
  obj17 style flexWrapValue=1 gap10 pad10 units3, 2D slots
  perRow=floor(availW/(itemW+gapH)); (3) per-row ItemVM index bind
  ('List Index'/'State' components -> ItemLabel text + ellipse
  visibility); (4) SM listeners pk=634 + KeyFrameColor anim on
  ellipses (entry-state colors at frame 0). Item obj31: 100x100,
  Node.x=534 offscreen base (layout overrides), gray box obj46
  111x105 units3 + 2 white ellipses 34x34 + centered label.
