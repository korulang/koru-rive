# Authored-file parity — first named layers (snapshot 2026-11-18)

`oracle/authored_parity.py` runs the reference recording renderer and our
`kr/rive:opsdump` on the same authored file, digests both, and names the first
layer that differs. This is the snapshot of the first full run; regenerate with

    python3 oracle/authored_parity.py            # demo set, human output
    python3 oracle/authored_parity.py --json      # machine use

| file | artboard | first divergent layer | ref draws | ours draws | ref clips | ours clips |
|---|---|---|---:|---:|---:|---:|
| joystick_databound_keyframe_test | Main (11) | drawable-count | 2 | 1 | 0 | 0 |
| car_widgets_v01 | Main_Artboard (90) | drawable-count | 69 | 71 | 7 | 0 |
| jellyfish_test | Jellyfish (47) | paint (313131 vs 747474) | 1 | 1 | 1 | 1 |
| data_viz_demo | Main (315) | drawable-count | 44 | 3 | 8 | 1 |
| inventory_demo_test_v2 | — | **ref-unavailable** (rive-cpp asset importer assert) | — | — | — | — |

Every tuned fixture is 30/30. Every authored file diverges at the *structure*
layer, before state machines, inputs, or time are involved.

## Three systematic gaps, not four unrelated bugs

1. **Clips are dropped.** car_widgets: reference emits 7 `clipPath`, ours 0;
   data_viz: 8 vs 1. Consequence: content that should be masked paints outside
   its region. This is the single most repeated divergence in the set and the
   cheapest to fix.

2. **Drawable presence is wrong in both directions.** joystick loses one (2→1);
   data_viz loses almost everything (44→3); car_widgets gains two (69→71).
   A shared traversal rule is wrong, not three separate drawables. Candidate
   discriminant: the joystick's missing drawable is the one whose `SolidColor`
   carries **no colour property at all** (`props=1`) and therefore paints with
   rive-cpp's `SolidColorBase` default `0xFF747474` — that default is applied
   correctly elsewhere (`rive/index.kz:3019`, `:3555`), so this looks like a
   path where a shape is skipped rather than defaulted.

3. **Colour fallback fires where the file has a colour.** car_widgets ours emits
   `747474` six times where the reference resolves `000000`/`ffffff`; jellyfish
   ours emits `747474` where the reference emits `313131`. Since `747474` *is*
   the documented default, each of these is a colour property we failed to read
   — the decode gap is real but narrow: the property exists, we resolve the
   default instead.

## One structural imbalance worth its own probe

jellyfish: reference `xform` 2 / `restore` 2, ours `xform` 25 / `restore` 25
with only 2 `save`s. Our transform push/pop bookkeeping is not the reference's:
we push per node where the reference pushes per drawable group. This will
scramble any transform-level comparison even after draws match.

## Instrument notes

- The artboard is resolved **by name** from `abnames`. `ab` is an object index;
  a wrong index does not error, it emits a plausible degenerate stream. Never
  compare without the name check.
- `oracle/dump` cannot open `inventory_demo_test_v2.riv` (rive-cpp asserts in
  `file_asset_importer.cpp:25`). The commission's primary candidate needs the
  dumper's file-asset callback fixed before it can be a reference target.
- The digest compares drawable count/paint, clip count, save/restore balance,
  transform count, and geometry volume. It deliberately does not compare point
  coordinates yet — geometry comparison is the next slice, and false precision
  here would hide the structural gaps above.

## Update — the colour-default fix (same day)

`propColor` returned `0` for an absent colour key, so any `SolidColor` with no
explicit `colorValue` resolved to alpha-0, and the alpha-0 cull deleted the
drawable. rive-cpp's `SolidColorBase::m_ColorValue` default is `0xFF747474`
and it draws with it. Added `propColorOr`/`propColorAnimOr` and applied them at
the four `SolidColor` colour-read sites (`rive/index.kz`), leaving the global
`propColor` default alone.

Effect on the smallest repro:

| joystick (708 B) | draws | colours | first divergent layer |
|---|---|---|---|
| before | 1 | 282828 | drawable-count |
| after | 2 | 282828, 747474 | save/restore (ref 3/3, ours 2/2) |

The drawable-count and paint layers now match the reference. Remaining on that
file: save/restore grouping (the reference wraps each drawable in an extra
save) and geometry volume (ref 11 points, ours 9). A fill-rule difference is
also visible in the raw stream — our second draw emits `eo=1` where the
reference prints `fillRule=2` — not yet investigated.

