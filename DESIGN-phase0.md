# Phase 0 design notes — canvas vector verbs (from session reads, 2026-11-16)

## Golden op set the verbs must express (oracle/goldens/*.txt)

Ops emitted by rive-native per frame: `save`, `restore`,
`transform a b c d e f` (Mat2D, 6 floats), `clipPath`,
`drawPath(style,color,thick,join,cap,blend,shader,fillRule)`,
`drawImage`, `modulateOpacity`. Path geometry: verbs
move=0 line=1 quad=2 cubic=4 close=5 (Skia values) + x,y point pairs.
Paint: fill(1)/stroke(0) style, RGBA color, stroke thickness/join/cap,
blend mode, optional shader (gradient/image — v2), fillRule
(even-odd=2 observed).

## Canvas architecture (oshun/canvas/index.macos.kz, ~3076 lines)

- Verbs are `~pub tor name { args }` decls + `~proc name|zig` Zig bodies.
  The part files ARE Zig host code — "Koru" surface, Zig implementation.
- Draw model: CPU emits `GpuInstance` structs (extern struct, 16B-aligned
  fields: rect[4], color[4], border_color[4], uv[4], clip[4], radius,
  border_width, kind, clip_round, silk[4]) into `f.insts` array;
  `instFlush` packs them into a shared MTLBuffer and draws ONE instanced
  quad call (`pso_inst`, 4 verts × n instances) — fragment shader does
  SDF eval per instance kind.
- inst kinds: quad=0 text=1 shadow=2 image=3 glass=5 frost=6 stroke=7
  gradient=8 gradient_radial=9. Kinds 8/9 unimplemented on koru-native —
  "refuses at compile, not silently" is the established loud-fail pattern.
- Non-instance draws (draw.triangle, draw.bezier?) call `instFlush(f)`
  first, then `setRenderPipelineState(f.pso)` + `drawPrimitives` —
  direct vertex path exists alongside instancing.
- Clips: `f.clip_stack` + `f.clip_depth`; `curClip(f)` reads innermost;
  `clipRound(f)` packs rounded-clip. Only rect/roundrect clips today.
- Frame fields seen: device, encoder, pso, pso_inst, insts, clip_stack,
  clip_depth, text.atlas, images.texture, scene_tex, time, vp_w, vp_h,
  flushed, plus window/surface plumbing elsewhere in file.
- Opaque-handle precedent: `image.load { path } | img i64 | err string`,
  `image.free { tex: i64 }`, `font.load` — i64 pointer handles with free
  verbs. Path handle should follow this shape.

## Proposed verb surface (v1, matches golden ops)

Path construction (handle lifecycle = the obligation story):
- `path.open {} | p *Path<open!> | err string` — allocates recording path
- `path.move { p: *Path<open!>, x, y }` — stays open!
- `path.line { p: *Path<open!>, x, y }`
- `path.quad { p: *Path<open!>, cx, cy, x, y }` (control + end)
- `path.cubic { p: *Path<open!>, c1x, c1y, c2x, c2y, x, y }`
- `path.close { p: *Path<open!> }`
- `path.end { p: *Path<!open> } -> *Path<built!>` — discharge open, issue built
- `path.free { p: *Path<!built> }` — consume

Drawing:
- `draw.path { f: *Frame<frame>, p: *Path<built>, fill_r,g,b,a,
  stroke_r,g,b,a, stroke_w, join, cap, fill_rule, even_odd? }`
  — or split `draw.path.fill` / `draw.path.stroke`? DECIDE: golden paint
  carries style+color+thickness together → single verb with both paint
  param sets, zero-values = off, mirrors draw.panel precedent.
- `transform.push { f: *Frame<frame>, a,b,c,d,e,f6: f64 }` /
  `transform.pop { f: *Frame<frame> }` — CTM stack on Frame.
  v1 impl: CPU-bake into path points at draw.path/clip.push.path emit
  (no shader change); honest scope note in verb doc.
