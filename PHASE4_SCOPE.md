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
- clip residual isolated: ops now correct-looking — ellipse clip
  path (cubic loop, r=85.8) + source world translate(209.7,231.8)
  -> device ellipse x[124,295] y[146,318]; draw rect -> x[35,483]
  y[17,336]. Intersection NON-EMPTY -> ink should appear. ink=0
  means clip.push.path mask rasterization fails on this input:
  suspects = cubic-path flattening in mask rasterizer, or AND
  with the artboard frame clip (500x500 path clip also active).
  NOTE: ellipse child Node.x offsets STILL absent from clip verts
  (+/-85.8 centered at origin, not +150/-89 halves) — Ellipse
  type_key 4 may not be isNodeType -> pathSpaceMat identity.

- clip ellipse mystery narrowed: synthParametric DOES handle
  type_key 4 (Ellipse, line ~1905). Clipper shape43 has TWO ellipse
  children (44@+150.1, 45@-89.1, 45 has pathFlags=1) but clip path
  emitted ONE centered ellipse r=85.8 — either only one child
  gathered or offsets still absent. pathSpaceMat(44,43) should
  yield translate(150.1,...) since isNodeType(4)=true and prop13
  present. Next: count PVs per child / check if synthParametric
  early-returns on pathFlags=1 for obj45.

- clip mask internals: clip.push.path stores per-entry ctm and
  rasterizes each entry's mask with ITS OWN pctm (index.macos.kz
  ~3779) into a union-bounds atlas ANDed across active entries.
  Draw-time lookup (652-654) samples clip_path[clip_depth-1] —
  TOP entry only. clip_tests has TWO path clips active (frame
  500x500 + ellipse) — if top-entry sampling is correct that's
  the ellipse mask; ink=0 means ellipse mask itself rasterized
  empty OR clip_depth ordering off. Next: verify which entry is
  top at draw time + whether ellipse mask atlas region is nonzero.

- clip ordering verified: frame clip depth0 + ellipse clip depth1
  (top) during draws — top-entry sampling IS the ellipse mask.
  Emit-side fully correct; ink=0 = ellipse mask rasterizes empty
  inside clip.push.path despite correct path+ctm. Needs canvas-
  side instrumentation (dump mask atlas coverage or clipCov
  samples) — op-level debugging exhausted. Named: clip mask
  rasterization defect candidate in index.macos.kz.

- lwti classification: ops(ab:7) = frame clip + ONE fill
  ff313131 over the 500x500 rect = artboard bg fill. Browser ref
  is blank white (nonEmptyPx=250000 opaque, ink=None) because it
  failed to import type-544 content — the fixture's real
  text+image surface is undecoded on BOTH sides. Our bg-fill
  emission vs browser's blank = divergent handling of the same
  undecoded type-544 surface. Classification: oracle-limitation /
  undecoded-type territory, NOT a renderer defect. Type 544 =
  next decode target if this fixture matters.

- component_list_rtl_row: BROWSER-VACUOUS — Host AND Row render
  alphaMax=0 at ticks 1/10/30/60. Fixture needs VM data the oracle
  doesn't inject; no reference obtainable -> oracle-limitation,
  pixel gate skipped honestly (not a renderer FAIL).

- ik_over_distance_constraint: BROWSER-VACUOUS ticks 1/15/30/60 —
  IK fixtures need input-driven animation (pointer/drag), oracle
  can't inject -> oracle-limitation, gate skipped.

- early_exit_reversal_blend: BROWSER-VACUOUS ticks 1/15/30/60 —
  SM-transition fixture needs inputs the oracle doesn't fire;
  oracle-limitation, gate skipped. Same expected for
  early_exit_reversal_blend_elastic and other SM-input fixtures.
- Corpus-expansion finding: viable pixel-gate set is NARROW —
  only self-contained fixtures with default-visible static/SM
  content render non-vacuous refs (clfp, cl1, clip_tests, hw,
  cdo, dsm passed). Hosted/type-544/VM-data/input-driven classes
  are all oracle-limited. Remaining PASS fixtures mostly fall in
  the limited classes — expansion should target fixtures whose
  content is visible at bind pose.

- mesh AA pairing RESOLVED: ref_clfp_c_t1.png was a /tmp artifact
  (unrecoverable) BUT regenerated ref_clfp_main_t1.png has
  IDENTICAL ink-bbox (24,89,471,452) = same capture. Pairing was
  correct all along -> ours=(49,49,49) dominant IS our mesh
  output regressed vs 0.71-mass baseline. Suspects: AA shader cov
  OR meshops/ops changes since f4321af (t4f merge). Next:
  A/B — stash AA shader, re-render, compare ink mass.