Regression status: **incomplete.** The pixel gates are static comparisons
against committed renders, and `run_gates.py --only hw` reports `[STALE]`, so
it validates the stored images, not this change. The colour default touches
every fill, so a full re-render pass of the gates is required before claiming
no regression.

Also note: this harness is for *authored* files. On tuned fixtures such as
`component_list_follow_path` our emit includes component-list rows that the
reference dumper does not drive, so the two streams are not comparable and the
harness reports a large false divergence. Do not use it as a fixture gate.


## Snapshot after nested-artboard expansion (2026-11-18, later)

`rive/index.kz` now expands `NestedArtboard`(92)/`NestedArtboardLeaf`(451)/
`NestedArtboardLayout`(452) recursively, resolving `artboardId`(197) as an
**index into the file's artboard list** (`File::artboard(size_t)`) — matching
it against `Artboard.viewModelId`(583) had expanded wrong subtrees by
coincidence.

| file | ref draws | ours before | ours now | first layer |
|---|---:|---:|---:|---|
| joystick_databound_keyframe_test | 2 | 1 | **2** | **op-identical** |
| data_viz_demo (Main) | 199 | 3 | 170 | drawable-count (≈ -29 = ForegroundLayoutDrawable, layout-blocked) |
| car_widgets_v01 | 612 | 72 | 809 | drawable-count (over-expansion, unmatched) |
| jellyfish_test | 2 | 1 | 1 | mesh file — 243 mesh verts / 121 tendons; the known mesh worklist |
| inventory_demo_test_v2 | — | — | — | ref-unavailable (rive-cpp asset importer assert) |

Net absolute error improved on both expanded files (data_viz 196→29,
car_widgets 540→197). car_widgets now *over*-draws: colours the reference never
emits (`ff0000` ×50, `350000` ×36, `1f1717` ×16) with 80 default `747474` and
50 fewer `000000`. Not yet attributed; the class-3 finding (gradient paints)
covers the colour half, and the over-draw is a separate culling question.

## Per-artboard attribution (`--all-artboards`, re-measured 2026-11-18 21:10)

car_widgets_v01, frame 0, after nested expansion and with a working toolchain:

| artboard | ref draws | ours | delta | Shapes | ref clips |
|---|---:|---:|---:|---:|---:|
| Main_Artboard | 612 | 809 | +197 | 74 | 7 |
| TIRE PRESSURE | 68 | 254 | **+186** | 226 | 0 |
| COMPASS | 413 | 417 | +4 | 369 | 0 |
| G_Meter | 69 | 66 | −3 | 61 | 0 |

COMPASS and G_Meter are essentially exact — traversal and paint resolution are
sound. **TIRE PRESSURE is the outlier**, and Main's +197 is that same content
propagated through the nested instance (186 + neighbours).

Measured facts about the delta:

- The reference draws **68 even in its `static t=0` block**, before any advance,
  with the same colours as frame 0. So this is the **base pose**: not a state
  machine transition, not an animation, not time.
- 226 Shapes, **all** have a Fill/Stroke child.
- 116 objects carry `WorldTransformComponent.opacity` (key 18); **none is 0**.
- Exactly **one** `ShapePaint.isVisible` (key 41) exists, and it is `false`.
- **Zero** `KeyedProperty` objects in the file key opacity (18).
- No `Solo`(147) components in any artboard.
- 226/226 shapes' parent chains reach the artboard — no orphans.
- 27 path objects carry `pathFlags`; hidden contours cannot explain 158.
- Only **12** of the 210 extra draws fall entirely outside the artboard rect,
  so a cull rect is not the rule either.
- car_widgets has just **4** `LayoutComponent`s — one per artboard — so the
  earlier "layout" reading of this delta was wrong; layout is data_viz's
  problem (`ForegroundLayoutDrawable`), not car_widgets'.

Identity comparison settles the shape of it: matching each draw by
(transform matrix, colour, style) instead of by bbox, **52 of the reference's
68 draws match ours exactly**, 16 are reference-only, and 202 are ours-only. So
the reference's set is mostly a subset of ours — an over-draw of ~3x, not a
different scene.

**A correction worth recording:** an earlier reading said the extra draws
"cluster at the origin" and inferred un-laid-out content. That was wrong —
the bbox coordinates in the digest are the drawable's **local path** bounds, not
its world position. Reading the matrices instead shows every draw at a real
gauge position (728,655 / 984,1051 / 617,564 …), with **zero** draws near the
origin. Both the layout reading and the cull-rect reading were artifacts of
reading local coordinates as world ones.