- `clip.push.path { f: *Frame<frame>, p: *Path<built> }` — arbitrary
  clip; needs clip representation upgrade (today clip_stack entries are
  rect[4]+radius — path clip needs either stencil or rasterized mask;
  DECIDE: v1 may do scissor-from-bbox + fragment path-test is NOT
  possible in instanced quad model → likely needs the direct-draw path
  with stencil, OR defer clip.push.path to v1.5 and land
  transform.push/pop + draw.path first).

## Metal implementation sketch (the hard part)

Arbitrary path fill needs tessellation: flatten quad/cubic → line
segments (de Casteljau, tolerance ~0.25px) → polygon → ear-clip
triangulation → vertex buffer → draw with pso (non-instanced path,
instFlush first like draw.triangle). Stroke: offset-curve tessellation
is the hard version; v1 could do stroke via inst_stroke-style thick
quads only for quads? NO — honest v1: fill only + stroke via tessellated
stroke outline (or defer stroke, fillRule+fill first). DECIDE at write
time; fill-first is the steelman.

## koru-native part

Same decl signatures; bodies refuse loudly (compileError/panic naming
the missing rasterizer path — SDF model can't do arbitrary paths;
polygon coverage is its own project per commission phase 4).

## Still open

- Exact `part` decl mechanics for adding verbs (read index.kz part
  blocks + how index.macos.kz/index.koru-native.kz join).
- Whether Frame struct lives in a shared header both parts see
  (transform stack + clip_depth fields must exist in both).
- Zig-side path storage: page_allocator vector of verb/point pairs,
  i64 handle = pointer (image.load precedent).

---

## OUTCOME — phase 0 landed differently than sketched (oshun 36d20fc + 1910d4c)

The sketch assumed Metal tessellation + phantom handles. What shipped:

- **Backend: CoreGraphics rasterization, not Metal tessellation.** The
  sketch's hard part (ear-clipping, stroke offset curves, stencil fill
  rules) is CG's home turf — `CGPath` → `CGBitmapContext` → BGRA pixels →
  the SAME atlas→instanced-quad pipeline `draw.image` already proves.
  Fill rules, joins, caps, AA come correct for free; a native tessellator
  remains the documented optimization, not a correctness gap. One real
  bug found en route: `CGContextDrawPath` consumes the CONTEXT's current
  path — a standalone `CGPath` is inert until `CGContextAddPath`.
- **Handles: i64, not phantom.** `path.open` mints a 1-based index into a
  module-level `PathData` registry — `image.load`'s custody shape. The
  `*Path<open!>`→`*Path<built!>` phantom ladder is still the aspiration
  but the declaration mechanics for custom phantom types were never
  located in-tree; i64 is proven syntax. Upgrade is signature-level.