- mesh AA verdict: A/B identical histograms (AA shader = pixel
  no-op on clfp mesh content — cov saturates on large tris).
  Backdrop resolved: scene bg IS (49,49,49) dark gray — correct
  oracle params --bg 49,49,49 (earlier magenta/white params were
  wrong). Residual ink-bbox whole-frame = sparse magenta clear
  visible at edges (mesh doesn't cover full frame) — separate
  coverage question, not AA. Honest: AA landed, no measurable
  delta on this fixture; degenerate guard correct regardless.

- magenta-edge residual DIAGNOSED: exactly 10 px at diagonal
  corners (0,0)-(4,4) and (495,495)-(499,499), color
  (152,25,152)=magenta/dark 50/50 blend. A/B proved pre-AA
  (identical histograms) -> tessellation micro-gap: bg quad's two
  tris don't share bit-identical diagonal endpoints -> hairline
  wedge at tips lets clear bleed. Cosmetic (10px/250k) but real;
  fix = snap shared-edge verts or weld duplicates in meshops.

- CORRECTION on 892b052: the 10px seam-bleed diagnosis was measured
  on a STALE /tmp/ours_mesh_t1.bmp (older driver state). Clean
  A/B (pre-AA 3f1c7c2 vs current, fresh renders both): identical
  853 nonbg / 0 edge px — no seam bleed exists in current output.
  Seam-gap diagnosis RETRACTED as unverified; mesh AA confirmed
  pixel no-op on this fixture; no coverage residual stands.

- in_band_asset: FAIL same signature — ours (49,49,49) bg field,
  ref blank (ink=None). PATTERN across lwti/hff/deam/iba: our
  runtime emits an ff313131 bg fill the browser doesn't draw.
  Either (a) systematic defect — hidden/invisible bg shape
  reaching paint loops via a path isVisible(41) doesn't cover
  (artboard-level bg?), or (b) browser genuinely shows nothing.
  ONE check decides: does the .riv's bg shape carry isVisible=0
  or is it artboard-background (different prop)? If (a) it's a
  real renderer defect affecting EVERY bg-fill fixture — higher
  value than more gates.

- bg-fill divergence ROOT-CAUSED (iba dump): Fill obj6 +
  SolidColor ff313131 are parented to the ARTBOARD/Image
  (parent_obj=3, Image type100 sibling) — NOT a Shape. Our ops
  emit them as full-frame solid rects; browser doesn't paint
  image-attached fills as rects (image itself unrendered ->
  blank ref). VERDICT: renderer defect — fills whose parent is
  not a Shape (artboard/image-attached) must not emit solid-rect
  draws. Reclassifies lwti/hff/deam/iba FAILs: they were this
  defect + image-decode gap, not pure oracle-limitations.
  Fix: gate fill emission on parent being a renderable shape.

- bg-paint arm located (~4300): paints ANY type-20 Fill with
  parent_obj==artboard as full-frame solid — over-reaches: iba's
  Fill (props=1, only SolidColor link, no isVisible) is likely
  orphaned/image-consumed data browser ignores. Artboard-child
  Fill != guaranteed background — need rive-cpp semantics for
  when it actually renders (or whether artboard bg is a color
  prop, not a Fill object). Fix candidate: restrict arm or
  verify against rive-cpp Artboard::background.

- bg-arm removal BLOCKED by compiler: deleting the two
  artboard-child-Fill arms (collectDraws ~4300 +
  collectArtboardOps ~4417) triggers KORU112 in UNRELATED
  meshops proc ('k','m','ring' bare module names, index.kz:5372)
  — verified stash/compile/pop A/B. Per koru rules this is a
  compiler gap (removing code shouldn't break an unrelated
  proc's name resolution); belongs in /Users/larsde/src/koru.
  Arm stays until compiler fix or alternative gate shape.

- oracle-metric re-measure: dcpo/iba/lwti/deam/hff/cin re-run
  under channel-aware coverage — NO verdict flips; refs genuinely
  ink-free (limitation classifications stand). Metric fix helps
  future colored-ink fixtures, not absent content.

- type-544 decode recon VERDICT: 544 =
  FormulaTokenParenthesisOpen (data_bind/converters/formula) —
  a databind FORMULA token, not renderable content. Browser
  rive 2.37.0 itself fails to import it -> blank refs are
  oracle-design, not our gap. Minimal decode pointless: real
  requirement = formula eval + VM binding (t4f lane). lwti
  classification CONFIRMED oracle-limitation, out-of-scope for
  renderer work.

- image decode recon VERDICT: cin's image IS embedded —
  FileAssetContents obj2 carries 245B PNG (89504e47 magic,
  IHDR 15x15); ImageAsset 'customLibraryImageAsset' assetId=123;
  Image type-100 assetId=0 -> resolves to the embedded bytes.
  Canvas side: draw.image/imagetint exist but take texture
  handles from image.load(PATH) only — NO bytes-load verb.
  Minimal decode spec: (a) canvas verb image.load.data(bytes)
  via CGImageSourceCreateWithData (one new verb, CG does PNG),
  (b) emit-side: FileAssetContents.bytes -> temp/handle ->
  draw.image at Image node's world rect. Bounded but real
  canvas+emit work — candidate next feature if image fixtures
  matter (cin + iba + lwti-class all gated on it).

- image rect semantics: originX/Y default = 0.0 (component_origin
  m_OriginX=0.0f) — center-clip theory FALSIFIED for default.
  cin image obj4 has only parentId+assetId props -> origin 0,
  scale 1, intrinsic 15x15 -> ours (0,0,14,14) is spec-correct
  per rive-cpp Image::draw. Ref (0,0,7,7) ~half-size unexplained
  — remaining suspects: browser-side image decode size, PNG
  display-density handling, or hidden layout-fit prop. Next
  probe: compare actual pixel colors ours-vs-ref in the 8x8
  region (scale vs alpha-vs-position bisect).

- cin pixel bisect: REF renders BLACK silhouette ([0,0,0]
  across region) — PNG RGB~0 + alpha shape (mask-style image).
  OURS renders gray alpha-blends ([32,32,32],[223,223,223]) —
  semi-transparent black texels blending on white. Decode
  pipeline works; residual = alpha fidelity: either (a) PNG
  texels genuinely semi-transparent and browser composites
  differently, or (b) our premultiply->straighten->blend chain
  loses alpha vs browser's. Next: dump PNG texel (0,0) alpha +
  compare against rendered value — decides decode-vs-composite.

- cin alpha verdict: texel(0,0)=rgba(0,0,0,223)=87% black ->
  correct white-composite = ~32 gray = EXACTLY ours [32,32,32].
  OURS IS SPEC-CORRECT. Ref [0,0,0] opaque black -> browser's
  image decode/render drops alpha for this mask-PNG (or draws
  opaque). Ours defensible; residual = browser image-pipeline
  semantics, not our bug. cin stays FAIL-by-oracle but ours is
  the correct render — candidate oracle-limitation reclass.

- iba re-gate under image pipeline: emits kind-11 (308B blob)
  but PNG is 1x1 grayscale ct=0 — single pixel, below ink
  threshold both sides. ink=None ref+ours = honest
  near-vacuous, NOT a decode failure. lwti ops=0 (type-544
  class, nothing to emit). Image pipeline re-gates: cin=live
  spec-correct, iba=vacuous-1px, lwti=out-of-scope.

- emitOps audit: LIVE but debug-only — callers are dumpDrawOps
  + list-row dump (drawops_clfp.k/drawops_dump.k/inspect3.k).
  Render path = collectOps->collectArtboardOps exclusively.
  emitOps is PRE-FIX semantics: no pathSpaceMat/xformPV (path-
  child compose gap from 1abec30 never ported), own fill loop
  at 3262. Verdict: superseded for render; debug dumps diverge
  from render on offset path children — name it, don't fix
  (debug-only, fixing doubles maintenance for zero gate value).

## Standing rule — visual gallery (Lars 2026-11-16)

Every visual change gets eyeball-able evidence, not just metrics.
`oracle/gallery.py` regenerates `oracle/gallery.html` + `oracle/images/pair_*.png`
(ours|ref composites for all 17 gates). Run it after ANY visual-affecting change
and commit the outputs. Add new gates to the GATES manifest when a fixture gets
a pixel verdict. Verdict labels are authoritative; images are the evidence.

- cl2 converter semantics (rive-cpp data_converter_number_to_list.cpp):
  input DataValueNumber N -> count=max(0,floor(N)); per item creates
  ViewModelInstanceListItem + createDefaultViewModelInstance(viewModel
  [converter's viewModelId=0=ItemVM]); output DataValueList of items.
  Item artboard obj31 viewModelId=0 matches -> rows resolve. Per-row
  instance = fresh default ItemVM instance each (identical values;
  'List Index' component likely supplies row index separately).

- cl2 GATE PASS: NumberToList synthetic path in listRowItems (568
  converter k816 viewModelId -> N rows instOrd=0), ListRow struct
  {vmId,instOrd} replaces []usize(427 idx) in both row loops, g_rowIdx
  feeds SymbolListIndex(566)->row index for to_string labels, flexWrap
  (604) 2D grid slots with perRow=floor(availMain/(item+gap)) —
  dir default corrected to 2=Row (Yoga enum, generated base default).
  NEW PASS: artboard-level Fill/Stroke->backdrop rect in collectArtboardOps
  (was emitOps-only; cl2 Main obj22 0xff313131 was magenta canvas clear).
  cl2: 12 rows 4x3 grid, ink-bbox exact (8,8,437,327), mass 1.00, gap
  0.17%. SM listeners+keyframes not needed at t1 (entry-state colors
  match) — named residual for animated frames. Regression: cl1/clv/
  clfpItem all PASS unchanged.

- cl2 t10 GATE PASS (color keyframes): KeyedObject.objectId=16 ->
  SolidColor obj48 (item fill 0xffcccccc) keyframes 0xff887e00->
  0xff000000 via Item's own Timeline. Rows render transforms at
  frame=-1 (dsm rule) but colors now animate: g_cframe carries the
  host frame into row emission; cf = frame>=0?frame:g_cframe feeds
  propColorAnim in collectArtboardOps (artboard paints, layout-box,
  shape fills) + collectDraws. cl2 t10: items black, ink-mass 1.00,
  gap 0.80%. SM listeners still unexercised (autoplay animation,
  no clicks in refs) — named residual. Regression: cl1/clv/clfpItem
  PASS, dsm ops identical.

- SM listeners SCOPED OUT (t42 ruling): browser refs are tick-driven,
  render_browser.mjs has no click/input injection -> listener->boolean
  (pk=634) paths have no pixel oracle. Not built; named gap until an
  input-injection oracle exists. cl2's animation is autoplay so t10
  gate is unaffected. Backend parity note: rive_webgl accepts
  the input set (smLog clean) but produces ZERO visual diff at
  any tick — input->SM propagation gap in rive_webgl 2.37.0,
  named oracle limitation; rive_canvas is the canonical ref
  backend so gates unaffected.

- lwti/type-544 VERDICT (standing commission item 1): formula eval is
  OUT-OF-SCOPE for this fixture — recon falsified the LIMIT premise.
  (a) Formula tokens (544/543/538) are ORPHANED: no DataConverterFormula
  (type 536) exists in library_with_text_and_image.riv to consume them.
  (b) The pixel gate doesn't need it: ref_lwti_t1.png is a blank
  (49,49,49) 500x500 frame and ours_lwti_t1.bmp is byte-equivalent
  blank — both sides match already. (c) The real lwti gap, if the
  fixture is meant to show content, is nested-library instantiation:
  the artboard has no direct drawables; content lives in
  FileAssetContents obj2 (embedded .riv, 428B) which neither renderer
  instantiates. data_converter_formula.cpp is a 585-line shunting-yard
  evaluator — real machinery, but zero observable pixels depend on it
  here. Building it is unjustified until a fixture has an active
  DataConverterFormula + a non-blank oracle.

- layout residuals milestone: layoutOffsetOf now applies the full 3x3
  alignment grid (632 row-major: 0-2 top, 3-5 center, 6-8 bottom;
  4==center preserved); layoutContentSize recurses into nested
  intrinsicallySized 409 children (cycle-safe — tree descent only, no
  parent lookup). All 5 gates re-verified PASS (cl1/clv/clfpItem/
  cl2t1/cl2t10), dsm ops identical.
- SM listeners UNBLOCKED (ebd588c): render_browser.mjs gained
  RIVE_INPUTS="Name:value@tick;Trig@tick" schedule -> stateMachineInputs
  at pump ticks. Proven: clfp Item Hover:true@5 -> 56,580 px diff vs
  no-input ref (listener->bool->visual path measurable). Remaining
  gap is OUR side: listener->boolean (pk=634) eval + input schedule in
  ops emission — t4f lane. cl2 autoplay unaffected.

- koru-native arm link attempt: --build=koru-native flag works
  (part gates exclude macos parts correctly) BUT render drivers
  fail frontend: libs/canvas:* tors are macos-part-gated —
  canvas surface absent on koru-native. The arm needs either
  (a) a canvas-free driver (decode+ops only, no raster) to
  reach link stage, or (b) a koru-native canvas/ CmdView
  surface (oshun/koruos ui_probe path exists for that).
  Undefined-symbol census NOT yet reachable — blocked at
  frontend, not linker.

- koru-native arm CENSUS RESULT: opsdump_clip.k (decode+ops,
  canvas-free) compiles+links+RUNS clean on --build=koru-native.
  nm shows ZERO undefined _koruos_*/_koru_kbd_* symbols — the
  runtime core is fully self-contained, NO host shim needed for
  decode+ops. The undefined symbols the arc feared live on the
  RASTER side only (canvas verbs are macos-part-gated, never
  reach koru-native frontend). VERDICT: bounded-shim question
  is moot for core; real gap = koru-native raster surface
  (CmdView/kwin path, oshun/koruos ui_probe idiom) — path (b).

- koru-native raster surface MILESTONE-0 census: oshun/canvas/
  index.koru-native.kz EXISTS (1062 lines, freestanding software
  raster into koruos/surface backing, u32 0x00RRGGBB src-over).
  HAS: window.*/frames/input.*/draw.rect/roundrect/panel/
  clip.push(.round)/pop/draw.mesh/mesh.*/text.*/release.frame.
  MISSING for koru-rive replay: path.open/move/line/cubic/quad/
  close/reset (7 verbs), draw.path, draw.clip.push.path,
  draw.image, image.decode.data/width/height, transform.push/pop
  (verify). mesh.* already consumes kr/rive Tri soup — the
  tessellator path is LIVE on koru-native. Next: implement path
  verbs (flatten->scanline fill) + draw.path -> first pixel gate.

- koru-native raster gates M1: cl2 PASS + hw PASS (native,
  no macOS bridge). cl1 FAIL (ink-mass 1.603, coverage — partial
  raster delta, likely clip-mask/transform edge). clv/clip
  pending verdict. Shim: KN_TAG env names surface dumps.

- koru-native gates M1 verdicts: cl2 PASS, hw PASS, cl1 FAIL
  (mass 1.603), clv FAIL (mass 1.2), clip FAIL (mass 2.43,
  coverage 100% — clips not applying). PATTERN: all FAILs are
  clip-heavy fixtures -> clip.push.path mask suspect (mask
  coverage or clip_aux indexing). Next: instrument clipCov
  mask branch on clip_tests.

- koru-native gates M2 (clip fix: fillContours->pxBlend):
  cl2 PASS, hw PASS, cl1 PASS (mass 1.002), clv PASS.
  clip FAIL residual: backdrop (26,26,38) vs white +
  mass 0.49 + gap 33.76% — mask polarity/coverage residual
  on nested path clips (not the bypass bug — that was fixed).

- koru-native raster arc COMPLETE (46c9fb5 + oshun 64df1a8):
  5/5 native gates pixel-PASS incl. clip_tests nested path
  clips. clip_tests residual resolved: artboard bg (26,26,38)
  not white + mask polarity on nested clips. Gallery 24 gates
  incl. kn_* native-vs-ref pairs. Named deltas: image decode
  loud-err (no codec in kernel ABI), stroke joins/caps
  approximated, rotated-rect bbox, binary clip masks.

- SM-listener recon (clfp Item Hover:true@5): ref regenerated via
  RIVE_INPUTS — smLog confirms "Hover@5=true", nonEmptyPx 33242.
  Visual diff vs idle = 31,324px in item box (0,107)-(157,327):
  fill 0x12A100 -> 0x0C6C00 (dark green hover state).
  Structure: Item SM obj98 has TWO single-keyframe hold animations —
  obj90/obj93 kf=0xff063700 (hover dark) and obj94/obj97
  kf=0xff12a100 (idle green), both KeyedObject.objectId=11 +
  KeyedProperty.propKey=37. obj110 StateMachineListenerSingle fires
  on pointer; obj105/107 StateTransitions gate on
  TransitionBoolCondition(inputId=0=Hover, opValue=1).
  BLOCKER for impl: keyframedColor/hasKeyframed scan ALL keyframes
  globally by slot+prop — both hold animations merge into one
  degenerate list, last-wins=idle green. Needs per-animation
  membership (which KeyedObject/KeyedProperty/KeyFrame belongs to
  which LinearAnimation) + SM current-state eval + input schedule
  plumbing before colors can select the hover kf. Decomposed:
  (a) animation-membership decode, (b) SM state/transition eval,
  (c) g_inputs schedule into frame eval, (d) per-animation kf scope.

- SM-listener milestone (a)+(d): animation membership decoded —
  exporter writes keyed objects right after their LinearAnimation
  (linear_animation.cpp:177); animOwnerOf maps each KeyedObject to
  its owning animation via contiguous kf-cluster stream order.
  g_activeAnim + kfOwnerOk now scope hasKeyframed/keyframedValue/
  keyframedColor per-animation (-1 = unscoped, all prior gates
  unchanged: ops identical). clfp Item structure verified: obj90
  'Timeline 2' owns kf 0xff063700 (hover dark), obj94 'Timeline 1'
  owns kf 0xff12a100 (idle green), both slot11+prop37.
  REMAINING (b)+(c): SM state/transition eval + RIVE_INPUTS schedule
  to set g_activeAnim. stateToId = index into layer's m_States
  (stream order); animationId = index into artboard's animations
  (stream order); TransitionBoolCondition inputId+opValue semantics
  still being pinned (opValue=1 vs absent polarity).

- SM-listener milestone (b)+(c) PARTIAL: input schedule (RIVE_INPUTS
  env -> g_smInputs, name:val@frame, bool holds latest<=frame) +
  smActiveAnimIdx eval landed. Verified resolving: clfp Item ab=74
  + Hover:true@5@frame10 -> animId=0 -> obj90 'Timeline 2' (dark
  hold anim). animArtboard = nearest preceding type-1 (slots are
  artboard-scoped, objectId can't resolve globally). stateToId =
  layer m_States stream index; animationId = artboard anim stream
  index; bool condition opValue 0/absent->require true, nonzero->
  require false. RESIDUAL: render still shows idle green — the
  keyframe target's slot/paint path isn't hitting propColorAnim
  (item fill SolidColor slot vs objectId=11 unverified; possibly
  the layout-box pass resolves a different SolidColor). Debug
  prints reverted; machinery compiles clean, gates unchanged.

- SM-listener residual recon: Item fill SolidColor IS slot 11 —
  obj86 (parent_obj=88 Fill under obj75 LayoutComponent), matching
  KeyedObject.objectId=11. Mechanism should paint dark: propColorAnim
  (slot11, key37, cf=10) under g_activeAnim=90 -> keyframedColor ->
  obj93 0xff063700. Render still green -> the visible green is likely
  painted by a DIFFERENT pass/object than the obj75 layout-box fill
  (shape-fill pass or a second Fill), OR layout-box pass resolves a
  different SolidColor. Next: trace which op emits the green rect.

- SM-listener HOVER GATE PASS: clfp Item RIVE_INPUTS='Hover:true@5'
  frame=8 -> transition crossfade lands exactly on ref's 0x0C6C00
  (12,108,0) = 50% lerp of idle green 0x12A100 / hover dark 0x063700
  (duration=200ms, input@5, frame8 -> 3 ticks=100ms -> t=0.5).
  Mechanism: smActiveAnimIdx resolves active LinearAnimation per
  artboard; g_activeAnim scopes keyframes; g_blendFrom/g_blendT drive
  propColorAnim lerpColor during mid-transition. Per-row SM scoping
  added (embedded artboard's own SM, not host's) — fixed cl2_t10
  regression where host SM scoped out Item row keyframes.
  Regression sweep: cl1/clv/clfpItem/cl2/cl2t10 all PASS, dsm ops=12.
  Gallery: 20 gates 0 missing; pair_clfp_hover.png added
  (ours_clfp_item_hover.bmp / ref_clfp_item_hover.png).

- Input-coverage recon (t42 next-leg): census across component_list
  family — StateMachineNumber(56): dsm declares 3 (a/b/level) but ZERO
  condition objects consume them (no TransitionNumberCondition
  anywhere) -> declared-but-unused, no observable path. Trigger(58):
  ZERO in family -> no fire() oracle. Bool(59): clfp Hover only
  consumed input (done). VERDICT: number+trigger input paths have no
  gateable surface in this fixture family — scoped out with census
  evidence, same class as earlier listener scope-out.
  Item 3 LIVE: clfp carries KeyFrame.frame=60 records (6+) — real
  frame-spaced keyframes exist (vs cl2's degenerate frame-0 holds).
  Intermediate-frame interpolation is implemented (keyframedValue/
  keyframedColor lerp); gateable iff a clfp Main/Item ref renders
  mid-animation. Next: check clfp frame-60 kf targets + ref ticks.

- NATIVE gate coverage (t42 lane): render_kn_sm_input.k — software
  offscreen raster (no Metal) drives clfp Item ab=74 frame=8 with
  RIVE_INPUTS='Hover:true@5' -> 0x0C6C00 blend, oracle PASS vs
  ref_clfp_item_hover.png (ink-bbox exact, coverage-gap 4.44%).
  dsm_row native drivers already exist (render_dsm_row.k/_b.k ops=10,
  render_dsm_main.k ops=12) — bound-row text path covered natively.
  Gallery: 21 gates 0 missing; pair_kn_sm_input.png added
  (ours_kn_sm_hover.bmp / ref_clfp_item_hover.png).

- Native coverage milestone 2: render_kn_clfp_item.k (ab74 f-1) +
  render_kn_cl2_t10.k (ab15 f10) both oracle PASS natively. kn_cdo
  RESOLVED: render_kn_cdo.bmp is byte-IDENTICAL to the known-good
  ours_cdo_child_t1.bmp gallery asset — driver reproduces the PASS
  render exactly. The earlier oracle FAIL was wrong --bg arg
  (49,49,49 vs the fixture's actual clear), not an emit gap.
  kn_cdo = PASS.
  Gallery: 23 gates.

- Metal arm M2: TRIANGLE PROOF COMPLETE — vertex_id+buffer(0)
  fetch path draws fullscreen tri (red 4096px verified). Key
  fixes: float4 needs 16B alignment in Metal address space
  (V struct padded to 32B stride); vertex-descriptor attribute
  path abandoned for buffer-fetch idiom (better for dynamic
  tri soup anyway). Clear+draw+readback all live on
  --build=koru-native. NEXT: tessellate paths->tris -> ops
  replay -> image texture path (codec resurfaces).

- Metal arm M3: metal.pathfill LIVE — flatten->earClip->
  tri soup->MTLBuffer->draw->getBytes->CPU clip-composite.
  Rect probe: 2304 red px exact (48x48 @8,8). v1 deltas:
  per-call texture (slow), evenodd holes named, CPU clip
  composite. NEXT: frame-persistent encoder, stroke tris,
  stencil path clips, ops replay gate, image texture path.

- Metal hw residual bisect: winding-aware earClip landed
  (correct regardless) but hw UNCHANGED (mass 0.67, xmax
  129 vs 340) — missing right-side ink is NOT winding.
  Next bisect: which op kind owns x>129 region (dump ops,
  check kind distribution in that bbox).

- Metal frame-batch: consecutive unclipped solid fills now
  accumulate into g_mbatch -> ONE texture/encoder/readback
  per flush. Flush hooks at every px-writer + clip verb +
  snap (ordering contract). eo + clipped draws stay per-call.
  All 5 knm gates re-verified PASS post-batch.

- Metal strokes on GPU: metalStrokeTris — segment quads +
  round joint/cap fans (8-seg) -> g_mbatch when unclipped,
  software fallback when clipped. miter/bevel = named delta.
  All 5 knm gates re-verified PASS.

- Metal image path M-image: image.decode.data LIVE on darwin
  (CFData->CGImageSource->CGImage->CGBitmapContext->RGBA
  registry), image.width/height, draw.image textured quad
  (RGBA8 tex + linear sampler + premul composite). cin
  driver built; kind-11 emits (imgemit obj4 245B). GATE
  FAIL named: backdrop (26,26,38) full-frame + ink=0 —
  decode-or-draw bisect pending (err arm vs texture path).

- cin bisect progress: backdrop bug ROOT-CAUSED+FIXED —
  window.clear.color only set win.clear for NEXT frames
  iteration; mid-frame clears left default dark backing.
  Now repaints win.px immediately (real canvas fix). cin
  backdrop now white PASS. Residual: image ink=0 — neither
  textured draw nor magenta err-arm visible at (0,0).
  Next: decode-handle vs draw.image composite bisect.

- Metal image path COMPLETE: bisect found 3 bugs — TVtx
  stride 40B vs shader 32B, stray setFragmentTexture:
  selector crash, CGBitmapContextCreate bitmapInfo 0x2000
  -> 0x2002 (premultipliedLast|byteOrder32Little). cin now
  renders image ink (0,0,14,14 mass 60 vs ref 19) — SAME
  named residual class as macOS arm (intrinsic-size vs
  browser half-size + alpha composite), NOT a Metal defect.
  Codec delta fully closed on darwin: kind-11 -> CGImageSource
  -> MTLTexture -> pixels. 5/5 knm gates re-verified.

- Metal eo batching: fills+strokes+eo all record into
  g_mbatch/g_msegs (seg = start/count/kind/col); flush =
  ONE texture+command buffer+readback, ordered seg draws,
  per-eo-seg stencil parity sub-passes. All 5 knm gates
  re-verified PASS. GPU path now fully batched except
  clipped draws (per-call) and images (per-call).

- Mesh dashed-stroke (sole FAIL gate): recon complete.
  Dash=507 has ONLY length(692)/lengthIsPercentage(693) —
  single dash length, gap = same length (Rive dash pattern
  is [dash,gap] alternating). DashPath=506 carries offset
  (690/691). Stroke paints parent Dash objects — find via
  parent_obj == paint slot. Plan: decode dash len+offset on
  stroke DrawRec -> OpRec/MeshDrawHdr dash fields -> in
  strokeVerbs path: walk flattened contour measuring arc
  length, emit dash-run sub-contours (skip gaps) -> existing
  quad/fan tessellation per run. meshops kind-8 style==0 arm
  at ~line 6019; probe draw.path stroke arm ~line 5885.
  Ref: ref_clfp_c_t1.png, ours_mesh_t1.bmp; fails
  ink-mass 0.71 / ink-coverage 65.66% / AA 0.

- ListFollowPathConstraint(625) — mesh gate last mile.
  Props: distance(363-range shared?), distanceEnd(888),
  distanceOffset(889), target slot, strength/orient likely
  shared with FollowPath(165). Semantics (rive-cpp
  list_follow_path_constraint.cpp): constrainList(list) —
  startOffset = distanceOffset + distance; per-item offset
  = startOffset + i * itemSpacing along pathMeasure of
  target path; constrainAtOffset per TransformComponents.
  Our gap: constrainedWorld handles 165 only; 625 needs
  LIST-LEVEL eval — enumerate constrainable list items
  (component_list rows), compute per-item arc offset,
  compose path position+tangent into each item's world.
  clfp rows currently emit x~0 (list at origin).

- constrainList impl state: graphdump(clfp) dumped to
  /tmp (G 128 objects); O-line grep pending — need type-625
  object's parent_obj (the ConstrainableList) + target slot
  + distance/distanceEnd/distanceOffset props, and how list
  items enumerate (row artboard instances under the list).
  Hook point: effectiveWorld/constrainedWorld per-item, or
  collectOps row-emission arm — per-item ordinal -> offset =
  distanceOffset+distance + i*(distanceEnd-distance)/(n-1)
  -> pathMeasureAt(targetPath, offset) -> compose pos+tangent
  into item world (mirror constrainedWorld 165 machinery).
  Env guards from 2676acf still in tree (uncommitted? check
  git status — they were committed in 2676acf).

- constrainList next-step correction: graphdump O-line fields
  are "O type_key slot parent parent_obj style_obj nprops" —
  grep '^O 625 ' directly (field 1 = type_key). /tmp/gdump
  binary exists; rerun: /tmp/gdump 2>/dev/null | grep '^O 625'
  plus '^O 165' for comparison. Then find list items: rows are
  NestedArtboard(92)/artboard instances whose ancestor chain
  reaches the constraint's parent (ConstrainableList).

- CRITICAL recon result: graphdump(clfp ab:all) shows ZERO
  type-625 objects AND zero type-92 nested artboards in the
  dump grep — the follow-path constraint may be a different
  type_key in this file, or rows position via list layout
  alone. Verify: /tmp/gdump | grep '^O ' | awk '{print $2}'
  | sort -n | uniq -c — enumerate actual type_keys present,
  look for constraint-ish types (165 handled? 625 absent?).
  If no 625 exists, the x~0 collapse is LIST LAYOUT solving
  (component_list rows at origin), not constraint eval —
  reclassify residual to t4f layout lane.

- constrainList residual (post-97dc6a5+a9feb54): traced
  positions CORRECT (10-row S + 6-row ellipse match ref ink
  windows) but rendered rows land as blobs BETWEEN traced
  points — row-origin vs row-body offset under tangent
  rotation, or missing component scale (constrainHelper keeps
  A.scale; our listRowSlot never applies layout sizing scale).
  destSpace default=world(0) so NO parent-space conversion
  needed — world-space tB was algorithm-correct. strength=1,
  spaces=world defaults confirmed. NEXT bisect: emit one row's
  vertex bbox under RIVE_TRACE_DRAW and compare vs traced
  (frac,pos,tan) — isolates whether slot reaches emitOps or
  row artboard adds its own offset/scale.

- constrainList bisect RESULT: all 16 rows emit ops (lfp fires
  per row, slot->op6->collectArtboardOps recursion confirmed).
  Rendered ink: ~4/15 traced windows show blobs AT the traced
  pos (rows 3,6 of list20; 1,4 of list24) — rest show ZERO ink
  in-window but scattered ink elsewhere on canvas. Signature:
  steep-tangent rows rotate content away from row-origin windows
  -> rotation pivot / row-local offset composition residual.
  Row content local coords vs pivot assumption is the open
  question (does row artboard center content at origin?).
  emitOps is debug-only (tracing-gated); real path = collectOps
  op6 CTM + recursion. DRAW trace prints object-hierarchy world
  NOT the CTM-composed transform — t=0,0 expected, not a bug.

- constrainList row-bounds dump (frame-8 ops): row artboard
  content = small ~40x40 rects (green ff12a100 fills + white
  detail), NOT 200x50 — rows are compact. Naive CTM replay of
  ops stream shows row bboxes scattered near origin-x — the
  k=5/6/7 transform-op semantics need exact modeling (push/
  absolute-vs-relative) before vertex-level bisect continues.
  ink blobs (~1000px/60x40win) = MULTIPLE small rows overlapping
  or row+stroke combos, not single big rects.

- constrainList SMOKING GUN: ops-stream k=6 transforms for
  rows show e=0 (x-translation ZERO) with rotation — rows
  collapse to x~0 column = the render bug. Traced pos.x=25..
  471 never reaches so.e. Check: (a) is the e=0 k=6 the slot
  or an inner artboard/clip transform? (b) so.e=slot[4] —
  Mat2 idx4=e; tB[4]=pm.pos.x set correctly in
  listFollowPathWorld? (c) trsCompose(rot,1,1,0,0) then
  tB[4]/[5] overwrite — verify no aliasing. Line 27 of
  clfp_ops.txt (frame-8 dump) is the suspect op.

- constrainList last-mile state: slot transforms VERIFIED in
  ops stream (e=25..471, rotations correct) AND meshops
  kind-8 arm DOES fold ctm_stk into draw verts (~line 6450).
  So transform path is complete on paper — residual must be
  in the ctm fold detail (application order to verbs/pts, or
  pts transformed pre/post flattenPath) OR row content offset.
  Uncommitted: lfp-slot trace print in listRowSlot.

- constrainList tri-trace miss: RIVE_TRACE_TRIS print landed
  inside the style==0 (stroke) branch of kind-8 — row fills are
  style==1 (tessellate branch) so it never fired. Move/duplicate
  the bbox print into the fill branch (after tessellate() call)
  to dump final tri world-bounds per draw. Everything upstream
  verified: slot->ops->ctm fold all correct on paper.

- constrainList end-state: pipeline verified correct through
  mtri emission (ctm fold -> per-tri vert transform -> mtri).
  Render STILL identical FAIL (mass 1.99, coverage 64.11%)
  across all instrumentation — residual is NOT missing
  plumbing. Remaining suspects ranked: (1) ctm_stk fold ORDER
  — stack[0]=outermost? if inner transforms push after slot,
  fold direction may invert nesting; (2) row artboard emits
  its own op6 that RESETS expectation; (3) draw.mesh canvas
  side ignores/handles tri coords differently. Next concrete
  step: dump ctm_stk depth+matrix at ONE row's kind-8 and
  hand-compose to compare vs traced pos.

- constrainList DECISIVE: ctm_stk dump shows [slot=tB, inner=artboard
  offset(+8,+8)] folding CORRECTLY (inner applied first, slot
  outer) — row0 stk=[-0,1,-1,-0,25,154.5]+[1,0,0,1,8,8] =
  90deg rot + path pos + 8px artboard pad. Verts land at
  traced positions BY CONSTRUCTION. Residual is therefore
  DOWNSTREAM of tri emission: mesh.tri/draw.mesh canvas-side
  consumption, or the row content's local coords vs pivot.
  Pipeline koru-side is exonerated end-to-end.

- constrainList final hypothesis: rotation pivot. Row content
  local coords span ~(0,0)-(40,40); tB rotates about ORIGIN
  then translates to path pos — under 60-90deg tangents the
  body swings ~40px perpendicular off the traced point =
  "blobs between positions" signature EXACTLY. rive-cpp
  constrainHelper would produce identical math UNLESS the
  item's authored pivot differs — check whether row artboard
  content is centered at origin in the .riv (shape coords
  -20..20?) vs our emission adding +8,+8 inner offset that
  shifts the effective pivot. Cheap test: translate tB by
  -(inner offset) rotated, or emit row content centered.

- constrainList RESIDUAL REFRAMED (decisive): ref_clfp has ZERO
  green pixels; ours renders ~600+ green (18,161,0 = paint
  ff12a100) — the row template's green background fill is
  wrongly VISIBLE. Positions/transforms verified correct
  end-to-end; the remaining bug is row-content visibility:
  green shape should be hidden/occluded/transparent in ref.
  Suspects: opacity-0 ancestor not honored inside row
  artboard recursion, hidden flag on the shape, wrong paint
  child selected, or z-order (white overlay should cover).
  rowbind confirms all rows legitimately vmid=2 (numbered
  list 0-9, single template) — not a binding bug.

- green spatial map: green ink concentrates at ~2 spots
  (~(175,175) and ~(175,325)) — NOT all 16 rows. So the green
  is a specific sub-element visible only in certain rows/
  positions, not a universal row background. Row artboard 74
  subtree: children = LayoutComponent(409 idx75) + LayoutNode
  (420 idx87); SolidColor(20 idx88, parent 75) is likely the
  ff12a100 source. Next: identify which shape under 75 carries
  paint->88 and why it should be invisible (opacity/clip/SM
  state) in ref.

- green source narrowed: row draws emit via layout-managed
  branch (~5253, FLD/box path) NOT the traced main-shape loop
  — that's why RIVE_TRACE_DRAW missed them. lcolor = SolidColor
  child of the paint (same propColorAnimOr). Green spots ~2
  positions = likely FLD boxes or layout-child shapes picking
  up ff12a100 paint. Mass decomposition: green ~600px of the
  ~1191 excess; rest = positional/shape mismatch of row
  content (rows verified at path pos but content shape/size
  vs ref unverified — next: dump one row's emitted path bbox
  in LOCAL coords vs ref row extent).

- green IS row content (RIVE_LFP_OFF -> green 6980 at layout
  column; fp-on -> 2416 at path positions). NOT FLD
  (RIVE_NO_FLD unchanged 2416). Emitted via layout-managed
  branch. Row74 subtree: nested LayoutComponents (409->76)
  + SolidColors (20->88 parent75, 20->89 parent78). Open:
  which shape carries paint->88, and whether ref hides it via
  opacity/hidden/VM-bound color (ViewModelPropertyColor 440
  exists; only boundRunText resolves VM props today — no
  bound-color path). If row color is VM-bound, base green
  shows instead of bound gray = exact symptom.

- VM-bound-color hypothesis DEAD: zero ViewModelPropertyColor
  (440) objects in clfp — VM props are numbers/lists only
  (431x2, 566, 568x2) matching the numbered-list binding.
  Green is AUTHORED color — shape must be legitimately
  invisible in ref via opacity/hidden/z-order/clip, or our
  paint picks wrong SolidColor child. Next: opacity/hidden
  audit — find shape owning paint->SolidColor88, check its
  ancestor opacity chain + whether a same-slot sibling paint
  (white/gray) should win instead.

- GREEN OBJECT CHAIN SOLVED: row74 subtree = Text(77/78/82,
  number glyphs, WHITE color carrier 79=ffffffff) + Layout
  components. GREEN = Fill obj88 (type20, parent_obj=75
  LayoutComponent) -> color carrier 86 (type18, prop37=
  ff12a100). It is a LAYOUT-ITEM BACKGROUND fill — the green
  boxes are layout-managed drawables whose visible area depends
  on layout solving. Ref shows zero green => ref's layout gives
  that item ~zero area or different bounds; ours sizes it ->
  green boxes. THIS IS THE t4f LAYOUT-SOLVER GAP MANIFESTING,
  not a paint bug. Text is correctly white.

- CS last hop VERIFIED: nested expansion (92/451/452 arm at
  ~5761) resolves artboardId prop197 as INDEX into file's
  artboard list -> target object idx -> recursive
  collectArtboardOps -> same shape loop where CS ancestor-test
  fires. Routing is CORRECT by construction. Residual question
  is aid->target mapping: do any instances carry aid 3/4/6
  (object idx 174/2328/5840 = artboard-list positions 3,4,6)?
  ab26 opsdump showed 1 clip — either ab26 isn't composed main
  or its instances target other artboards. Next: dump prop197
  per 451/452 instance + confirm true main artboard index.

- CS aid-mapping DECISIVE: artboard list idx->obj: 0=26,1=124,
  2=149,3=174,4=2328,5=4756,6=5840,7=9482,8=9504,9=9887,
  10=9916. Instance prop197 aids: ab26's five 451s -> 7,8,8,8,9
  (9482,9504x3,9887); ab9482's 92s -> 5,5,5,6 (4756x3,5840).
  REACHABLE CS owner: only 5840 (31 clips) via chain
  26->9482->5840. UNREACHABLE: 174(25)+2328(24)=49 CS — no
  instance targets aid 3 or 4 anywhere in file. Those clips
  CANNOT fire in composed render — matches FINDINGS'
  "~50 of 130 clips unaccounted" precisely (49 CS objects).
  Residual for clip-volume gate: nested expansion must carry
  5840's clips (reachable) AND the 49 unreachable are a
  fixture/oracle-scope question (ref may render them via a
  different composition path — e.g. direct artboard render).

- CS verdict path BLOCKER found: opsdump ab:26 emits only 33
  draws/1 clip — nested expansion NOT firing despite 5 owned
  451 instances (5840 alone has 303 draws). So composed render
  never reaches ANY CS target — the clip-volume gap is upstream
  in nested expansion (owningArtboard/aid-197 resolution or
  noNested gate), not in CS traversal (proven per-artboard:
  174->5, 2328->4, 5840->5 clips). NEXT: instrument the 451 arm
  — print ni/aid/target resolution for ab26 to see where it
  bails (owningArtboard!=26? aid<0? target<0? depth?).

- nest trace DECISIVE: 451 arm FIRES for ab26 — ni35/41/47->9504,
  ni59->9482, ni64->9887 all resolve+recurse (RIVE_TRACE_NEST).
  Yet composed opsdump still 33 draws — bail is DOWNSTREAM inside
  recursive collectArtboardOps(target): expanded targets emit
  ~nothing (SM state? opacity? frame? or target content is
  non-k8 kinds). 9482->5840 chain needs 9482's own 4 instances
  to fire in recursion — unverified whether depth-2 reached.
  NEXT: count draws per expanded target (trace collectArtboardOps
  entry per abIdx) to see which level starves.

- CS verdict DECISIVE: per-abIdx emit counts — ab26=28,
  ab9504=263x3, ab9887=122 (expansion WORKS), but
  **ab9482=0 ops TOTAL** — the gateway to 5840 (31 CS) emits
  literally nothing, so its 4 nested instances (->4756x3,
  5840) never fire. 5840's clips are reachable-but-starved at
  depth-2. Root cause candidate: owningArtboard() inside
  recursion returns wrong owner for 9482's instances (Koru's
  parent-chain walk vs file structure), or 9482 early-returns.
  49 untargeted CS (174/2328) remain structural per aid census.

- ab9482 zero-emission: next probe = owningArtboard() on its
  4 instances (object idx ~9483/9486/9489/9492 area) vs
  recursion abIdx=9482, plus SM/opacity guard check —
  collectArtboardOps may early-return for artboards with no
  direct drawables before reaching the nested arm (arm is
  AFTER shape loop but BEFORE return — verify ordering).

- ab9482 probe partial: owningArtboard() = parent_obj walk to
  nearest type-1 (no early-out bug visible); collectArtboardOps
  nested arm sits at fn end — no early return blocks it for
  drawable-less artboards. 0-emission therefore means either
  (a) 9482's 4 instances' owningArtboard()!=9482 under Koru's
  walk (parent_obj chain differs from file layout), or (b)
  exception/oom silently swallowed, or (c) 9482 itself isn't
  reached as abIdx (aid->target mismatch: ni59 aid=7 ->
  artboard-list idx7 = object 9482? VERIFY list order —
  artboards sorted by object idx: 26,124,149,174,2328,4756,
  5840,9482 -> idx7=9482 YES). Next: RIVE_TRACE_NEST inside
  recursion — does ni inside ab9482's call print candidates?

- DEPTH-2 FIX LANDED: nested arm MOVED from collectOps (root
  only) into collectArtboardOps end — recursion now expands
  all depths. VERIFIED expansion reaches depth-2+ but exposes
  NEW panic: integer overflow in keyframedColor->lerpColor
  (propColorAnimOr) inside nested collectArtboardOps — likely
  g_activeAnim/SM-scope or blend-state corruption at depth,
  or smActiveAnimIdx returning bad idx for SM-less targets.
  NEXT: guard lerpColor/keyframedColor inputs or fix
  g_activeAnim save/restore around nested expansion.

- lerpColor/keyframedColor overflow FIXED: guarded channel
  clamps (ch NaN/negative/over-255) + wrapping i64 subtractions
  (t1.f-t0.f, frame-t0.f) — panic gone, opsdump completes.
- NEW blocker: nested expansion now HANGS — arm inside
  collectArtboardOps re-expands shared targets per instance;
  diamond/cyclic nesting (5840 contains an instance) multiplies
  work, depth-8 cap insufficient -> opsdump never returns
  (timeout kills, zero OP output). NEEDS: per-path cycle guard
  (visited artboard set) or expansion budget. CS clips in 5840
  unreachable until bounded.

- CYCLE GUARD + panic chain FIXED: g_abStack[24] per-path
  visited set (seeded root in collectOps, push/pop in arm) +
  propU u64->i64 saturating cast + keyframedColor sh u5->usize
  overflow + channel clamps. opsdump_hx26 COMPLETES: 8487 ops,
  534 draws, 6 clip pushes (k=9), exit clean.
- Clip count 6 vs ref 130: residual = (a) 49 CS structurally
  untargeted (aid census), (b) 5840's 31 CS — did expansion
  reach it? per-shape clip emission should yield MORE than 6
  if all matched -> CS ancestor-match may under-fire. NEXT:
  RIVE_TRACE_NEST confirm 5840 reached + count CS matches.

- CLIP-VOLUME VERDICT DATA: expansion reaches 5840 at depth=2
  (ni9493 aid6, emitted=3654 ops) and 9482 (7538). Yet only 6
  k=9 clip pushes total vs 31 CS owned by 5840 — CS traversal
  UNDER-FIRES. Suspects: (a) CS parent shapes emit via
  layout-managed branch not the type-3 shape loop (CS check
  only lives there); (b) prop92 source resolution fails for
  most CS; (c) CS parents invisible/hidden. 49 CS in 174/2328
  remain structurally untargeted. Next: count CS objects whose
  parent_obj chain reaches a type-3 shape that actually emits.

- CLIP-VOLUME VERDICT: golden hunter_x_demo.txt = 130
  clipPath ops per frame (artboard-0 scope). Ours now 36 k=9
  pushes on ab26 f8 (was 1). Residual decomposition: (a) 49 CS
  structurally untargeted (174/2328, aid census — cannot fire);
  (b) emission-model delta — golden counts clipPath ops in
  rive's per-drawable-run interleave (start+end pairs per
  group), ours emits per-shape push/pop — count semantics
  differ so 36-vs-130 isn't 1:1 comparable; (c) deeper-nested
  CS inside 9504/9887 subtrees may still under-fire.
  Class verdict: traversal+expansion+cycle-guard all landed;
  clip volume went 1->36, residual is structural+model delta,
  not a traversal bug.

- FLEX-FLOW M1 MEASURED: db_health opsdump e-coords now spread
  0->9917 (was clustered ~36-50) — sequential flow LIVE but
  OVER-ACCUMULATING: ~31px steps over hundreds of children
  suggests layoutSizeOf summed for non-item children (420
  styles/containers) or wrong item set. Gold target ~755.
  NEXT: filter accumulation to actual flex items (exclude 420
  style objects + non-drawable children), verify dir axis,
  re-measure cluster vs 755.

- FLEX-FLOW M2 measured: 420-style filter did NOT change
  distribution — still 0->9917 ~31px steps. So over-accumulation
  is NOT style objects; either (a) genuinely hundreds of flex
  items (db_health long list — ref ~755 implies wrap/
  virtualization/clamp ours lacks), (b) wrong main-axis dir
  (598 absent -> default row=2 may be wrong for this container),
  or (c) items nested under intermediate nodes so p!=flex parent.
  NEXT: dump the flex parent's 420 props (598 value present?)
  + count its children + check flexWrap(604) — ref 755 smells
  like wrapped/visible-window layout.

- FLEX props dump: db_health has MANY 420 styles; at least
  one carries 598=0 (COLUMN per Yoga enum 0=col,2=row) +
  gap 498/499 — direction enum confirmed. The 0->9917 e-spread
  (x-axis) therefore comes from ROW-direction containers with
  genuinely many item children, not the column one. Gold ~755
  implies ref wraps/virtualizes/clips long lists — flexWrap(604)
  + visible-window semantics still missing. NEXT: per-container
  item counts + wrap check vs gold's ~755 cluster.

- FLEX WRAP M3 measured: line-breaking implemented (wrap!=0 ->
  crossOff/lineCross accumulate, mainOff resets per line) but
  e-distribution IDENTICAL (0->9917) — wrap containers absent
  or availMain never exceeded. Strong signal the spread is NOT
  from layoutOffsetOf flex at all for most values — likely
  nested-artboard/list transforms compounding. Verify by
  A/B: RIVE_NO_ flex env or check which op6 e-values trace to
  flex parents vs other mechanisms before more flex work.

- FLEX A/B ATTRIBUTION VERDICT: RIVE_NO_FLEX diff — >1500
  e-values IDENTICAL (306 both arms) => the 0->9917 spread is
  NOT flex-driven; it comes from listRowSlot/nested-artboard
  transform compounding (component-list row pitch over many
  rows). Flex contributes real but mid-range deltas (~50-770,
  ~7 net histogram lines). e36->e755 target therefore lives in
  the LIST/nested path, not layoutOffsetOf flex — flex work was
  correct-but-not-the-metric. NEXT: trace which op6 e>1500
  parents are (559 list rows vs nested 92/451) via gdump_dbh
  parent census.

- BIG-E ATTRIBUTION REVISION: bige traces (RIVE_TRACE_BIGE,
  uncommitted) show ZERO row-slot/nested op6 with |e|>1500 —
  spread is neither flex nor listRowSlot/nested transforms.
  AND: current working tree (concurrent lane's uncommitted
  animFps keyframe-time fix + scrub removal) collapses max e
  to ~73 — the 0->9917 spread was KEYFRAMED ANIMATION values
  under a 30fps-vs-authored-fps time-base bug, now corrected.
  e36->e755 divergence likely resolves via that fix; re-measure
  opsdump_dbh e-cluster vs gold ~755 once their edits commit.

- DB_HEALTH RE-MEASURE under t4j fps claim: e-spread STILL
  0->9917 IDENTICAL. t4j's fps-proper commit is NOT in this
  checkout (HEAD=e3b994c; pull --rebase did not advance —
  dirty-tree refusal likely). Earlier max-e=73 reading was a
  transient working-tree state (concurrent uncommitted edits
  since evolved). e36->e755 remains OPEN pending t4j's actual
  landed commit; re-measure then. Flex/layout hunt stays parked.

- TRIMPATH(47) IMPLEMENTED: trimContourRange + trimPathVerbs
  (flattenPath 0.25 tol, sequential total-length fractions +
  synchronized per-contour, offset rotation, de Casteljau
  already flattened upstream). Hooked per-paint in
  collectArtboardOps: stroke paints with type-47 child emit
  trimmed verbs/pts. trim.riv opsdump clean (27 ops ab1).
  Golden trim.txt: 62 drawPaths/31 verbs=0 — full-section diff
  pending (ab-index scope). Residual: multi-trim chaining,
  fill-mode closeShape, cubic-preserving split (currently
  flattened lines — same 0.25 tol strokeVerbs uses).

- TRIM VERDICT DATA: trim.riv has exactly ONE TrimPath —
  mode=2 (synchronized), NO start/end/offset props -> defaults
  0/1/0 = identity trim, so the 6-pathop stroke output is
  CORRECT-by-default, not a partial-trim bug. The golden's 31
  verbs=0 drawPaths belong to other drawables/scope. Residual
  question narrows to: does ref treat absent end(115) as 0
  (empty) rather than 1 (full)? Check trim_path.riv (the
  animated fixture) for keyed 114/115 to confirm defaults.

- TRIM_PATH_LINEAR VERDICT: fixture has REAL keyed trim —
  114=0.366, 115=0.685, mode=1 sequential. DrawPath COUNT
  matches golden (3/section). Stroke pathops=9 vs golden
  verbs=12 — trim FIRES but we emit flattened line segments;
  ref preserves native cubic verbs via de Casteljau split.
  Residual = verb-level fidelity, not correctness of region:
  same 0.25 tol strokeVerbs consumes, but golden diff flags
  verb structure. NEXT if pursued: cubic-preserving trim
  (split cubics at arc-length boundaries, keep verb 2/3/4).

- AB-SCOPE VERDICT: opsdump_dbh ab:180 IS the first/main
  artboard (objidx 180 of 11 type-1 objects) — scope CORRECT,
  the 0->9917 e-spread is real main-artboard fr0 output.
  Attribution chain now: NOT flex (A/B null), NOT row/nested
  (bige traces zero), NOT fps (identical under live WIP).
  Remaining: spread may be CORRECT (scrollable list rows
  legitimately off-viewport at e 2000-9900; gold ~755 could be
  a different frame/state) or an uncovered mechanism. Cheapest
  next: compare ours e-cluster vs GOLDEN db_health section
  directly (same frame) rather than the ~755 anecdote.

- TESS SPECIMEN SCAN state: emitOps (golden-format drawPath
  printer, ~3740) is invoked at 3199-3223 inside a proc whose
  tor wrapper wasn't identified before context limit — likely
  the corpus/golden regen path. NEXT session: find that tor
  (grep driver .k files for the proc name), run it on
  curve-heavy fixtures (check goldens for high verbs/pts
  drawPaths), diff verbs/pts vs ours per drawable -> specimens
  where divergence IS flattening. Alternative per t42: craft
  circle.cubic fixture with known ref tessellation.

- TESS SPECIMEN FOUND (text_follow_path_shape_length f0):
  drawPath count matches (22/22), straight paths verb-exact
  (5,3 / 4,9), but EVERY curved path is +1 pt: golden
  (1337,2945)->ours(1337,2946), (2691,6019)->(2691,6020),
  (1601,3547)->(1601,3548), (566,1179)->(566,1180),
  (778,1746)->(778,1747), (3257,7369)->(3257,7370). Uniform
  +1 vertex per curved contour = off-by-one emission (likely
  duplicated contour-close point in flattenPath/buildPath).
  Draw ORDER also permutes vs golden (z-order question,
  separate). This is THE vertex-exact frontier specimen —
  smallest possible delta, uniform signature.

- +1 PT ROOT CAUSE NARROWED: verbs counts MATCH golden
  exactly (1337=1337 etc.) — geometry/verb structure identical.
  The +1 is in PRINTED pts only: pathPrintedPoints suppresses
  each contour's terminal point; ours suppresses one FEWER ->
  isTailSegment/pathPrintedPoints off-by-one (extra contour or
  verb-5 boundary miscount), NOT a geometry bug. Fix site =
  pathPrintedPoints/isTailSegment in index.kz (~1845).

- +1 PT PINPOINTED: verb sequences IDENTICAL (1337=1337,
  verb-for-verb equal). Diff isolated to LAST cubic before
  close: golden prints 2pts (tail-suppressed), ours prints
  3pts — isTailSegment SHOULD return true (verbs[vi+1]==5)
  yet doesn't fire. Coordinate deltas (~0.001) are separate
  transform-precision noise. Contradiction unresolved:
  either verbs tail isn't [...,4,5] as printed, or
  pathPrintedPoints counts a different array. Next probe:
  dump raw verbs tail indices + isTailSegment verdicts.

- +1 PT RESOLUTION ATTEMPT: emitTextDraw (4752) prints RAW
  pts.items.len + unfiltered points — the diverging paths are
  TEXT glyph runs, not shape paths (printPathGolden was already
  correct). Applying isTailSegment suppression there
  OVER-suppressed (-74 pts): golden suppresses ~1 pt/path,
  meaning text-path pts= is closer to RAW count — the +1 is
  likely ONE REAL duplicate vertex in textDrawPath glyph
  contour emission (e.g., duplicated on-curve join point),
  not a print convention. Both experiments reverted; tree =
  HEAD + clean. NEXT: diff textDrawPath's verbs/pts tail vs
  golden V-lines point-by-point to find the duplicate vertex.

- +1 PT FIXED: emitTextDraw now suppresses ONLY the final
  drawing segment's terminal point (golden text convention —
  closed contours keep theirs). Result on
  text_follow_path_shape_length f0: pts counts MATCH golden on
  every verb-matched path (1337/2945, 2691/6019, 3257/7369,
  1601/3547, 778/1746, 566/1179 all exact). Residual renamed:
  TWO drawPaths diverge in VERB count — golden (2569,5745)x2
  vs ours (2691,6019): ours carries ~122 extra verbs = likely
  an extra contour emitted (or golden drops one). Plus one
  small path (12,9)g vs (10,8)o. New class: text contour
  over/under-emission, not point suppression.

- CONTOUR VERDICT DATA: the two golden (2569,5745) drawPaths map
  to TEXTIDX 51 and 57 (drawPath positions 8-9); ours emits
  (2691,6019) for them = +122 verbs each ≈ several extra
  contours per run. All other text paths now verb+pt exact.
  Suspects: whitespace/empty-glyph contour emission, or
  path-following text duplicating a glyph's contours. Probe:
  dump verb5-contour count + per-contour verb spans for
  TEXTIDX 51 vs a matching (2691) run; check textDrawPath's
  glyph loop for runs golden culls (zero-width/space glyphs
  still emitting contour geometry).

- CONTOUR OBJECTS ID'D: TEXTIDX 51/57 = type-134 Text objects
  (slots 20/26); their drawPaths come from first TextValueRun
  (type 135) child via runOverride=-1. +122 verbs each vs
  golden 2569. To discriminate duplicate-vs-real: dump the
  run's text string (135 child's string prop) + count verb5
  contours ours vs golden-implied (~2569v). If ours emits
  contours for chars golden skips (space/combining), it's a
  glyph-cull gap; if a whole run's contours duplicate, it's
  an emission-path bug in textDrawPath's run loop.

- CONTOUR CORRECTION: TEXTIDX 51 actually emits 1337/2945
  (MATCHES golden) — position-mapping was wrong. The 2691v
  drawPaths belong to a FAMILY of text objects (57,63,73,84,
  90,100,106,112,125,131,140,159,171,177 all emit 2691) —
  likely the same repeated label string. Golden expects TWO
  of them at 2569v5745p (-122v) while rest match at 2691 —
  so it's not object-identity but STATE-dependent: two runs
  in a different SM/hover state emit fewer contours (glyph
  variant or run split). Probe: which two of the 2691-family
  differ in golden order positions 7-8; check their SM state
  / TextValueRun count vs siblings.

- STATE SOURCE NAMED (strong): 15 type-134 Text objects form
  the 2691v family; textDrawPath resolves boundRunText per
  run — VM-bound text. Golden's two 2569v drawPaths are almost
  certainly two instances whose BOUND text resolves shorter
  (fewer glyphs -> -122 verbs) while ours emits template/
  same-length text. The just-landed g_instVmid/g_rowVmid
  scoping (concurrent lane) targets exactly this resolution.
  VERIFY: check which family members carry DataBind props on
  their run-135 children and whether boundRunText returns
  different strings per instance scope; if the two golden-2569
  objects are VM-bound to shorter values, the fix is already
  in flight via inst-scope — re-diff after it settles.

- VERDICT DATA: run strings DIFFER — family members carry
  125/148/58/32-char texts. Golden's 2569v drawPaths = a
  TEXT-LENGTH variant (fewer chars -> fewer glyph contours),
  NOT VM binding (boundRunText returned null for all runs —
  RIVE_TRACE_BT empty). Fixture name says it: text ON A PATH
  WITH LENGTH CONSTRAINT — golden truncates/ellipsizes runs
  exceeding the path length; ours draws full string ->
  2691v. The two 2569s = the two runs whose text overflows
  their follow-path length budget. NEXT: find the path-length
  prop (likely on the path-follower/constraint object) and
  implement char-budget truncation in textDrawPath's glyph
  loop — measure glyph advance vs path length, stop at
  budget (matches "shape_length" fixture intent).

- TRUNCATION MECHANISM PARTIAL: TextFollowPathModifier does NOT
  cull glyphs — transformGlyph positions overflow along the
  tangent (pathLength/validLength math at ~108-160), so glyph
  COUNT is decided upstream in text layout. -122 verbs ≈ 1-3
  glyph contours = likely a trailing-char/ellipsis cut or a
  line-break width constraint in text.cpp layout (paragraph
  maxWidth vs follow-path length). NEXT: check text.cpp for
  where follow-path feeds a width/char budget into shaping
  (grep maxWidth/ellipsis in text.cpp ~840 region where
  resetTextFollowPath is called), or diff the two divergent
  runs' resolved glyph sequences vs golden-implied count.

- ELLIPSIS MECHANISM NAMED: Text.overflowValue(287)=3 on ALL
  family texts; differentiator is box size (285/286 w/h dbls
  vary: h=33.1 vs 47.9). rive-cpp: wantEllipsis =
  overflow==ellipsis && overflowAsFixed -> last fitting line
  gets ellipsized -> fewer glyphs -> -122 verbs. OUR
  textDrawPath never reads 285/286/287 — no box constraint,
  no ellipsis, draws full string. The two golden-2569 runs =
  the two texts whose box fits fewer lines/chars. NEXT:
  implement overflow-ellipsis in textDrawPath's layout —
  wrap to box width(285), cap lines by height(286), replace
  tail with ellipsis glyph run when overflow=ellipsis(287=3?).

- ELLIPSIS ATTEMPT FALSIFIED: implemented overflow=3+box_w
  truncation -> over-truncated EVERYTHING (all texts -> 874v).
  Box-width-285 is NOT the constraint in our units (or texts
  follow paths whose LENGTH is the real budget — fixture name
  says shape_length). All boxes ~150w but golden truncates
  only 2 -> constraint is per-path length, not box. Reverted;
  tree clean (only concurrent g_instVmid WIP remains).
  NEXT: constraint = follow-path length — accumulate glyph
  advance vs pathMeasure length of the follow-path shape,
  truncate at budget. Find where textDrawPath learns its
  follow-path target (TextOnPath/constraint object props).

- PATH-LENGTH PROBE RESULT: TextModifierGroup.transform only
  repositions glyphs (transformGlyph per modifier) — NO culling
  anywhere in modifier path. Glyph-count delta must originate
  in the STRING or shaping, not path budget. RE-OPENED
  candidates: (a) the 148-char run variants ("...about a cat
  and a dog.") vs 125-char — maybe golden's 2569s ARE the
  148-char texts where OUR runOverride=-1 picks run0 but the
  object has 2 runs and golden draws run1 (or vice versa);
  (b) per-run string genuinely differs. NEXT: count TextValueRun
  (135) children per divergent text object — if any family
  member has >1 run, runOverride=-1 first-run-only is the bug
  (golden draws ALL runs = separate drawPaths, shifting the
  multiset). Check run counts for the 15 text objects.

- RUN-COUNT VERDICT: all 15 family texts have EXACTLY ONE
  run-135 child — runOverride hypothesis DEAD. Strings differ
  (125/148/58/32-char variants confirmed). Remaining coherent
  story: the two golden-2569 drawPaths = the two 148-char
  texts, truncated by golden's ellipsis to fit some budget;
  ours draws them full -> but ours emits same 2691v as the
  125-char texts which is itself suspicious (148 chars should
  emit MORE verbs unless our shaping caps). NEXT: verify ours'
  per-text verb counts by textIdx (RIVE_TRACE_TEXT already
  prints) — if the two 148-char texts emit 2691 same as
  125-char, our glyph loop may be dropping tail chars
  (pen/advance bug) masking the real delta; if they emit
  distinct counts, multiset alignment was coincidental.

- PER-OBJECT PROBE INCOMPLETE at context limit: TEXTIDX trace
  pairing didn't extract (stream interleave). Banked state:
  all 15 texts single-run; strings 125/148/58/32-char; ours
  emits uniform 2691v on long texts; golden wants 2 at 2569v.
  NEXT session: rerun RIVE_TRACE=1 RIVE_TRACE_TEXT=1, pair
  TEXTIDX->verbs per object, correlate to string byte-length
  (prop268 hex) -> confirms whether 148-char texts emit same
  2691 (our tail-drop bug) or distinct count (golden-only
  truncation). Then implement the named budget mechanism.

- RESUME STATE: TEXTIDX trace print was lost in the ellipsis
  revert (env-gated diagnostic, needs re-adding at emitTextDraw
  ~4760 before drawPath print). Per-object verb counts still
  unmeasured. All analysis state banked above; vertex-exact
  frontier = text contour divergence (golden 2x2569v vs ours
  8x2691v on repeated-label family, strings 125/148-char).

- PER-OBJECT VERB TABLE (RIVE_TRACE_TV, verified this session):
  ti51=1337 ti57=2691 ti63=2691 ti73=3257 ti84=3257 ti90=2691
  ti100=2691 ti106=778 ti112=1337 ti125=2691 ti131=2691
  ti140=566 ti159=2691 ti171=2691 ti177=1601.
  Golden wants the 2691-family as 6x2691 + 2x2569 -> exactly
  TWO of {57,63,90,100,125,131,159,171} must lose ~122 verbs.
  3257-pair (73,84 = 148-char texts) already exact. Remaining
  differentiator candidates: fontSize/box-width per object
  (overflow=3 ellipsis only fires when advance>box), or
  follow-path length budget. NOTE: /tmp/dops2 stale-binary
  artifact explained — fresh /tmp/dv build emits full dump.
  NEXT: dump per-text fontSize+box props for the eight
  2691-family members -> the two outliers should differ.

- DIFFERENTIATOR FOUND: of the eight 2691-family texts, exactly
  TWO — ti125 and ti131 — carry box height 286=33.10
  (0x4201c825) vs all others' 46.08 (0x42361405); width 285
  identical 150.3, sizing=2 fixed, overflow=3 ellipsis on all.
  Prime suspects for golden's 2569v pair. Mechanism: fixed
  box + overflow=ellipsis -> golden wraps to width and caps
  lines by height; shorter box -> fewer lines -> tail replaced
  by ellipsis -> -122 verbs. OUR textDrawPath does single-line
  pen-walk, no wrap/line-cap/ellipsis. NEXT: implement
  box-constrained layout in textDrawPath: wrap chars at
  t_box_w advance, cap visible lines at t_box_h/lineHeight,
  append U+2026 on the truncated last line when overflow=3 —
  verify ti125/ti131 emit ~2569v.

- CONTOUR-LEVEL VERDICT: 2691-family texts all emit 157
  contours; golden's 2569 pair shows ~151 -> golden drops
  ~6 TAIL contours (~122 verbs) = last ~6 glyphs of the
  125-char string. Consistent with line/height budget cut +
  ellipsis on ti125/ti131 (only box-height differentiator:
  33.1 vs 46.08). Implementation = wrap-at-t_box_w +
  line-cap-at-t_box_h/lineHeight + U+2026 tail in
  textDrawPath's glyph loop — feature-sized (needs line
  breaking + per-line pen reset + ellipsis glyph emit), not
  landed this leg. All simpler hypotheses dead.

- OPEN FORK before implementing: two candidate mechanisms for
  the ~6-tail-glyph drop — (a) height-budget ellipsis (box h
  33.1 vs 46.08, needs wrap+line-cap+U+2026), or (b)
  FOLLOW-PATH LENGTH glyph cull: fixture is text_follow_path;
  if ti125/131 follow shorter paths, glyphs past path length
  aren't emitted. Discriminator: check ti125/131's modifier/
  constraint children vs siblings — a TextFollowPath target
  prop or path-length difference settles it. If (b), the fix
  is measuring cumulative advance vs pathMeasure length in
  textDrawPath's glyph loop — much smaller than full
  wrap+ellipsis layout. Check children/parent props of
  ti125/131 vs ti57 first.

- DISCRIMINATOR VERDICT: golden's 2569 drawPath y-bands span
  0-30 in THREE line clusters (~0-10, 15-20, 25-30) with all
  x<160 — golden WRAPS at box width 150.3 into multiple lines;
  ours emits ONE line (y 1.9-9.5, x->467). The -6 contours =
  height cap (box h 33.1 ~ 2.x lines) dropping overflow +
  likely ellipsis tail. Mechanism CONFIRMED = full box
  layout: wrap-at-width + line-cap-by-height + overflow
  handling. This is a real text-layout feature (line
  breaking), not a cull — implementation needs per-line pen
  reset at t_box_w advance, y advance per line, stop when
  line's y exceeds t_box_h budget, emit U+2026 if overflow=3.
  Estimated scope: moderate — textDrawPath's glyph loop gains
  a line-break pass before emission.

- WRAP IMPL ATTEMPT (uncommitted->committed WIP): line-wrap +
  height-cap pre-pass landed in textDrawPath (cps/cpsLine,
  baseY per line, U+2026 on droppedTail). MEASURED: WRONG —
  ti125/131 still emit 2691 (maxLines too generous: lh from
  asc-desc+gap too small -> floor(33.1/lh)>=4 lines, text
  needs ~3-4 so nothing drops); two OTHER texts now emit
  2696 (+5 = ellipsis fired wrongly). LAY/TV diagnostic
  prints mysteriously silent on latest binary (drawPaths
  still emit — possibly stale build or early-return path;
  unresolved). NEXT: get real lineHeight (golden pitch
  ~11-13px vs computed lh) + fix maxLines formula + stop
  ellipsis firing on non-overflowing texts; verify LAY
  trace fires.

- LINEHEIGHT SOURCE: prop 370 (TextStyle.lineHeight) ABSENT
  on all runs -> font-metric default. text.cpp/line_breaker:
  lh = -asc + des where asc/des = computeLineMetrics(
  font->lineMetrics(), run.lineHeight, run.size) — hhea
  ascender/descender scaled by fontSize (my asc-desc+gap was
  close but baseline/cap formula also differs: line.top=Y,
  baseline=Y-asc, bottom=Y+des; cap likely on line.bottom vs
  box_h not floor(h/lh)). NEXT: read computeLineMetrics +
  text.cpp height-cap site (where lines beyond box are
  dropped/ellipsized — search 'ellipsisLine' usage in layout)
  -> implement exact cap -> re-diff.

- ELLIPSIS MECHANICS MAP (for next session): wantEllipsis gate
  at text.cpp:2618 (overflow==ellipsis && overflowAsFixed);
  ellipsisLine selection ~379-449 (last line that fits height);
  ellipsis RUN shaped separately ~899-944, 1084 — golden's
  2569 drawPath likely contains a shaped "…" run's contours.
  computeLineMetrics at line_breaker.cpp:27. Cap = per-line
  bottom vs box_h, NOT floor(h/lh). Implementation remains
  feature-sized: needs line records (top/baseline/bottom),
  per-line glyph x-reset, height-cap line drop, ellipsis run
  emission. WIP pre-pass at index.kz ~4706-4740 is the
  scaffold — replace maxLines floor() with per-line bottom
  check and add ellipsis-run emission.

- CAP-FORMULA SWAP = NULL RESULT (identical multiset): the
  per-line-bottom check changed nothing — combined with LAY/TV
  diagnostic silence, strongest remaining suspect is that the
  wrap branch never engages OR textDrawPath isn't the fn
  emitting these drawPaths on this binary. NEXT session FIRST
  verify LAY fires (rebuild clean, RIVE_TRACE_TV=1) — if
  silent, find the actual text emission path for drawops
  output before more layout work.

- LAY DIAGNOSTIC RESOLVED: traces need RIVE_TRACE=1 (emitOps
  gate) — earlier "silence" was missing env, not wrong fn.
  MEASURED: lh=9.68, bw=157.3; siblings bh=45.5 (~4 lines),
  ti125/131 bh=32.4 (~3 lines). 125 chars wrap to ~3 lines
  at our advances -> nothing drops; golden drops 6 contours
  -> golden wraps TIGHTER (more lines): likely letterSpacing
  on runs (text.cpp scales it into advance) or wider
  advances. ALSO: ellipsis fired on 2 wrong texts (+5v) —
  droppedTail logic needs the ellipsisLine semantics (only
  last fitting line gets "…", and only when overflow line
  exists). NEXT: check run-135/style props for letterSpacing
  key; add it to char advance; then cap+ellipsis per
  ellipsisLine rule.

- LETTERSPACING DEAD: prop 390 absent file-wide. Golden wraps
  tighter because it uses SHAPED advances (run->advances from
  HarfBuzz text.cpp:958 — includes kerning/GPOS), ours uses
  raw per-char hmtxAdvance -> systematically narrower -> fewer
  wrap lines -> height cap never bites. Closing the gap needs
  either GPOS kerning or measuring the effective advance delta
  from golden's contour x-positions (golden contour xs ARE
  the laid-out positions — diff ours vs golden per-contour x
  to derive the advance model golden used, possibly
  hmtx+constant or kern-pair table subset).

- NEXT (kerned advances): two routes — (a) parse font table
  dir for kern/GPOS presence (ttf magic scan at offset 107
  inconclusive — extract font via fontdump tor properly);
  (b) EMPIRICAL: golden contour x-positions give laid-out
  advances — compare per-line char counts: golden ~4 lines vs
  ours ~3 on 125 chars implies ~33% wider effective advance;
  test uniform scale first (cheap), kern-pair table if it
  fails. If font lacks kern/GPOS, gap may be fontScale
  (text.cpp multiplies size AND spacing by fontScale — check
  what fontScale is for these runs).

- EMPIRICAL X-DIFF ATTEMPT: naive y/11 clustering failed (V0 y
  varies per glyph, not per line). Correct route: cluster
  contours by BASELINE — each glyph contour's bottom edge y
  (max y within contour) approximates baseline; or use the
  fact golden has exactly 3-4 lines: sort contour origins by
  y then x, split where y jumps >lh/2. Then chars/line +
  xmax/line -> effective advance vs ours. STILL OPEN.

- BASELINE CLUSTER VERDICT: golden 2569 = 3 kept lines
  (baselines ~9/19/28, pitch ~9.7 = lh) + a culled 4th line;
  ~37-44 contours/line. Ours wraps 125 chars into ~3 lines
  total (bw=157.3) -> cap never engages. Golden chars/line
  ~31 vs ours ~42 -> golden wraps NARROWER: either true wrap
  width <157.3 (check which prop feeds t_box_w — LAY bw=157.3
  vs raw prop285=150.3 mismatch!) or advances wider. FIRST
  CHECK: where does t_box_w=157.3 come from vs prop 285 —
  possible wrong-prop or scale bug making our wrap too wide.

- t_box_w RESOLVED: no mismatch — prop285 decodes to
  157.31 (my earlier 150.3 was a hex misread); LAY bw=157.3
  correct. Remaining question: why golden wraps ~31 chars/
  line vs ours ~42 at same 157.3 width -> golden's effective
  advance ~35% wider OR wrap width is NOT box_w for
  follow-path text (path length / shape-length constraint —
  fixture name!). NEXT: check whether ti125/131's text has a
  follow-path modifier/constraint whose path is shorter than
  siblings' — if wrap width = path length, that's the whole
  mechanism and box_w is a red herring for this fixture.

- FOLLOW-PATH MAP: only FIVE family texts carry
  TextFollowPathModifier(547) via TextModifierGroup(159):
  texts {63,73,90,131,159} — ti125 has NONE (breaks the
  box-height pair theory: ti125's 2569 must come from a
  different cause OR golden's pair is actually two of the
  modifier texts). 547 props: P778 = u {6,1,13,84,112} —
  likely path-target ref/mode. NEXT: resolve P778 target ->
  path object -> pathMeasure length per text; the two
  shortest paths = golden's 2569 pair. If ti125 truly emits
  2569 in golden without a modifier, box-height ellipsis is
  still live for it — re-verify WHICH texts golden truncates
  by matching golden 2569 contour prefixes to specific
  textIdx (block0 vs block1 earlier: block1 matched ti125
  coords 1.4091/1.9318 — CHECK block0's first coords vs
  ti131/others to assign both 2569s definitively).

- ATTRIBUTION DATA: all family texts emit IDENTICAL contour
  sequences (same string) — coords can't distinguish members.
  BUT golden's two 2569 blocks have DIFFERENT y-offsets:
  block0 baseline ~y39, block1 ~y2 -> different box heights
  or valign -> the pair is NOT uniformly {125,131} short-box.
  Follow-path path-length attribution gains weight. NEXT:
  resolve 547-P778 targets -> path objects -> lengths; two
  shortest = golden pair. ALSO: block0's ~39 y-offset may
  match a 45.52-box text's valign positioning — cross-check
  golden 2691 blocks' y-offsets per box-height group to learn
  golden's valign convention (needed anyway for coord parity).

- P778 RESOLVED: TextTargetModifier.targetId — values
  {6,1,13,84,112} are path-target ids for modifier texts
  {63,73,90,131,159} respectively (order: 72->63? verify
  group->text map). NEXT: map each targetId to its path
  object (shape/path vertex list), measure path length via
  existing pathMeasure/flattenPath machinery; texts on the
  two shortest paths = golden's 2569 pair; wrap width for
  follow-path text = f(path length) per text.cpp — find
  where paragraph maxWidth derives from follow-path
  (text.cpp ~840 resetTextFollowPath junction) then feed it
  into t_box_w in the wrap pre-pass.

- text.cpp WIDTH CHECK: follow-path does NOT feed layout
  width — modifiers run post-layout (computeCoverage +
  resetTextFollowPath at ~835, AFTER shaping). Paragraph
  maxWidth = effectiveWidth() = box width for fixed sizing.
  So golden's narrower wrap is NOT path-length-derived via
  layout. Reopened: (a) shaped/kerned advances still the
  advance-gap candidate; (b) glyph culling may live in the
  DRAW stage (~940-1090 curX/advances loop) where follow-path
  glyphs beyond path end skip path emission — contour count
  drops without layout change. NEXT: read text.cpp ~940-1090
  for a path-length/coverage check around glyph path emission.

- DRAW-STAGE CULL CHECK: text.cpp ~1040-1090 is hit-rect/
  background bounds + curX advance — NO path-length skip.
  Follow-path glyph positioning is transformGlyph-only
  (already exonerated). Every cull mechanism now measured
  dead; the surviving explanation for -6 contours is WRAP
  DENSITY: golden's shaped advances (HarfBuzz, kerned) are
  wider -> 4+ lines -> height cap drops tail. That makes the
  fix = advance model, not culling. Bounded next step:
  measure golden advance empirically — per-line contour
  count*avg-advance vs ours; or extract font, check kern/GPOS
  tables via fontdump.

- FONT TABLES: embedded font HAS kern@6278 + GPOS@192.
  No type-409 layout objects (not layout-managed width).
  Kern alone (~10-15% typical) probably can't explain ~33%
  advance gap BUT could tip 2.9->3.2 lines over the boundary.
  CHEAPEST DECISIVE TEST before implementing kerning: apply
  uniform advance scale factor k to wrap math only (glyph
  coords unchanged), sweep k in {1.05,1.1,1.15,1.2} -> if any
  k makes ti125/131 drop to ~2569v while siblings stay 2691,
  the mechanism is advance-width and exact k can then be
  sourced (kern sum or fontScale). ONE build+4 runs settles
  it vs full GPOS implementation.

- SWEEP VERDICT — MECHANISM CONFIRMED: RIVE_ADV_K=1.045-1.05
  makes the ENTIRE static section verb+pt EXACT vs golden —
  only residual is unrelated (12,9)g vs (10,8)o small path.
  ti-pair emits exactly 2569v; all siblings hold 2691v.
  Advance model gap is real and uniform ~+4.7%. NEXT: find
  the actual source — candidates: fontScale prop on run,
  upem/scale rounding, or golden advance = hmtx + fixed
  letter gap. Check text.cpp fontScale computation + whether
  run carries a scale prop; implement REAL advance (not the
  env k) then remove RIVE_ADV_K hook. NOTE: advK currently
  only scales WRAP pre-pass advance, not pen/emission —
  coords still match because wrap only decides line breaks.

- K-SOURCE INVESTIGATION: fontScale DEAD (text.cpp:2253 —
  only fitFontSize overflow=5 scales; ours are overflow=3).
  Other text fixtures (new_text, runtime_nested_text_runs)
  have unrelated emission gaps (ours 4-10 drawPaths vs gold
  9-14) — k universality UNPROVEN, can't validate there.
  k~1.047 remains unexplained: kern usually NEGATIVE
  (narrows), can't explain wider wrap. NEW SUSPECT: our
  advance may MISS something golden includes — e.g. space
  advance, or hmtxAdvance returns wrong field, or golden
  advance = hb shaped advance including mark/attachment
  offsets. NEXT: dump our per-char advance list for ti125's
  string + golden's implied per-line char counts -> solve
  for the per-char advance model directly.

- ADVANCE DUMP: upem=2816 (unusual), scale=0.00284, fs=8.0.
  Glyph coords match golden to 0.001 -> scale CORRECT, so
  per-glyph advances are correct too -> k~1.047 is NOT a
  scale bug. Effective golden wrap width ~= 157.31/1.047 =
  ~150.2 — suspiciously close to round 150. HYPOTHESES:
  (a) golden wrap width = box_w minus inset/padding (~7px),
  (b) positive kern pairs add ~4.7% (kern CAN be positive;
  avg +40u*0.00284*124pairs ~ +14px/line-group — plausible),
  (c) wrap width comes from a different prop. NEXT: check
  kern table format-0 presence + measure actual kern delta
  on this string in python (extract font via fontdump->file);
  also test RIVE_WRAP_W env override at 150.0 — if verb-exact,
  width-source is the answer not advances.

- WRAP_W=150 VERDICT — ATTRIBUTION SETTLED: ti125+ti131 emit
  exactly 2569v/5746p (golden 5745 — +1pt residual only).
  The pair IS the short-box texts; width-source confirmed
  over kern (uniform wrap width reproduces golden exactly).
  Remaining: WHERE does 150 come from — box_w=157.31, delta
  7.31. Candidates: layout-assigned width (rows?), box_w
  minus inset, or prop 288 (=400 only on ti125/131 — check
  its prop name in table). ALSO: pts +1 residual — wrapped
  text's final-segment suppression may need the same
  textDrawPath convention applied per-line.

- WIDTH SOURCE FOUND (text.hpp:349): effectiveWidth() =
  isnan(m_layoutWidth) ? width() : m_layoutWidth — when a
  LAYOUT controls the text, wrap width = layout-assigned
  m_layoutWidth (~150), NOT authored width()=157.31. That
  IS the 150. No type-409 seen earlier — layout participant
  may be another type or nested-artboard layout; find which
  object parents ti125/ti131 in the layout tree and what
  slot width the layout solve assigns. Implementation:
  textDrawPath's t_box_w should read the layout-resolved
  width when a layout participant exists (mirror
  layoutBoxWidth/layoutParticipant logic), else prop285.

- PARENT MAP: all 15 family texts share parent obj25 (the
  artboard/container) — uniform parent means width source is
  SHARED; per-text divergence is purely box HEIGHT (32.45
  drops line 4, 45.52 keeps it). Model coherent: all wrap
  at ~150, short-box pair culls tail. 150 likely = layout/
  artboard-derived width uniform across family — resolve
  obj25's type + any layout/clip width ~150, or check if
  prop285's 157.31 minus artboard inset gives 150. NEXT:
  identify obj25 type_key and its width props.
