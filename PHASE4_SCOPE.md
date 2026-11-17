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