What the 202 extras share is still unidentified. Colour does not separate them
(the artboard's base `SolidColor`s are red-dominant, its keyframe palette is
red-dominant, and the reference's 68 are greens — so colour selection differs
independently of membership), and no shape property we decode splits 68 from
226.

**Cull-rule sweep (run, then scaffolding removed).** A temporary
`RIVE_CULL_RULE` switch skipped shapes by candidate property and counted the
resulting draws, against the reference's 53 fills + 15 strokes:

| rule | fills | strokes | total |
|---|---:|---:|---:|
| none | 199 | 55 | 254 |
| skip shapes that set `blendModeValue`(23) | 97 | **16** | 113 |
| skip shapes without it | 137 | 39 | 176 |
| skip shapes with `rotation`(15) | 163 | 55 | 218 |
| skip shapes with `scaleX/scaleY`(16/17) | 126 | 38 | 164 |

No single shape-level property reproduces the reference. The near-miss is
informative: filtering on `blendModeValue` leaves **16 strokes against a target
of 15**, while fills only fall to 97 against 53. That asymmetry says the
remaining rule is **per paint, not per shape** — one shape can carry both a fill
and a stroke, and the reference's stroke set is nearly explained while its fill
set is not. Next probe: apply the candidate predicates to the *paint* child
(`Fill`/`Stroke`, its gradient vs solid kind, and its keyed colour during the
static pose) rather than to the shape.

Note for reproducibility: the first sweep used wrong property keys (rotation is
15, not 14; `blendModeValue` is 23, not 26) and its numbers were discarded.

Per-**paint** predicates then landed it. Same harness, rules applied to the
`Fill`/`Stroke` child instead of the shape (target: 53 fills + 15 strokes):

| rule (keep only…) | fills | strokes | total |
|---|---:|---:|---:|
| paints whose colour is **keyframed** | **54** | 10 | 64 |
| paints whose colour is *not* keyframed | 180 | 45 | 225 |
| gradient paints | 45 | 27 | 72 |
| keyframed **or** gradient | 64 | 37 | 101 |
| keyframed **or** stroke | 54 | 55 | 109 |
| keyframed **and** gradient | 35 | 0 | 35 |

**The drawn set is the keyframed-colour paints.** That rule reproduces 54 of
the reference's 53 fills — off by one — where no shape-level rule came within
a factor of two. Strokes come out 10 against 15, and the likely reason is
`hasKeyframed`: it matches keyframe groups by *slot*, which is exactly the kind
of lookup that under-matches on stroke paints. So the rule is probably right
and the detection is slightly narrow.

Interpretation: at the static pose the artboard draws the elements that
participate in its active animation; paints with no animation participation are
not drawn. For a gauge whose every visible element is animated, that is a
coherent authoring style rather than a Rive-wide rule — **so this must be
validated on the other artboards and files before it becomes a decoder cull.**


Related, and needed for nested instances specifically: each carries a
`NestedStateMachine` child (`NestedAnimation.animationId`), so a nested
instance's state comes from the *instance*, not from the target artboard's
default state machine. Expansion currently calls `smActiveAnimIdx(target, …)`,
which asks the artboard, not the instance.

Related, and needed for the nested instances specifically: each carries a
`NestedStateMachine` child (`NestedAnimation.animationId`), so a nested
instance's state comes from the *instance*, not from the target artboard's
default state machine. Expansion currently calls `smActiveAnimIdx(target, …)`,
which asks the artboard, not the instance.

## Recommended order (revised after the fix)

1. **Save/restore grouping** — the remaining joystick divergence, and the same
   root cause as jellyfish's 25-vs-2 transform count. One rule, several files.
2. **Feather clip emission** — the car_widgets "7 vs 0 clips" is not a clip
   bug: car_widgets has zero `ClippingShape` objects and 452 `Feather`s, so
   those clips come from `shape_paint.cpp`'s inner-path insets. Feature-sized.
3. Geometry volume (ref 11 points, ours 9 on the smallest file).
4. Colour property *decode* on the objects that still fall back to `747474`
   where the reference resolves a real colour (car_widgets, jellyfish).
5. Fill-rule agreement (`eo` vs `fillRule`), then state machines and the
   timeline.

