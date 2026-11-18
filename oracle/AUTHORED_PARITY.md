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

## Per-artboard attribution — resolved: ancestor opacity (2026-11-18)

The car_widgets over-draw was **ancestor opacity**. `WorldTransformComponent
.opacity`(18) multiplies down the transform tree and 0 hides the subtree; we
only read opacity on the Shape itself. TIRE PRESSURE's red band sits under a
Node with `opacity = 0.000`, so we drew every element of a hidden branch — and
that branch is why our palette was red where the reference's is green.

Per artboard, frame 0, before → after (`rive/index.kz`, commit "propagate
ancestor opacity"):

| artboard | ref | before | after |
|---|---:|---:|---:|
| Main_Artboard | 612 | 809 | **628** (+16) |
| TIRE PRESSURE | 68 | 254 | **73** (+5) |
| COMPASS | 413 | 417 | 417 (+4) |
| G_Meter | 69 | 66 | 66 (−3) |

TIRE PRESSURE's strokes are now exact (15/15) and its colour histogram matches
the reference's greens draw for draw. `joystick_databound_keyframe_test`
remains op-identical, so the fix introduced no regression there.

## How that was found (worth keeping)

Five rounds of predicate-sweeping produced a confident, wrong answer: "the
drawn set is the paints whose colour is keyframed" reproduced 54 of 53 fills,
and it was an artifact — the hidden branch happened to be the keyframed one.
What broke the false lead was testing it against the artboards that already
matched (COMPASS, G_Meter): a rule that requires a global cull would have
under-drawn them, so the rule had to be wrong. A correlation that reproduces
one file's number is not a rule until it survives the files that already work.

## The clip gap is the next lever (2026-11-18, measured)

With the digests compact (the harness now prints counts, not full bboxes),
data_viz Main makes the clip gap obvious:

| | draws | clips | fills/strokes |
|---|---:|---:|---|
| reference | 199 | **38** | 172/27 |
| ours | 170 | **3** | 144/26 |

So ~35 clips are missing on Main alone. Nested-instance content is the likely
source: rive-cpp clips a nested artboard to its own bounds, and our expansion
pushes the instance matrix but never the matching clip — so instance content
that overflows its rect paints over its siblings. Implementing that is a
contained change in the nested-expansion block (emit the instance bounds as
clippush/clippop around the recursive collect).

Two other things from this round, recorded so they are not re-tried blindly:
- Changing the text colour default from `0xFF313131` to black makes the harness
  report a *different* divergence layer for data_viz (geometry instead of
  drawable-count), so the default is load-bearing somewhere and the change was
  reverted. It needs its own probe, not a speculative edit.
- The harness now prints a compact per-side summary instead of dumping whole
  digests — the dump once buried the line that mattered in 14 KB of bboxes.

## Remaining deltas

- Main +16 and TIRE PRESSURE +5: the leftover is `747474` default-colour
  paints (14 in TIRE PRESSURE) that the reference either does not draw or draws
  with a colour we resolve as the default. Next class to chase.
- COMPASS +4 / G_Meter −3: small, same colour-default family.
- data_viz −29: `ForegroundLayoutDrawable`(513), blocked on layout solving.
- car_widgets' clips: feather path-effects, not `ClippingShape`.
- jellyfish: mesh file (243 mesh verts, 121 tendons).


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