- **Transform stack: per-frame CTM on `Frame`.** `transform.push/pop`
  hold `[6]f64` affines (16 deep, loud panic on overflow/underflow —
  NOT clip.push's silent drop). Consumed by `draw.path` rasterization
  only; retrofitting CTM onto the ~50 primitive verbs is contract work,
  documented as such — not hidden.
- **clip.push.path: deliberately absent.** Rect `clip_stack` cannot
  express arbitrary path clips; doing it right needs mask/stencil
  infrastructure (rasterize clip → mask texture → shader-side test).
  Named gap, not worked around.
- **koru-native: zero new decls** → compile-time refusal, the
  `draw.gradient` precedent.

### Verbs shipped (macOS part only)

```
path.open {} -> i64
path.move/line { p, x, y }   path.quad { p, cx, cy, x, y }
path.cubic { p, c1x,c1y,c2x,c2y,x,y }   path.close { p }
path.reset { p }   path.free { p }
transform.push { f, a,b,c,d,e,g }   transform.pop { f }
draw.path { f, p, fr,fg,fb,fa, sr,sg,sb,sa, sw, join, cap, evenodd }
```

join: 0=miter 1=round 2=bevel; cap: 0=butt 1=round 2=square (CG numbering).
evenodd != 0 selects even-odd fill (Rive fillRule=2). Zero paint alpha
disables that paint — draw.panel's border convention.

### Verified

`canvas/tests/path_probe.k` — koruc -c + full build + run; snap BMP
pixel-read: fills, stroke, quad/cubic, CTM translate+scale+nested push,
evenodd vs nonzero all at expected positions/colors. NOT yet verified:
hidpi raster scale (1.0 unit=1px), clip.push.path, gradient shaders,
per-frame re-raster cost under animation load.

---

## Component-slot model — CONFIRMED against hello_world.riv data

`claimsArtboardSlot`: Core default false; `Component` override true;
`Artboard` false BUT its import does `objects().addObject(this)` first —
the artboard is slot 0 of its OWN list. ScriptInput* types also claim.
Slots = index into the owning artboard's `objects()` list, assigned in
STREAM ORDER among claiming objects only (assets/anims/states don't
claim). Failed imports still hold their slot (ids stay aligned).

Verified resolution on hello_world (slots: 0=Artboard obj[3], then
objs[4..10] in stream order = slots 1..7):
- Text parentId=0 → Artboard ✓
- TextValueRun parentId=1 → Text; styleId=2 → TextStylePaint ✓
- SolidColor obj[6] parentId=6 → Fill obj[9] (paint belongs to fill) ✓
- SolidColor obj[8] parentId=7 → Fill obj[10] ✓
- Fill obj[9] parentId=2 → TextStylePaint ✓
- Fill obj[10] parentId=0 → Artboard (background fill) ✓

NEXT IMPLEMENTATION: extract `class XBase : public YBase` parents from
generated/*_base.hpp → isComponent = descendant of ComponentBase;
decoder assigns slots per artboard (reset on each Artboard object),
resolves parentId + styleId (component-slot space) to obj indices;
other *Id props (animationId, stateToId, artboardId, fontAssetId…)
each have their OWN id spaces — enumerate per-prop before resolving.
Then path vertex storage via a shape-bearing fixture
(component_list_*.riv found in tests/unit_tests/assets/).

## Hierarchy extraction — gotcha found (2026-11-16)

Generated base headers declare `class ArtboardBase : public LayoutComponent`
— parents are CONCRETE names (no "Base" suffix) pointing at the class the
base mixes into; normalize parent+"Base" → file <snake>_base.hpp. First
extract attempt returned 0 classes: regex expected "Base" suffix on
parents. isComponent = chain reaches ComponentBase.

## Path vertex storage — CONFIRMED on follow_path_shapes.riv

Paths are OBJECT GRAPHS, not packed blobs:
- `PointsPath` (parent→Shape): `PointsCommonPath.isClosed` (key 32, bool)
- Vertex children (parent→PointsPath, stream order = path order):
  `Vertex.x`/`Vertex.y` (keys 24/25, f32) + per-type tangent props —
  CubicMirroredVertex: rotation(82)/distance(83); StraightVertex,
  CubicVertex, CubicAsymmetricVertex, CubicDetachedVertex carry their
  own. Vertex TYPE selects the segment kind (first = moveTo).
- `ParametricPath` subclasses (Rectangle etc.) are procedural:
  width(20)/height(21)/radius — NOT vertex lists; the player must
  synthesize their geometry or the oracle shows what rive emits.
- Forward refs confirmed real: SolidColor→Fill resolves post-pass.

## Schema extraction bug found by fixture #2

camel(filename) lost interior capitals: `interpolating_keyframe` →
"InterpolatingKeyframe" ≠ class "InterpolatingKeyFrame" → its props
never entered propField (propKey 68 desynced component_list_1 at obj62).
Fix: read `class X` name from each header. propKeys 638→680,
components 152→171 (hierarchy.json regenerated).

## Transform eval — VERIFIED exact on unconstrained nodes

Composition (transform_component.cpp:63-82): local =
fromRotation(rot) with [4]=x,[5]=y then scaleByValues(sx,sy)
(m[0,1]*=sx; m[2,3]*=sy — translation UNSCALED); world =
parentWorld * local, root = local. Node.x/y = keys 13/14,
rotation=15, scaleX/Y=16/17 (radians, defaults 0/1/1).
isNodeType = 33 typeKeys descendant of NodeBase (hierarchy.json).

VERIFIED: hello_world Text world transform = 73.4805 175.7852 —
byte-identical to golden. follow_path_shapes deltas (+100y, small
rotation on scaled shapes) are CONSTRAINT effects: constraints run
in updateConstraints() AFTER composeWorldTransform — FollowPath/
IK solving is player-eval scope, named gap not a bug.

## Player-leg remaining map
- t=0 static: transforms(done) → buildPath tangent math → paints
  (Fill/Stroke→SolidColor/gradient) → golden-format emitter → diff
- animation: KeyedObject/KeyedProperty/KeyFrame* interpolation
- constraints: FollowPath/IK/TransformComponentConstraint solvers
- text: glyph paths from embedded font (hello_world is ALL text —
  biggest single subsystem; needs font parsing + glyph outline extract)
- images: DrawableAsset → drawImage

## Animation model (mapped 2026-…, follow_path_shapes)

Flat stream, parentId=-1 — linkage is by ID props, not parenting:
- LinearAnimation (fps=56, duration=57, speed=58, loop=59, workStart/End=60/61)
- KeyedObject.objectId (51) — component-slot ID of target (same slot space as parentId)
- KeyedProperty.propertyKey (53) — the animated prop key (363 = FollowPathConstraint.distance here)
- KeyFrame.frame (67), InterpolatingKeyFrame.interpolationType (68), interpolatorId (69)
- Values: KeyFrameDouble.value (70 f2), KeyFrameColor.value (88 f3), KeyFrameBool (181), KeyFrameString (280), KeyFrameId (122)
- Runtime applies via CoreRegistry::setColor/setDouble(object, propertyKey, v) — writes the live property; interpolated between surrounding keyframes (type 1 observed).
- follow_path_shapes' LinearAnimation animates ONLY FollowPathConstraint.distance (6 keyed objects) — the ff747474 colors come from STATE-MACHINE animations (nested/blend), not this linear anim. Constraint solving still required to turn distance into shape transforms.

## Constraint solver semantics (follow_path_constraint.cpp + path_measure.cpp)

- FollowPathConstraint props: distance(363 f2, KEYFRAMED 0→1.0),
  orient(364 f4), offset(365 f4), strength(172), targetId(173).
- PathMeasure.atPercentage(p) = atDistance(totalLength * clamp01(p))
  — distance is a FRACTION of arc length, not pixels. Keyframes
  animate it 0→1 = 0%→100% of path.
- targetTransform(d): pos+tangent at d → transformB = target's
  worldTransform, orient→rotate toward tangent (strength-blended),
  offset→parent translation, [4,5]=pos+offset.
- constrainHelper: decompose A(component world) + B(target),
  blend x/y by strength t, keep A's rotation (if !orient)/scale/skew.
- Needs: ContourMeasure flatten (cubic→polyline at tolerance) +
  cumulative arc length + pos/tan interpolation — the missing math
  piece. Keyframe eval: frame units, fps prop 56, interpType 1=linear.

## ContourMeasure (skia-inspired, contour_measure.cpp)

- Contour = vector<Segment> + vector<Vec2D> pts + length + isClosed.
- Segment: {distance(cumulative start), ptIndex, type(2bit: line/quad/
  cubic), tValue} — built by walking RawPath verbs, chopping cubics at
  tolerance (m_invTolerance = 1/max(tol, kMinTolerance)).
- Length via wangs_formula per segment; findSegment = lower_bound on
  cumulative distance (skips zero-distance segs).
- PosTan eval per segment type at local t (eval_quad/eval_cubic +
  line) → pos + unit tangent.
- PathMeasure.atPercentage(p) = atDistance(length*clamp01(p));
  atDistance → findSegment → eval → pos/tan.
- Koru port shape: build from my PV/buildPath V-stream (verbs+pts
  already emitted) — flatten cubics to quads/lines OR keep cubics and
  eval analytically (eval_cubic gives exact pos+tan — no flatten
  needed if we keep segment params!). Skia chops for bounds; for
  follow-path only pos+tan matter → analytic eval per verb segment
  with cumulative EXACT-ish length (Wang's formula per segment).

## State-machine eval path (state_machine_instance.cpp et al.)

- sm->advanceAndApply(dt): per-layer StateMachineLayerInstance advances
  its LayerState (Entry/Exit/Animation states), transitions gated by
  SMI inputs (SMIBool/SMINumber/SMITrigger) + transition conditions.
- AnimationState wraps LinearAnimationInstance(s); NestedLinear/
  NestedSimple/NestedRemap wrap sub-animations with mix/speed/time;
  BlendAnimation* mix multiple animations by weight.
- Each active animation instance applies its KeyedObject/KeyedProperty/
  KeyFrame values via CoreRegistry::set*(object, propertyKey, v) —
  same write path my keyframedValue models, but TIME BASE + MIX +
  WHICH-ANIMATION-IS-ACTIVE are SM-decided, not a single timeline.
- follow_path_shapes divergence hypothesis: SM selects/nests the
  LinearAnimation with nonzero time offset or blend — OR a different
  animation object plays. Next: dump the SM's layer/state/animation
  instance graph for this fixture (state names, animationIds, mixes)
  and compare the played animation's keyframe timeline vs my
  keyframedValue(363) assumption.

## follow_path_shapes SM graph (decoded)

StateMachine[217] -> StateMachineLayer[218] -> EntryState[219],
StateTransition[220] (stateToId=3), ExitState[221], AnyState[222],
AnimationState[223] (animationId=0 -> LinearAnimation obj[190]).
SM DOES play our LinearAnimation — selection confirmed. Divergence
is therefore in TIME BASE or INTERPOLATION, not selection:
- interpType=1 semantics unresolved (linear vs eased — check
  interpolating_keyframe.cpp effectiveInterpolator +
  keyframe_interpolator.hpp)
- fps prop absent -> default; duration default 60 frames; loop=1
- candidate: cubic ease interpolator on the keyframes, or
  advanceAndApply time != frame index * (1/fps)

## interpolationType (key 68) — open

m_InterpolationType default 0; fixture keyframes carry 1.
Consumer not yet located (property decl only so far) — likely read
in keyed_property/linear_animation_instance apply path or selects
hold-vs-interpolated segments. NEXT: grep interpolationType() call
sites in src/animation/, then port easing if cubic.

## interpolationType RESOLVED (keyed_property.cpp:192)

interpType==0 -> HOLD (apply fromFrame value verbatim);
!=0 -> applyInterpolation (lerp via interpolator; interpolatorId
absent -> default linear). Fixture keyframes are type 1 =
interpolated — my linear lerp shape is CORRECT. Divergence is NOT
interp type. Remaining: `seconds` time base — KeyedProperty works
in SECONDS (toFrame->seconds()); KeyFrame.frame -> seconds via
animation fps at instance setup; advanceAndApply dt accumulates
seconds; mix/blend weights may scale actualMix. NEXT: read
linear_animation_instance.cpp time->frame mapping + fps source.

## LinearAnimationInstance time base — partial

Instance carries m_time (seconds, accumulated by advance). fps
source + frame<->seconds conversion still unread (file's apply
path is bind/holder-heavy). mix/actualMix scaling unread.
NEXT: grep 'fps' across src/animation + artboard advance path;
KeyFrame.frame is in FRAMES, toFrame->seconds() implies conversion
at keyed-property build time (fps from animation or artboard).

## TIME BASE FOUND (linear_animation_instance.cpp:317-362)

m_time += deltaSeconds; frames = m_time * fps; fps =
animation.fps(). advanceAndApply(dt=1/30) -> frame f maps to
anim-frame f*fps/30. fps default still unconfirmed (m_fps not in
generated base — check linear_animation.hpp or core default).
loop=1 wraps at duration (60 frames default). If fps=60:
golden f15 -> anim frame 30 — my RIVE_FRAME=30 test SHOULD have
matched; divergence therefore likely fps!=60, loop/work-area
clamping, or mix scaling — verify fps value next.

## fps=60 CONFIRMED (linear_animation_base.hpp:32)

m_Fps default 60 -> golden f15 == anim frame 30 mapping was CORRECT.
Loop::loop wraps at duration end (60); workStart/workEnd absent ->
full range; frame 30 is mid-loop, no clamp. Divergence therefore
NOT time-mapping, NOT interp, NOT selection -> remaining: actualMix
blend scaling (AnimationState mix / NestedLinear mix) or the
keyframe->seconds conversion inside keyed_property (frame->seconds
may use a different fps than playback). NEXT: read keyed_property
frame->seconds + AnimationState mix defaults.

## frame->seconds + mix — still open at context limit

KeyedProperty applies in seconds; conversion likely lives on
KeyFrame (frame->seconds via fps at instance build). Mix defaults
unread. The bug is therefore probably NOT in keyframedValue's math
but in WHICH time value reaches it — e.g. SM applies animation at
mix<1 or a nested time remap. NEXT SESSION: instrument — print
distance(t) my eval produces at frames 0/15/30/45/60 vs the
positions golden frames imply; if monotonic-but-wrong, it's mix;
if wrong-shape, it's time base.

## frame->seconds CONFIRMED equivalent (keyframe.cpp:10)

m_seconds = frame / fps (fps=60) — identical math to keyframedValue's
frame-space lerp. ALL math suspects eliminated: selection, interp
type, time mapping, frame->seconds. Divergence must be in WHAT the
SM actually applies per advance: state transitions mid-run (the SM
has StateTransition/AnyState — states may change which animation
or pose is active across the 30 frames), mix<1 blends, or trigger
inputs firing. NEXT: instrument distance(t) per frame + check
whether golden frame ops show DISCONTINUITIES (state jumps) vs
smooth motion — discontinuity => transition, smooth-but-offset =>
mix/time.

## Frame-motion discriminator: SMOOTH LOOP, no transitions

Golden frame transforms trace a continuous closed loop (408,298 ->
... -> 396,298 over 30 advances) — the constrained shape rides the
CLOSED PointsPath once per loop (distance 0->1 = full perimeter,
loop=1 wraps at frame 60 = advance 30). No discontinuities => no
SM transitions; motion is pure LinearAnimation. Divergence is
therefore INSIDE my eval at distance>0: static (distance=0) matched
29/30 because path-start is exact; at distance=0.5 my 16-chord
cubicLen approximation accumulates length error vs Skia's Wang's-
formula segment lengths -> arc-fraction maps to wrong position.
NEXT: port wangs_formula cubic length (include/rive/math/
wangs_formula.hpp) into cubicLen — the only remaining math gap.

## Keyframe uniformity confirmed

All 6 KeyedObjects: prop 363, identical keyframes (frame0 default
-> frame60 value 1.0) => distance(t)=t/60 uniform across
constraints. NOT the divergence source. orient (364) animation
status still unchecked (truncated listing).

## Remaining divergence hypothesis

pm.pos oracle-exact but transforms diverge on cubic-path nodes
only (line-path nodes match: 8/24 = the rect/square-target
groups). Suspect: tangent direction or the targetTransform orient
branch for CURVED paths — eval_cubic tangent vs my cubicTan, or
angleB wrap semantics (C++ fmod vs my wrapPi on angleB+diff).
NEXT: print pm.tan + final cB.rot per constraint vs golden
transform decompose — isolates tangent-vs-compose.

## cB.rot diagnostic (frame 30)

node102=3.024 (golden decompose ~3.030, delta 0.006)
node2=1.571, node22/42/62=-3.142 (pi-wrap equivalent),
node82=2.658. Positions oracle-exact. Residual rotation delta
~0.006 rad on cubic paths -> tangent eval difference: eval_cubic
uses ENDPOINT DIFFERENCING at t==0/1 (contour_measure.cpp:76+)
vs my cubicTan derivative everywhere; at path ends tangent can
differ. Also possible: angleB fmod vs wrapPi edge at +-pi.
NEXT: port eval_cubic's t==0/1 differencing into cubicTan call
site (posTan needs both pos+tan from same eval).

## component_list_default_state_machine — second falsifier mapped

Golden structure: artboards=2 (Main + Row); 3 frame-groups of 30
(sm0 all-empty; two populated groups each 1 drawPath/frame).
Populated op: ff57a5e0 rect 100x40, verbs=6 pts=4, identity
transform + local coords (0,0)-(100,40).

My player ALREADY emits the rect statically (color ff57a5e0 exact,
geometry matches modulo known close-line pts delta) — divergence
is STRUCTURAL not math: golden's sm0 frames are EMPTY (component
list populates Row instances via ViewModel/default-state timing);
my drawops emits unconditional static ops per artboard and has no
per-SM/per-artboard visibility or component-instantiation model.

New object types in this fixture: ArtboardComponentList,
ViewModelInstance, ViewModel, LayoutComponent, StateMachineNumber,
ViewModelPropertyNumber — the component-list subsystem is the
next frontier (instantiation + VM property binding + SM gating).

## Instantiation chain decoded (component_list_default_state_machine)

ViewModel[1](name) + ViewModelPropertyNumber[2] + ViewModel[4]
+ ViewModelPropertyList[5]
 -> ViewModelInstance[3](viewModelId=0), [6](viewModelId=1)
 -> ViewModelInstanceList[7](viewModelPropertyId=0)
   -> ViewModelInstanceListItem[8](viewModelId=0, instanceId=0)
 -> Artboard[9](viewModelId=1, defaultSM=0, 200x200)
   -> LayoutComponent[11](styleId=3)
     -> LayoutComponentStyle[12](flexDirection=0, margin/pad units=1)
     -> ArtboardComponentList[13]  <- instantiates per list item
 -> Artboard[20] at x=300 = Row (Shape22+Rectangle23 = ff57a5e0 100x40)

ONE list item -> ONE Row instance -> the single drawPath/frame.
sm0 empty = Main artboard's own SM draws nothing; populated
groups = instantiated Row content (+ possibly a second SM section).
DataBindContext[14] binds source paths (VM->component props).

## Section structure + instantiation link confirmed

Golden emits PER-ARTBOARD sections: static + smN frame groups.
sm0 appears twice (two artboard contexts), sm1 once.
Artboard[20] Row: viewModelId=0 == ViewModelInstanceListItem
.viewModelId=0 -> THE instantiation link (list item selects which
VM-bound artboard materializes). defaultStateMachineId=1 (Main=0).

Flat-traversal drawops already emits all content unconditionally —
the REAL structural gap is per-artboard x per-defaultSM sectioning:
emit each artboard's static ops, then its default SM's 30 frames.
sm0's empty frames = Main artboard draws nothing itself (its only
content is the component list, which instantiates Row — Row's own
section is the populated one).

## Per-artboard ordering — partial finding

Object stream is already artboard-clustered: component_list
emission order = Main ops (transform 0,0) then Row ops (300,0) —
matches golden's per-artboard section ORDER without restructuring.
Remaining gap is purely FRAME SECTIONING: golden repeats each
artboard's ops under its default SM's 30 frames (sm0 empty for
Main, populated for Row); my drawops emits one frame per call.
Next leg: emitArtboardOps(abIdx, frame) extraction + frame loop
in dumpDrawOps (static + smN x f=0..29, anim frame = f*2 @fps60).
owningArtboard() helper landed (uncommitted->committed next).

## Instantiation-transform answer (artboard_component_list.cpp)

ArtboardComponentList::draw (line 2047) renders each row INSIDE
the list's own draw pass using worldTransform() + layout pass —
instantiated components draw in the INSTANTIATOR's section at
layout position, NOT as separate artboard sections. RowPass::
advance/settle (1569-1721) advances each row's own SM instance.
=> golden's populated groups = Row artboard's OWN section
(defaultSM=1, identity/local coords); Main's sm0 empty because
Main's SM produces no direct draws AND the dump records per-SM
sections, while row content appears under whichever section
advances the list. The 300,0 offset = instantiation layout pos,
distinct from Row's own-section identity transform.
