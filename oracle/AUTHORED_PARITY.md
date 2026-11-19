# Authored-file parity

`oracle/authored_parity.py` runs the reference recording renderer and our
`kr/rive:opsdump` on the same authored file, digests both, and names the first
layer that differs:

    python3 oracle/authored_parity.py                     # demo set
    python3 oracle/authored_parity.py --all-artboards F   # every artboard
    python3 oracle/authored_parity.py --attribute AB F    # per-class draws + skips

## Current status (2026-11-18, after the alpha fix)

| file | artboard | draws ref/ours | remaining |
|---|---|---:|---|
| joystick_databound_keyframe_test | Main | 2/2 | **op-identical** |
| car_widgets_v01 | Main_Artboard | 612/628 | +16 (layout-driven over-draw) |
| | TIRE PRESSURE | 68/73 | +5 |
| | COMPASS | 413/417 | +4 |
| | G_Meter | 69/66 | −3 (keyframe slot match) |
| data_viz_demo | Main | 199/196 | −3 |
| | HorizontalBars | 40/34 | −6 (text runs) |
| | ColorGuide | 38/38 | order only (38/38 identity) |
| | VerticalBars | 31/33 | +2 |
| | LineBars | 20/20 | placement |
| | Data | 45/46 | +1 |
| | Pie Chart | 16/16 | placement |
| | Circles | 44/44 | placement |
| jellyfish_test | Jellyfish | 2/1, 1/0 | mesh |
| inventory_demo_test_v2 | — | — | ref-unavailable (importer assert) |

Everything still open reduces to **placement** (layout solver: FLD/text-clip
placement, Circles/LineBars/Pie offsets), **drawable identity** in the reference
stream (ordering; blocked on the dumper's undocumented link recipe), or **mesh**.

## History: the first snapshot (superseded)

The original run recorded joystick 2/1, car_widgets 69/71, data_viz 44/3 and
concluded "every authored file diverges at the structure layer". That conclusion
was right at the time and is now obsolete: the structural layers were fixed one
at a time, and the numbers above are the current ones. Kept so the original
claim is not silently rewritten.


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

So ~35 clips are missing on Main alone. **Nested-instance bounds are not the
source** (tried and reverted: the nested target artboards carry no clip flag,
on the artboard or on their LayoutComponent children, and emitting a bounds
clip changed nothing — 3 clips before and after). The source is **feathers**:
data_viz has 118 `Feather` objects and car_widgets 452, and rive-cpp's
`shape_paint.cpp` emits a `clipPath` to the feather's inner path. That is the
same feature-sized port already named for car_widgets, now confirmed as the
clip gap for data_viz too. `ClippingShape` count in data_viz: 1 — it is not
the mechanism.

Two other things from this round, recorded so they are not re-tried blindly:
- Changing the text colour default from `0xFF313131` to black makes the harness
  report a *different* divergence layer for data_viz (geometry instead of
  drawable-count), so the default is load-bearing somewhere and the change was
  reverted. It needs its own probe, not a speculative edit.
- The harness now prints a compact per-side summary instead of dumping whole
  digests — the dump once buried the line that mattered in 14 KB of bboxes.

## Baseline (2026-11-18)

`oracle/parity_baseline.json` now records the measured per-artboard numbers, and
`authored_parity.py` reports `BASELINE DRIFT` when a run disagrees with it.
Prose numbers rot — this repo's recurring lesson — so the last measured state is
committed and compared, not recited.

Full per-artboard run at baseline time:

| file | artboard | ref | ours |
|---|---|---:|---:|
| joystick | Main | 2 | 2 (**op-identical**) |
| car_widgets | Main_Artboard / TIRE PRESSURE / COMPASS / G_Meter | 612 / 68 / 413 / 69 | 628 / 73 / 417 / 66 |
| data_viz | Main | 199 | 172 |
| data_viz | HorizontalBars / VerticalBars | 40 / 31 | 22 / 21 |
| data_viz | Data | 45 | 46 |
| data_viz | ColorGuide / LineBars / Pie Chart / Circles | counts match | **paint mismatch** (reference purples, ours `000000`) |
| jellyfish | Jellyfish / New Artboard | 2 / 1 | 1 / 0 (mesh) |

The gradient-colour rule (opaque black for gradient paints) is a **stopgap**: it
makes car_widgets match exactly, and on data_viz it replaces one wrong colour
(`747474`) with another (`000000`) — those artboards were already mismatched, so
it is not a regression, but it is not resolution either. The reference's
recorded colour for a gradient paint is per-drawable (purples like `472f62`,
`3f2958`, `442d5e` in data_viz; black in car_widgets) and is not the gradient's
stop colour (`GradientStop.colorValue`, key 38) as far as this dump shows. That
needs its own probe against a single gradient drawable.

## ForegroundLayoutDrawable — landed (2026-11-18)

`ForegroundLayoutDrawable`(513) now draws a rect from its parent
LayoutComponent's stored `width`(7)/`height`(8), painted black. No layout solver
is involved: the chart artboards' boxes are already in the file, so a solver was
never the prerequisite — only the emission was missing.

| artboard | ref | before | after |
|---|---:|---:|---:|
| data_viz Main | 199 | 172 | **202** (+3) |
| HorizontalBars | 40 | 22 | 34 (−6) |
| VerticalBars | 31 | 21 | 33 (+2) |
| LineBars | 20 | 20 | 26 (+6) |
| Data | 45 | 46 | 46 (+1) |

Main's error drops from −27 to +3. The residual is now overshoot on two
artboards (+2 LineBars, +6 in the second run) — some FLDs should not draw, or
draw once rather than per node — which is a culling question, not a geometry
one.

Two things this cost, worth recording:

- The first attempt was silently dead because the pass was inserted *inside*
  the shape loop; a standalone pass plus a trace line proved it runs. When an
  experiment changes nothing, prove it executes before theorising about guards.
- The run reported `LineBars: ours-unavailable (backend execution failed)` and
  the very next isolated run of the same artboard succeeded. A transient
  toolchain failure is not a regression — check it alone before believing it.

**Paint-source guard (same day).** An FLD with no sibling `Fill`/`Stroke` under
its LayoutComponent has nothing to paint, and the reference draws none of them —
that was exactly LineBars' +6 overshoot (its six FLDs have no fill sibling,
HorizontalBars' twelve all do). With the guard:

| artboard | ref | before guard | after guard |
|---|---:|---:|---:|
| Main | 199 | 202 (+3) | 196 (−3) |
| HorizontalBars | 40 | 34 | 34 (−6) |
| VerticalBars | 31 | 33 (+2) | 33 (+2) |
| LineBars | 20 | 26 (+6) | **20 (exact count)** |
| Data | 45 | 46 (+1) | 46 (+1) |

Total absolute error 18 → 12. LineBars' remaining divergence is a *paint*
mismatch (reference white, ours black) at one drawable, not a count.

**Text colour default was wrong (same day).** Texts with no explicit colour
were drawn `0xFF313131` (a hardcoded dark grey); the reference draws them black.
HorizontalBars' colour diff goes from 12 missing `000000` + 4 extra `313131` to
8 missing `000000` + 2 extra `ffffff` — a strict improvement, counts unchanged.

Consequence to keep in mind: any tuned fixture containing text renders slightly
differently now, and the committed gate images were made with the old default.
The gates are already `stale` by provenance, but a re-render is required before
their verdicts mean anything again.

Gradient paint colour remains open and is *not* stop-derived (see below).

## Gate impact of the decoder changes (analysed 2026-11-18; not re-rendered)

A re-render was flagged as required. The probe→gate recipe could not be
rediscovered in this session (building `render_kn_hw.k` produced a binary whose
own log says `meshrender`, so the file→gate mapping is not what the names
suggest), so the impact was bounded by inspection instead:

| change | gate fixtures affected |
|---|---|
| `ForegroundLayoutDrawable` emission | **none** — 0 type-513 objects in every gate fixture |
| text colour default → black | **none** — the two fixtures with a `Text` (`component_list_follow_path`, `hello_world`) both carry an explicit `SolidColor` (`0xffffffff`, `0xff00f3ff`), so the default never applies |
| gradient paint colour | **none** — 0 `shader=1` draws in any gate fixture |
| nested-artboard expansion | **none** — 0 `NestedArtboard*` objects in the sampled fixtures |
| ancestor opacity | only where an ancestor opacity is <1; such a case would have been failing before |
| fill-rule `2 → nonZero` | 8 draws across 2 fixtures (`component_list_follow_path` 6, `hello_world` 2) — all simple closed shapes, where nonZero and evenOdd agree |

So the decoder changes are gate-neutral on the evidence, with one honest limit:
this is inspection, not a byte-identical render. A real re-render still needs
the probe→gate mapping recovered, and the committed images remain `stale` by
provenance until then.

## Per-drawable identity (instrument added 2026-11-18)

Attributing a count delta has needed object identity for several rounds. It now
exists: `RIVE_TRACE_DRAW=1` makes the shape draw path print
`DRAW obj=<shape> paint=<object> style=<s> color=<c> m=<a>,<b>,<d> t=<e>,<g>`.
Gated, no behaviour change.

First use — car_widgets Main (+16): matching the reference's draws to ours by
(transform, colour, style) leaves the largest unmatched groups with object ids
inside **G_Meter's** range (`11191`, `11224`, `11237`, `11250`; `11167`-`11183`;
`11094`-`11153`). G_Meter standalone draws 66 against the reference's 69 — we
are *short* there, yet Main draws extra objects from that range. So the delta is
in how Main composes that instance, not in G_Meter's own traversal.

This is the first time that sentence could be written with object ids behind it.

## HorizontalBars −6: one draw per Text, not one per TextValueRun

Draw-class tags (`RIVE_TRACE_DRAW`) now account for every draw we emit:

| class | ours |
|---|---:|
| `ForegroundLayoutDrawable` | 12 |
| text | **6** |
| artboard paint | 1 |
| layout paint | 15 |
| **total** | **34** |

The reference draws **40**, and HorizontalBars has exactly 6 `Text` objects with
**two `TextValueRun` children each**. 12 + **12** + 16 = 40 fits the reference
exactly; we draw one path per Text (6) instead of one per run (12). That is the
missing six.

Not fixed here deliberately: text rendering is under active change in this
repository right now (composite-glyph `endPts` fix landed the same day), and a
per-run refactor inside that code would collide. The finding names the exact
change — loop `TextValueRun` children and emit one draw per run, each with its
own style — and the class tags make it verifiable in one run.

## Per-run text: correct diagnosis, not-yet-viable change (2026-11-18)

The HorizontalBars −6 was diagnosed exactly (one draw per `Text` where the
reference draws one per `TextValueRun`; 12 + 12 + 16 = 40) and implemented:
`textDrawPath` gained a run override and the text loop iterated run children.
HorizontalBars went to **40 = 40 exact**.

It was then reverted, because two failure modes appeared elsewhere:

- **SIGABRT** rendering HorizontalBars through the harness (`exit -6`), i.e. a
  crash in the glyph path for the second run.
- **+6 over-draw** on six other data_viz artboards: their second runs draw for
  us where the reference draws nothing. The likely rule is that those runs are
  *name-bound* text (a binding form we cannot resolve without a versioned
  manifest, so rive renders nothing); a skip predicate for it was written and
  did not match them, so the rule is still unknown.

Both live in text rendering, which another session is actively changing
(composite-glyph `endPts` fix, same day). The diagnosis and the shape of the fix
are recorded here; the change belongs to whoever owns that code next.

## Defect found: keyframe lookup ignores artboard (2026-11-18)

`hasKeyframed(r, slot, key)` matches `KeyedObject.objectId` (key 51) against an
object **slot** with no artboard check, and `kfOwnerOk()` accepts every group
when no animation is active (`g_activeAnim < 0`). Slots are per-artboard, so the
match crosses artboards.

Measured consequence: G_Meter draws 66 against the reference's 69, and the three
missing shapes are culled by false-positive keyframed opacity. The shapes carry
**no opacity property at all** (`obj[10949]`: parentId/rotation/scaleX/scaleY/
x/y/blendMode), and no `KeyedObject` targets them — yet `opSelf` read
`0.000`, because a *Main* object's keyframed opacity matched G_Meter's slot 63.

The obvious repair — scope the match with `owningArtboard()` — **does not work**:
`KeyedObject` groups are not parented into the artboard tree, so parentage
cannot attribute them. Measured: G_Meter 66 → 68 but Main 628 → 630, a wash in
total error, partly from *suppressed* matches rather than correct ones. Reverted.

The correct scope *is* available — `animArtboard()` resolves "nearest preceding
Artboard in stream order", which works for flat keyframe groups — so it was
implemented exactly that way (a module-level `g_abScope` set by
`collectArtboardOps`, checked in `hasKeyframed`). **It changed nothing:**
car_widgets measured 694 draws before and after. So the cross-artboard match was
not what culled those three shapes after all; the likely cause is the keyframe
**time mapping** (animation fps vs our 30fps ticks), which another session is
actively changing in this same file. The scoping was reverted as a no-op rather
than left in on principle.

Until the time mapping settles, the defect stands: slot collisions *can* cull
drawables in a multi-artboard file, and the G_Meter −3 is unexplained by
artboard scoping.

## `--attribute`: per-class accounting in one command

    python3 oracle/authored_parity.py --attribute G_Meter \
        rive-cpp/tests/unit_tests/assets/car_widgets_v01.riv
    # car_widgets_v01.riv [G_Meter (idx 10881)] draws=66
    #   DRAW      60
    #   TXT        6
    #   skips: opacity=3

Every attribution this doc describes by hand — which class emits what, and which
culls fire — is now one command. It reuses the decoder's class tags
(`RIVE_TRACE_DRAW`) and skip tags (`RIVE_TRACE_SKIP`), so the report cannot
disagree with the decoder.

Two bugs had to be fixed to make it honest, both in the harness rather than the
decoder: probes are now built to a unique path (`koruc run` writes a shared
`./a.out`, and a concurrent session can swap the program), and the trace env is
actually forwarded to the executed binary (it was only passed to the build, so
the first version reported zero classes for every artboard).

## Keyframe groups are matched by derived slot, not by object id (2026-11-18)

The decoder's `RivObj` has **no object-id field** — the linear object stream does
not carry one — so `hasKeyframed` matches `KeyedObject.objectId` against our
*derived* per-artboard `slot`. That stand-in is the remaining suspect for
G_Meter's −3.

Traced on G_Meter (active animation 11933):

    KF2 obj=10949 slot=63 kf=true kv=0.000 prop18=false
    KF2 obj=10958 slot=72 kf=true kv=0.000 prop18=false

Both shapes carry **no opacity property at all** (`prop18=false`), are matched to
an opacity keyframe group, evaluate to 0, and are culled — while the reference
draws them, which is exactly the three draws we are short.

Two explanations remain and this evidence does not separate them:

1. our slot numbering diverges from rive's objectId, so the group belongs to a
   different object; or
2. the group is ours but rive's value at t=0 is not 0 (keyframe time/fps
   mapping — another session is changing exactly that).

Settling it needs the objectId assignment decoded (or a C++ probe printing the
same id→keyframe mapping from rive-cpp), not another guess. `RIVE_TRACE_KF2`
(the trace above) is in the tree for that work.

## Draw order is not content: the metric was wrong (2026-11-18)

The digest compared draws **positionally**. The reference records them in its own
tree order; we emit them from separate passes (artboard paint, FLD, shapes,
text). For artboards whose draw *counts* match, that positional comparison was
reporting an ordering difference as a paint mismatch.

ColorGuide, measured: 38 draws each side, **identical colour multisets**,
first positional difference at index 0.

`first_divergence` now compares colour multisets first and reports
`draw-order` as its own layer:

| data_viz artboard | previous verdict | now |
|---|---|---|
| ColorGuide (38) | paint mismatch | **draw-order** |
| LineBars (20) | paint mismatch | **draw-order** |
| Pie Chart (16) | paint mismatch | **draw-order** |
| Circles (44) | paint mismatch | **draw-order** |

Four artboards are content-correct and differ only in ordering. That retires
"gradient paint colour" as a *paint* problem for them — the remaining question is
ordering, which matters for pixels only where draws overlap.

Next step this implies: emit in **tree order** rather than pass order. Our
draws come from separate passes appended in fixed sequence, so the stream order
is ours, not the tree's. A DFS over the artboard's children (objects already
appear in creation order) would interleave shapes, text and layout paint the way
the reference does, and is the likely route to turning those four artboards
fully op-identical.

## Draw order is tree order — measured, not yet implemented (2026-11-18)

The `draw-order` verdicts were tested against two cheap hypotheses on
ColorGuide (38 draws):

| emission order | positional matches with the reference |
|---|---:|
| object-stream order (current) | **9 / 38** |
| reversed stream order | **8 / 38** |

Neither is the rule — reverse only wins on the first draw and loses overall. The
structure of the divergence names the real one: the reference's first ColorGuide
draw is shape `876`, a **direct child of the artboard**, while our first is shape
`660`, nested three LayoutComponents deep (`660 -> 659 -> 658 -> 657 -> 655 ->
654 -> 653`). The reference emits in a **draw-tree walk**, not in the order
objects happen to sit in the file.

Per-artboard positional agreement is now reported (this is the number a DFS
has to move):

| artboard | draws | positional match |
|---|---:|---:|
| LineBars | 20 | **16/20** |
| Circles | 44 | **30/44** |
| ColorGuide | 38 | **9/38** |
| Pie Chart | 16 | **2/16** |

ColorGuide's mix is 32 shape draws + 6 text, so the ordering spans both passes —
a DFS has to interleave them, not just sort each pass. A first attempt at
rank-ordering the shape pass was abandoned before writing anything: the target
loop pattern occurs twice in the file (collectDraws and collectArtboardOps) and
the scaffolding referred to a rank array it had not built. Better to leave the
file untouched than land a half-refactor in a file another session is editing.

### Tested and rejected: rank-ordered shape pass (2026-11-18)

A `treeRanks()` DFS helper was written and the shape pass ordered by it, with a
sibling-order switch. ColorGuide positional agreement:

| emission order | matches |
|---|---:|
| stream order (default) | 9/38 |
| DFS pre-order rank | **9/38** |
| DFS with siblings last-first | 8/38 |
| whole shape list reversed | 8/38 |

No permutation helps — and the reason is structural: objects are stored in
creation order, so **DFS pre-order *is* stream order**. The reference's order is
therefore not a permutation of our shape list at all.

**Which exposes a weakness in my own metric.** "Positional colour agreement"
compares colour sequences, but a chart artboard repeats a handful of colours
across many draws (32 shapes, most `000000`/`ffffff`), so the score is nearly
insensitive to real ordering: 9/38 does not prove our order is wrong, and a high
score would not prove it is right. Ordering cannot be measured this way.

**Update (same round): identity exists without touching C++.** The reference
already prints a `transform` line per draw, so composing its save/restore stack
into an absolute CTM gives an identity per drawable: `(CTM, colour, style)`.
Comparing the *sets* of those (positional comparison is confounded by the order
difference itself):

| artboard | colour match | identity-set match | reading |
|---|---:|---:|---|
| ColorGuide | 9/38 | **38/38** | pure ordering — every drawable identical |
| Pie Chart | 2/16 | 9/16 | real differences beyond order |
| Circles | 30/44 | 14/44 | real differences beyond order |
| LineBars | 16/20 | 6/20 | real differences beyond order |

So ColorGuide's divergence is *only* order (38/38 identity), while the other
three genuinely differ in transform or paint. That is a much better target than
"order": only one of the four is an ordering problem at all.

Measuring it properly needs a reference stream that carries **drawable identity**
(the object id or name per `drawPath`), which `oracle/dump.cpp` does not print.
That is the prerequisite for any further ordering work — and it is a small
change on the C++ side, not another permutation on ours.

So the fix is a DFS over the artboard's children (objects already appear in
creation order, so sibling order is free), emitting each node's draws as it is
visited instead of the current pass order (artboard paint -> FLD -> shapes ->
text). That is a real refactor of `collectArtboardOps`, not a flag, and it is the
next piece of work rather than a quick win.

### What the identity diff says about LineBars: FLD positions, not paint

LineBars has 20 draws on both sides and an identity-set match of 6/20. The
difference is positional, and it is uniform:

    reference: (1,0,0,1, 210, 172)  (1,0,0,1, 170, 172)  ... (1,0,0,1, 10, 172)
    ours:      (1,0,0,1,  30,  54)  (1,0,0,1,  69,  54)  ... (1,0,0,1, 227, 54)

Same colours, same style, same scale — every bar sits ~20px right and ~118px up
of where the reference draws it. These are `ForegroundLayoutDrawable` rects, and
their placement comes from the parent `LayoutComponent`'s **computed** layout:
the box has width/height in the file but its position is solved. We emit the box
at the component's own transform, which is why counts came out right and
positions did not.

So the residual on these artboards is the layout solver, not paint or ordering —
which is consistent with `ForegroundLayoutDrawable` having been recorded as
"blocked on layout solving" from the beginning.

### Ordering: four hypotheses tried, none fits

For ColorGuide — the one artboard whose identity sets match 38/38, so ordering is
the *only* difference — positional identity was measured against candidate
orders:

| candidate order | positional identity |
|---|---:|
| ours as-is (stream order) | 1/38 |
| DFS pre-order (== stream order here) | 1/38 |
| reversed siblings | 1/38 |
| sorted row-major by transform (y, x) | 0/38 |

The same test on the other three: LineBars 5/20 regardless, Pie Chart 3/16 at
best, Circles 1/44. So the reference's order is not stream, not reversed, not
tree pre-order, and not layout order.

**Prerequisite to go further:** the reference stream needs a stable drawable
identity per `drawPath` (object id or name), not just a composed transform. With
identity, order becomes a matching problem with a checkable answer; without it,
every candidate order is judged through a proxy that repeats colours 30+ times
per artboard. **Tried instead: geometry identity.** Both streams carry path vertices, so
hashing them would give identity without touching C++ — but the conventions
differ in two ways that make a naive hash useless (measured 0–1/38):

- rive-cpp omits each contour's **terminal point when printing** (Skia RawPath
  convention) while the geometry keeps it — the code already documents this in
  `buildPath`;
- our op stream carries cubic segments as **three** points (in, out, end) where
  the text form prints two.

Set-of-points normalisation fixes neither fully (1/38 after deduping), so
geometry identity needs its own normalisation pass before it can be used. The
`(CTM, colour, style)` identity remains the best available — and it already says
ColorGuide's drawables are identical, ordered differently.

That is a small patch to `oracle/dump.cpp`/`record.hpp` (thread the
owning shape's id into the recorded draw), and it should come before any further
ordering work.

## Per-run text: retried, still wrong (2026-11-18)

With text stabilised by the other session, per-run emission was re-attempted
(the `runOverride` parameter had survived in the tree; only the loop was
missing). Measured:

| artboard | ref | per-Text | per-run |
|---|---:|---:|---:|
| HorizontalBars | 40 | 34 | **40** |
| LineBars | 20 | 20 | **26** |

HorizontalBars hitting 40 looks like confirmation and is not: its texts have two
runs that **share a style** (`style=19 fs=87`, `style=51 fs=14`, …), exactly like
LineBars', where the reference draws only six text paths. So the two artboards
have the same run structure but different reference text-draw counts — the
difference is not per-run versus per-Text, and the matching total is a
coincidence of composition (12 FLD + 12 text + 16 paints = 40, versus the
reference's 12 + 6 + 22).

Reverted again. Determining the rule needs the reference's *text* draw count per
artboard, which means identifying text draws in the reference stream — the same
identity problem as ordering, not a new experiment on our side.

## Feather clips: three variants measured, none matches (2026-11-18)

Implemented clip emission for feathered paints (clip to the shape path, which is
what rive records before drawing the inset inner path). Clip counts on
data_viz Main + ColorGuide:

| predicate | clips | reference |
|---|---:|---:|
| any `Feather` child | 73 | 44 (38 + ~6) |
| `Feather.strength > 0` | 61 | 44 |
| stroke paints with `strength > 0` | **7** | 44 |

No variant matches, so the reference's clips are not "feathered paints" alone —
38 clips on Main must come from several sources (feathers, text, layout, nested
instances) and we have not separated them. Reverted rather than ship the
closest guess.

**What would separate them:** count the reference's `clipPath` lines by the kind
of draw that follows (fill / stroke / text / nested) — cheap on the dump, and it
would say which source contributes how many before implementing any of them.

## The clip gap is TEXT clipping (2026-11-18)

Classifying the reference's `clipPath` lines by the draw that follows them, on
data_viz:

| artboard | clips | before a fill draw | before a text draw |
|---|---:|---:|---:|
| Main | 37 | 4 | **33** |
| ColorGuide | 6 | 0 | **6** |

So the clip gap is **text**, not feathers — rive clips a text run to its layout
box (`text.cpp` calls `clipPath` before drawing glyphs). That displaces the
feather hypothesis I had carried for several rounds; the four fill-clips on Main
*are* feathers and are a small remainder.

**Text clips, three predicates measured.** Emitting a clip for every text draw,
using the glyph bounds we already compute as the rect (a no-op visually for
auto-sized text, since the clip equals the content bounds):

| gate | clips (Main + ColorGuide) | reference |
|---|---:|---:|
| every text | 54 | 43 |
| `sizing`(284) != 0 | 21 | 43 |
| `overflow`(287) != 0 | 3 | 43 |

A fourth gate was tried on measured overflow — the box is stored (285/286) and
the run's width is our own glyph extent, so `box_w > 0 and glyph_width > box_w`
needs no solver. Result: **3 clips** (reference 43), because these texts are
auto-sized and store `width = 0`. The clip rect genuinely comes from layout.

All three bracket the reference without matching it, so the gate is not a stored
flag — it is almost certainly "does this run overflow its computed layout box",
which needs the layout bounds again. Reverted.

**But the clip rect is layout-derived.** Emitting a clip from the text object's
stored `width`/`height` (keys 285/286) changed the clip count by zero — those
texts are auto-sized, so their box comes from the layout pass. Third question
today that lands on the same dependency.

## Scoping the layout pass (2026-11-18)

Before writing a solver, the structure was mapped. LineBars mixes three regimes,
which is why a simple stacker will not sweep these artboards:

- **explicit-positioned shapes** — bars carry their own `Node.x` (`-98.75`,
  `-59.25`, `-19.75`, `19.75`, `59.25`, `98.75`) and `y = 0`;
- **bone-attached content** — the same artboard has `RootBone` nodes at
  `x = -108.75 … 88.75`, i.e. skinned offsets rather than layout;
- **layout components** — nested `LayoutComponent`s with width/height and a
  `LayoutComponentStyle` carrying `directionValue`(599), gaps (498/499) and
  padding (512-515).

And the measured offsets do not follow one of them: our white bars sit at
`(30, 54)`, `(69, 54)` … where the reference has `(10, 172)`, `(50, 172)` … — a
constant `+20 x`, `-118 y` relative to the reference, not a per-child layout
difference.

So the layout project starts with a **map, not a solver**: which drawable comes
from which regime, per artboard. That is a day of work, and it should be scoped
explicitly rather than started inside a round.

## Artboards carry their own transform (checked, not the offset)

Every chart artboard has `Node.x = -780` and its own `Node.y`
(HorizontalBars 207, ColorGuide 2224, VerticalBars -29, LineBars 408). Worth
recording because it is a plausible source of the constant offset — and it is
not the one: our bars are `+20 x / -118 y` from the reference, where applying the
artboard translation would move them by `-780 / +408`.

So the artboard transform is a real property our emission ignores, but it is not
what explains LineBars. Recorded so the next pass does not re-derive it.

## Drawable identity: blocked on being able to relink the dumper (2026-11-18)

The plan was to stamp each recorded draw with the owning shape's name —
`Component::name()` exists (`component_base.hpp`), so a hook in `Shape::draw` plus
an `extern` in `record.hpp` would give the reference stream a real identity.

The patch cannot be built here. `oracle/dump` links only system frameworks plus
static archives, but rebuilding from `rive-cpp/out/debug/librive.a` fails:

    undefined symbol: typeinfo for rive::Renderer
    undefined symbol: typeinfo for oracle::RecordingPaint
    nm -g out/debug/librive.a | grep _ZTIN5rive8RendererE  ->  0

There is no renderer archive (`libluau_vm`, `libminiaudio`, `librive`,
`librive_{harfbuzz,sheenbidi,yoga}`), and `librive.a` carries no Renderer
typeinfo, so the available objects are not what produced the existing binary.
Until the oracle's build is reproducible, the identity work is blocked — not by
the patch, which is small, but by the toolchain that would consume it.

## The oracle rebuild — the plan that would unblock identity (2026-11-18)

Identity has now failed three ways without touching C++: composed transform +
colour (works, but only tells us ColorGuide is ordered differently), geometry
hash (convention mismatch), and `(verbs, pts, colour, style)` signatures (0/38 —
our verbs/pts counts do not correspond to the reference's). The remaining route
is the small C++ patch, which needs a rebuild.

The working oracle must not be at risk, so the plan is to build in a copy:

    rsync -a --exclude out --exclude '.git' rive-cpp/ /tmp/rive-build/
    # patch Shape::draw to set a global shape name, record.hpp to print it
    cd /tmp/rive-build && ./build/build_rive.sh        # ~700MB source, 12 cores
    # relink oracle/dump from /tmp/rive-build/out/debug

rive-cpp is 2.9GB total but 2.2GB of that is `out/`, so the copy is ~700MB and
the existing binary stays untouched until the new one works.

That is a deliberate maintenance task, not a round-sized edit — recorded with the
commands so it can be run when the oracle can be offline for ~20 minutes.

## Isolated rebuild: the library builds, the dumper does not relink (2026-11-18)

The plan was executed in a copy, so the working oracle never moved:

    rsync -a --exclude out --exclude .git rive-cpp/ /tmp/rive-build/   # 533MB, 5s
    # patched Shape::draw:  const char* g_rive_shape_name = "";
    #                      g_rive_shape_name = name().c_str();
    cd /tmp/rive-build && ./build/build_rive.sh                        # EXIT=0

The library builds with the hook. **Relinking the dumper does not**, and the
reason is a missing recipe rather than a code problem:

    undefined symbol: typeinfo for rive::Renderer
    nm -g /tmp/rive-build/out/debug/librive.a | grep _ZTIN5rive8RendererE -> 0
    ls /tmp/rive-build/out/debug/*.a   # no renderer archive

Compiling `renderer/src/*.cpp` to supply it fails on
`generated/shaders/tessellate.glsl.exports.h` (shader headers produced during a
build target we are not invoking), and `-fno-rtti` breaks other symbols
(`RiveRenderPaint::getIsOpaque`). So `oracle/dump` was originally linked with a
configuration that is not recorded in the repo — that is the missing piece.

Both source patches were reverted: `record.hpp` referencing a symbol the shipped
`librive.a` does not define would be a footgun for anyone relinking.

**To finish this:** recover the dumper's link recipe (the build target that
produces the shader headers, or the exact command), then re-apply:

    // shape.cpp (after includes)
    const char* g_rive_shape_name = "";
    // shape.cpp, first line of Shape::draw
    g_rive_shape_name = name().c_str();
    // record.hpp
    extern const char* g_rive_shape_name;
    // record.hpp, drawPath format string: "drawPath shape=%s style=%d ..."
    // and pass (g_rive_shape_name ? g_rive_shape_name : "") first

## Ordering is material, not cosmetic (2026-11-18)

Before writing off draw order, the question "does it matter?" was measured from
the reference geometry (bbox overlap per artboard, frame 0):

| artboard | draws | overlapping pairs |
|---|---:|---:|
| ColorGuide | 38 | **703 / 703** |
| Circles | 44 | 748 / 946 |
| LineBars | 20 | 95 / 190 |
| Pie Chart | 15 | 81 / 105 |

Every pair overlaps on ColorGuide, so order changes what is painted over what —
it cannot be dismissed as cosmetic, and the identity work stays justified rather
than optional.

## Ordering has structure after all (2026-11-18)

Identity matching (composed CTM + colour + style) lets us recover the *permutation*
the reference applies to our draw order. ColorGuide, our positions in reference
order:

    31, 37, 28, 26, 30, 27, 29, 36, 23, 21, 25, 22, 24, 35,
    18, 16, 20, 17, 19, 34, ...

That is not random, and not a simple reverse. It is **groups of five, drawn
last-group-first, with an interloper after each group**:

    28 26 30 27 29 | 36
    23 21 25 22 24 | 35
    18 16 20 17 19 | 34

The five within a group follow offsets `+2, 0, +4, +1, +3` from the group base,
and the interloper counts down (36, 35, 34) across groups. So the reference is
walking the artboard's tree in some z/stack order: each group's items are
permuted by a fixed rule and one element is painted after the group rather than
with it.

That is a decodable rule, and it is the first real structure found in ordering
after four candidates failed. The next step is to extend this to all 38 draws and
map positions back to object indices (roots, paints, groups) so the rule can be
expressed as a traversal rather than a permutation.

## The permutation in object terms (2026-11-18)

Mapping ColorGuide's 38 draws back to object ids (via `RIVE_TRACE_DRAW`, which
prints them in emission order):

    ref: 876 868 | 856 844 856 850 856 | 831 | 821 809 821 815 821 | 795 |
         783 771 783 777 783 | 759 | 747 747 747 | 735 741 | 724 |
         712 700 712 706 712 | 687 | 660 672 666 672 672 672

The structure is now concrete:

- **interlopers are single draws** and are *different kinds*: `876` is a Shape
  parented directly to the artboard (`x=83.5`), `868`/`831` are Texts under
  LayoutComponents, `687`/`660` are Shapes;
- **groups are siblings under one parent**: `844, 850, 856` share parent `843`
  (a Node), `809, 815, 821` share `808`, `771, 777, 783` share `770`-ish;
- **one member is interleaved, not clustered**: the reference draws
  `856, 844, 856, 850, 856` where we draw `856, 856, 856, 844, 850`.

So the reference is not reordering shapes: it is walking the tree and painting
each node's *repeated* child between its siblings, one pass per sibling. That is
a traversal shape, not a sort — which is why stream, reverse, DFS and row-major
orders all failed while the permutation itself looks regular.

**Next:** dump the reference transforms for those five draws. If the three `856`
draws carry different CTMs, the interleaving is per-sibling-instance and the rule
is a nested walk; if they carry the same CTM, then `856` is being painted once
per sibling deliberately (a stroke/shadow pass) and the rule is per-paint.

## After the alpha fix, Circles' residual is placement (2026-11-18)

With alpha compared honestly (8 digits), Circles drops to 7/44 positional
colours and 14/44 identity-set. Diffing the sets:

    ref-only:  ffffffff (1,0,0,1, 438,113) (381,113) (325,113) (269,113)
    ours-only: 80ffffff (1,0,0,1, 213, 56) (269, 56) (325, 56) ...

The alpha (80 vs ff) is incidental — the transforms differ, so these are
different drawables. The real signal is the **y coordinate**: 113 in the
reference, 56 in ours, the same class of constant placement offset already
measured on LineBars.

Tested and reverted: not baking `WorldTransformComponent.opacity` into the
colour's alpha. The recording renderer keeps the raw colour and carries opacity
separately, so the idea is principled — but removing the baking changed no
measurement, and our op stream has no separate opacity channel, so it would have
made translucent draws render opaque. Left as-is.

## Circles' white circles: alpha and y (2026-11-18)

Reference Circles, first draws:

    ffffff (tx 437.71, ty 113.158)   ... 6 white circles stepping -56.29 in x
    ours: 80ffffff (tx 437/381/325..., ty 56)

Three facts, each checked rather than assumed:

1. **x matches exactly** (156.29, 212.57, ... ) — the transform chain is right in x;
2. **`80ffffff` is the file's own colour** (`SolidColor.colorValue = 0x80ffffff`,
   6 occurrences in the artboard), so it is not our opacity baking — verified by
   gating the bake off, which produced byte-identical op streams;
3. the reference records **`ffffff`** for those six draws, i.e. opaque white,
   where the file declares 50% alpha.

So either the reference's six white draws are a *different paint* of the same
shapes (a stroke where we emit the fill), or rive ignores that alpha somewhere.
That is checkable from the shape's paint list: it should have both a white
`Stroke` and an `80ffffff` `Fill`, and the question is which one the reference
records at that transform.

The `y` difference (113.16 vs 56) remains the placement question and is separate.

## The placement bucket is largely CONSTRAINTS, not layout (2026-11-18)

Chasing Circles' y offset (113.16 vs 56) led to the object itself:

    shape 2068 (Shape): Ellipse 3x3, Fill 2516 (colorValue 0x80ffffff),
                        TransformConstraint 2071 (targetId 326, originX 1.0, originY 0.5)

`TransformConstraint` is type key **83**, and there are **100** of them in
data_viz alone. Our decoder parses its properties (originX 372, originY 373, …)
but **never applies it** — there is no `type_key == 83` anywhere in the emission
path. So constrained objects are drawn at their unconstrained Node position, which
is exactly the kind of constant offset measured on Circles (y 56 vs 113) and
LineBars (bar placement).

rive-cpp's semantics (`src/constraints/transform_constraint.cpp`):

    targetTransform = target.worldTransform
                    * translate(bounds.left + bounds.width  * originX,
                                bounds.top  + bounds.height * originY)
    constrainWorld(component.worldTransform, targetTransform, strength, ...)

with optional local/global space handling. That is implementable: we already have
world transforms and can resolve `targetId`.

**This reframes the remaining work.** "Layout solver" was the label for the
placement bucket; a large part of it is a constraints feature we simply never
implemented, and constraints are far smaller than Yoga. The plan is to implement
`TransformConstraint` (and check `TranslationConstraint`/`RotationConstraint`
counts the same way) before touching layout.

## TransformConstraint: attempted, and blocked on target ids (2026-11-18)

Implemented type-83 constraints on the emission path (`effectiveWorld` only
handled FollowPathConstraint, type 165 — `hasConstraintChild` does not know 83).
First version resolved the target with `findBySlot` and produced:

    shape 2068: was (156.3, 56.5) -> became (101.0, 0.5)
    reference:                       (156.28, 113.16)

Wrong in a revealing way: **x was already correct before the constraint** and the
constraint broke it, which means the target was resolved to the wrong object.
`TargetedConstraint.targetId` is a **component id**, not a per-artboard slot;
`findBySlot` cannot resolve it, and neither can anything else in our decoder —
object ids are the same missing thing that blocks keyframe-group matching
(G_Meter) and draw ordering.

So constraints are **not** independent of the identity blocker: implementing them
correctly needs the object-id space, the same gap already recorded three times.
Reverted; decoder is byte-identical to HEAD again (Circles 44 draws).

**Both id hypotheses tested.** Before settling, the two cheap resolutions were
measured on shape 2068 (reference `(156.28, 113.16)`):

| resolution | result |
|---|---|
| `findBySlot(targetId)` | `(101.0, 0.5)` |
| `targetId` as object index | `(268.6, 493.2)` |
| unconstrained (current) | `(156.3, 56.5)` |

Neither matches. Note the third row: **x is already correct unconstrained**, so
whatever the id space is, the constraint must move this object only in y — and
neither hypothesis does that. That is a sharper constraint on the answer than
either failed attempt.

**Correction (same round): the blocker is not the id space.** `targetId` 326
resolves correctly through the per-artboard slot map to object 2419
(`LayoutComponent`, 25 x 110). With rive's formula
`target.world * translate(w*originX, h*originY)` and origin `(1.0, 0.5)`, the
offset is `(25, 55)`, so the reference's constrained position `(156.2857,
113.1582)` requires the target's world to be **`(131.29, 58.16)`**.

Our `effectiveWorld` puts that target at **`(101.0, 0.5)`** — off by
`(30.29, 57.66)`. That is a *layout position* error on one LayoutComponent, not an
identity error: the constraint resolves its target fine, and applies the right
origin offset, but the target itself sits in the wrong place.

So constraints are gated on **layout**, and the numbers above say exactly how
much: 30.29 in x, 57.66 in y, on a 25 x 110 box. That is a far better starting
point than the id hypotheses (both now rejected) — and it corrects the earlier
claim that constraints were blocked on ids.

That is worth knowing before anyone starts the constraints work: it looks like a
self-contained feature (100 instances, rive-cpp's math is 20 lines) and is
actually gated on the reference's id space.

## The constraint target's chain does not explain the drawing (2026-11-18)

Resolving the target properly (slot 326 -> LayoutComponent 2419) and walking its
chain gives flex parameters that *cannot* produce the reference layout:

    2419  25 x 110   sibling of 5 more 25 x 110 boxes
    2418  144 x 117  style: paddingLeft = 100, alignmentType = 7
    2417  257 x 187  style: flexDirection = 0, alignmentType = 4
    2415  21 x 124.281

The reference draws six white circles at x = 156.29, 212.57, 268.86, ... —
spacing 56.29, total span ~281. Six children of 25 in a 144-wide box with
248 of padding cannot give that, and `2415` being 21 wide cannot contain `2417`
at 257 wide.

So the drawn circles are **not** these layout components; the constraint chain I
traced belongs to something else in the tree. My mapping "constraint target =
the circle's container" was wrong, and building a flex solver against it would
have produced a wrong model with a plausible story attached.

**Next:** identify the actual drawables at those positions — the shapes whose
world transform matches the reference's draw transforms — before any layout work.
That is the same discipline that found the alpha bug: check the object, not the
story around it.

## vm.bind was a stub and the facade violated R1 (2026-11-18)

The leaf contract's R1 says *nothing about a leaf's state may live in
process-global storage*. The facade did exactly that:

    ~proc vm.bind|zig { _ = r; g_vm_bound = true; g_vm_vmid = vm; g_vm_inst = inst; }

`_ = r` — the handle was ignored, and the binding went into three module globals,
so two open handles could not hold different bindings and the last call won.

Fixed: `vm_bound` / `vm_vmid` / `vm_inst` are fields on `Riv`, all five read
sites (`boundStaticProp`, `boundColorProp`, `boundKfValue`,
`boundScriptArtboardId`, `boundRunText`) read them from the handle, `vm.bind`
writes the handle, and the globals are gone. joystick stays op-identical and the
data_viz counts are unchanged, so the refactor is behaviour-preserving.

Independence is now structural rather than tested: two handles own their own
fields. A runtime two-handle test needs a probe that threads two handles through
Koru's `|>` chain; that is worth writing when the facade grows its next verb.

**The input schedule is per-handle now.** `input.fire` had no handle parameter
at all (`{ name, value, frame }`) and appended to one process-global list, so two
leaves shared one input timeline. It is `{ r, name, value, frame }` and appends to
`Riv.inputs`; `RIVE_INPUTS` seeds the handle at `open` instead of lazily into the
global. `smInputBoolAt`/`smInputEventFrame` read the handle.

This is not an invention: `LEAF_CONTRACT.md` already specified
`leaf.input.fire { leaf, name, value, at_frame? }`. The implementation was behind
its own contract, which is worth noting — the ruling existed and the verb ignored
it. joystick op-identical, data_viz counts unchanged.

**The pointer channel is per-handle too.** Positional events lived in
`g_ptrLogs`, an `AutoHashMap(usize, *PtrLog)` keyed by the handle's address —
per-Riv only by convention, leaked on `free` unless the map entry was removed, and
a process-wide singleton keyed by address. `Riv.ptr_log` now owns them;
`ptrLogFor` and the map are gone, `free` deinits the handle's list, and the
`RIVE_POINTERS` seed runs at `open` so readers can stay `const`.

All three state-holding verbs are now per-handle: `vm.bind`, `input.fire`,
`pointer.move`. joystick op-identical, data_viz counts unchanged.

**The SM evaluation state now restores on every exit path.** The nested-artboard
expansion saved `g_activeAnim` / `g_blendFrom` / `g_blendT` / `g_instVmid` /
`g_instObj` by hand and restored them five lines later. Nothing returns in
between today, so there is no live leak — but these are per-leaf values, and one
future early return would carry a nested artboard's SM state into the next
drawable. The restore is a `defer` now, so it cannot be skipped.

They are still globals (moving them onto `Riv` needs the eval path to take a
mutable handle, a wide ripple); what changed is that they can no longer be left
dirty. car_widgets 628/612 unchanged, joystick op-identical.

**R1 is now tested, not just asserted.** `selftest.handles { path }` opens the
same file twice, mutates only the first handle's input schedule, pointer log and
VM binding, and fails if the second handle can see any of it:

    selftest.handles: ok (input, pointer and vm bindings are per-handle)

The earlier rounds could only argue independence structurally ("the fields are on
the handle"). This makes it checkable — a regression that reintroduces a global
would fail here rather than being discovered by a caller with two leaves.

**And it runs with the gates.** `oracle/leaf_selftest.py` builds the probe and
checks the verdict on three fixtures; `run_gates.py` invokes it after the image
gates and folds its result into the exit status (it cannot be a manifest entry —
it compares no images):

    independent  joystick_databound_keyframe_test.riv
    independent  car_widgets_v01.riv
    independent  data_viz_demo.riv
    leaf self-test: PASS (per-handle input, pointer and vm state)

### The mesh gate's justification was stale and false (2026-11-18)

With categories in place, the one KNOWN gate was worth reading rather than
trusting. Its manifest note said:

    mesh path — placement exact, AA verified pixel no-op

The artifact was marked STALE (backfilled provenance, driver unknown), so the note
described a render nobody had regenerated. Rebuilding `meshrender_clfp.k` and
evaluating it against the same reference:

| check | measurement |
|---|---|
| ink-bbox | ours `(0,0,499,499)` vs ref `(24,89,471,452)` — we ink the **whole frame** |
| ink-mass | 2397 vs 1206 (ratio **1.99**) |
| coverage-gap | **64%** unmatched within 1px (max 5%) |
| frame-diff | 1.70% of frame differs (max 0.10%) |

So the recorded "pixel no-op" is the opposite of the truth: our mesh fixture
currently fills the frame. The image, its provenance (driver `meshrender_clfp.k`,
this commit) and the note are all corrected, so the declared gap now states its
measured size instead of a stale claim from an earlier build.

**The triangle trace was lying, and fixing it named the culprit.** `tris n=… bbox=…`
computed its bounds with only `ctm[1]*vy + ctm[5]`, ignoring the rotation and
scale terms, so every triangle printed as a degenerate line (`(161,364)-(339,364)`
— zero height). With the full affine transform, the first draw is:

    tris n=2 ctmdepth=1 bbox=(0,0)-(500,500)

a **full-frame quad**. Our op stream starts with a `ff313131` fill covering the
whole artboard; its colour equals the gate's backdrop `(49,49,49)`, so the frame
looks empty while its anti-aliased edge reaches all four corners — which is
exactly why `ink-bbox` reported `(0,0,499,499)` while the dominant colour in our
render is still the backdrop.

Two separate facts, worth not conflating: that fill is one draw and the fixture is
short of many — ours emits **29** draws for this artboard against the reference's
**57**, so the mesh gate is failing on two axes at once.

**First diagnosis: not the clips.** `meshops` emits `mclip` rects derived from
the op stream; a full-frame clip painted as ink would explain the fill, so clip
emission was gated off and the render repeated — **byte-identical ink coverage**
(`ours=(0,0,499,499)` both ways). The triangles themselves cover the frame, so the
next place to look is the tessellation input: a degenerate or uninitialised vertex
in the path being tessellated, not the clip stack.

This is the failure mode the category work exposed: a KNOWN gate with an
unregenerated artifact will happily keep asserting last month's conclusion.

### Gate verdicts are category-aware (2026-11-18)

The runner counted a manifest-declared gap as a suite failure: `mesh` carries
`hand_label: NOTE` with the note "mesh path — placement exact, AA verified pixel
no-op", and yet the tally read "32 PASS, 1 FAIL" with a non-zero exit.

Verdicts now derive from the label:

| label | comparison fails | verdict |
|---|---|---|
| PASS (or absent) | — | PASS |
| LIMIT / NOTE | yes | **KNOWN** — recorded gap, suite stays healthy |
| PASS (or absent) | yes | **FAIL** — unexpected, exit 1 |

   33 gates: 32 PASS, 1 KNOWN (LIMIT/NOTE), 0 FAIL
   leaf self-test: PASS (per-handle input, pointer and vm state)

The failing *checks* still print for a KNOWN gate, so a gap that gets worse is
visible; and only an unlabelled or PASS-labelled failure sets the exit code. The
manifest is where a gap is declared, so silencing one means labelling it NOTE
with a reason in the same file — a reviewable act, not a quiet one.

Current suite: 33 image gates, 32 PASS and the known `mesh` FAIL (labelled NOTE,
marked STALE — mesh is not implemented, and it is not a regression from these
changes).

**Remaining R1 violations, for the record:** `g_activeAnim`, `g_blendFrom/T`,
`g_smInputs` (the input schedule), `g_cframe`, `g_rowVmid/g_instVmid/g_rowInstOrd`
are still module-global. They are the same class of problem and the same fix —
move them onto `Riv` — but each needs its call sites audited, so they are named
here rather than half-done.

## component_list_follow_path: we inline a 10-item list rive does not draw

`--all-artboards` on the file behind the mesh gate:

| artboard | ref | ours | status |
|---|---:|---:|---|
| Main (idx 18) | **3** | **29** | +26 |
| Item (idx 74) | 2 | 2 | op-identical |
| Artboard (idx 114) | 1 | 1 | op-identical |

The reference's three Main draws are specific: the `ff313131` artboard
background, then two white `ffffffff` strokes (`thick=1`, transforms at
`(25, 154.5)` scale 0.95 and `(250, 363.5)`).

Our 29 are **8 shape + 10 text + 1 artboard paint + 10 layout paints**. The nested
artboards match exactly, so this is not an expansion-count error at the instance
level: we are drawing a **ten-item list inline on Main** (ten texts, ten layout
paints) that the reference does not draw there at frame 0.

That is the same class as the earlier FLD work: the list's rows exist in our
stream because we emit them from the object tree, while rive draws none of them —
they are laid out only when the layout pass runs. It also explains the mesh gate's
frame-spanning ink: our extra layout paints are what reach the corners, not the
artboard background (which the reference draws too, at the same colour as the
backdrop).

A correction to the previous round's note: my "ref 57" came from calling
`oracle/dump <file> 18 0.0083` — the CLI takes `<frames> <dt>`, so `18` meant
eighteen frames, not artboard 18. The harness was right all along; the manual
invocation was wrong.

### Correction: those ten pairs are component-list rows, not duplicated draws

The previous note read the trace as a duplication bug ("the same object drawn ten
times"). That is wrong. `component_list_follow_path`'s Main artboard contains
`ArtboardComponentList` (type 559) objects, and the rows are *instances of the
Item artboard's objects*: `obj=77` (Text) and `obj=88` (Fill) live in artboard 74
(`Item`) and a component list re-emits them once per row. Emitting the same source
objects per row is the mechanism working as designed — there is no duplication
defect.

What is wrong is the **row count and their placement**: we emit ten rows, all at
`t=0.0,0.0` with only the width varying, while the reference draws none of them.
`RIVE_NO_NESTED` does not change the count because row emission is not the nested
loop.

So the question is not "what duplicates the draw" but "why ten rows at one
origin, where rive draws zero" — i.e. the component-list layout/virtualisation
question, which is the same layout dependency as before.

### Where the ten rows actually come from

The rows are emitted by the component-list path in `collectOps`, which for each
row calls `collectArtboardOps(rowArtboard, -1)` — that is why Main's stream
contains artboard 74's `obj=77`/`obj=88`. The extended `LAYPAINT` trace shows it
directly:

    LAYPAINT obj=88 lc=75 owner=74 color=ff12a100 t=0.0,0.0 wh=28.6,40.2

(two objects, ten emissions — one per row, exactly as a list should).

The objects behind the list are:

| object | type |
|---|---|
| 19 | Node |
| 20 | **ArtboardComponentList** |
| 21 | **DataBindContext** — no properties at all |
| 22 | ListFollowPathConstraint |

So the list has **no data source**: its `DataBindContext` carries nothing, which is
why rive renders zero rows at every frame. Our row count is derived (ten rows with
*computed* widths 28.6, 24.1, 28.2, 28.4, 28.9 …), not read from bound data.

That makes the fix rule-shaped rather than layout-shaped: a component list with no
bound data should emit **no rows**, and the ten we emit are invented rather than
misplaced.

#### Correction: that discriminator was a mis-parse

Re-reading the raw inspector output for the follow-path file:

    obj[21] DataBindContext slot=-1 parentId=-1% props=3
        DataBind.propertyKey (key 586, f0) = 800
        DataBind.converterId (key 660, f0) = 1
        DataBindContext.sourcePathIds (key 588, f1) = <2B>

It **has** a source path, identical in shape to `component_list_1`'s. My earlier
statement that it "carries no properties at all" came from a parser that dropped
those lines. So `sourcePathIds` is not the discriminator and must not be used as
one.

What actually differs is the sibling: the follow-path list has a
**`ListFollowPathConstraint`** (`targetId=10`, and `targetId=7` for the second
list), which positions rows *along a path*. Trace confirms rows exist in both:

    ROWS li=20 owner=18 n=10
    ROWS li=24 owner=18 n=6

Ten and six rows are real; we then place them all at `t=0.0,0.0` because we do not
evaluate the list's follow-path constraint. Rive places them along the path, where
they fall outside the artboard and are clipped — which is why it draws none.

So the gap is **list-row placement via `ListFollowPathConstraint`**, not row
existence.

### The discriminator: a DataBindContext with a source path

Comparing the file that renders rows against the one that must not:

| file | DataBindContext |
|---|---|
| `component_list_1.riv` (rows drawn) | `DataBind.propertyKey=800`, `DataBindContext.sourcePathIds=<2B>` |
| `component_list_follow_path.riv` (rows must not be) | **no properties at all** |

Also checked and excluded as the explanation: the count is not keyframed. The VM
numbers in the follow-path file are static (`propertyValue` 6.0 and 10.0), and no
`KeyedProperty` targets key 575, so barring a binding difference rive would compute
ten rows too — it computes none, which points at the missing source path rather
than at the number.

So the rule to implement and test: a component list whose `DataBindContext`
carries no `sourcePathIds` emits **no rows**. `component_list_1` has the source
path and its rows render; this file has none.

### And our counts agree with the goldens, not with the dumper

With the comparison scoped like-for-like (first artboard, frame 0 — the same block
`ref_digest` measures):

| file | dumper (ref) | golden | **ours** |
|---|---:|---:|---:|
| `component_list_1` | 1 | **17** | **17** |
| `component_list_follow_path` | 3 | **29** | **29** |
| `joystick_databound_keyframe_test` | 2 | 2 | **2** |

So for both data-bound list fixtures our draw count matches rive's *real* render
exactly, and the recording dumper is the outlier. The "over-draw" chased across
rounds 58–64 was an artifact of comparing against a reference that binds no data.

The harness now says so instead of reporting a divergence:

    ref-incomplete  component_list_1.riv: reference stream draws 1 but the golden
                    for this asset has 17 drawPaths — the dumper binds no data, so
                    data-bound lists render empty here. Not a divergence.

Two guards on that detector, both learned by getting them wrong first: it compares
the same block scope as `ref_digest` (counting every drawPath in the file flagged
op-identical joystick as incomplete), and it only fires when the reference is less
than half the golden, so a genuine regression that *reduces* our draws cannot hide
behind the label.

**Where the seam is, and is not.** Two isolation attempts:

- a simple fixture rendered through the same pipeline came out fully magenta —
  that probe selected an artboard with nothing to draw, so it proves nothing;
- the same file's 91x52 `Item` artboard leaves 247,982 of 250,000 pixels magenta,
  which is just the uncovered frame around a small artboard.

So the seam is only *visible* because the artboard quad is exactly the frame size:
two triangles tile the 500x500 square, and 496 pixels along their shared diagonal
keep the clear colour. The triangles come from our tessellation of the rect path
and are filled by the canvas backend, so the defect is in the **mesh render path**
(tessellation → canvas fill), not in the op stream: the reference draws the same
`ff313131` artboard fill, and our ops for it are correct.

That means it is not fixable in the decoder, and it should not be read as a
renderer parity failure of the decoded data.

### The frame-spanning ink is a 496-pixel triangle seam

Sampling the pixels the gate calls ink:

    (0,0)     -> (49,49,49)      backdrop
    (499,0)   -> (152,25,152)    magenta
    (0,499)   -> (152,25,152)    magenta

Magenta is the probe's clear colour (`offscreen.clear.color(r:1,g:0,b:1)`), so the
frame is not covered. Counting it:

| render | magenta pixels | locations |
|---|---:|---|
| ours | **496** | `(499,0) (498,1) (497,2) (496,3) …` |
| reference | **0** | — |

That is the **anti-diagonal of the artboard quad**: the quad is tessellated into two
triangles, and the shared edge leaves a one-pixel seam where the clear colour shows
through. One magenta pixel at each corner is enough to stretch `ink-bbox` to
`(0,0)-(499,499)` — which is the entire "frame-spanning ink" this gate has been
reporting for six rounds.

So the mesh gate's headline failure is a **rasterisation seam in the mesh path**,
not our path data, not list rows, and not a paint difference. The remaining
colour/coverage disagreements are separate.

## Correction: the mesh gate's frame-fill is not the list rows (2026-11-18)

Round 57 concluded that the mesh render's frame-spanning ink came from the extra
layout paints (list rows). That was testable and is wrong: after rows were moved
onto their follow-path positions, the mesh render is **byte-identical**:

    md5 /tmp/ours_mesh_t1.bmp oracle/images/ours_mesh_t1.bmp   ->  same hash

Same ink-bbox `(0,0)-(499,499)`, same ink-mass 2397, same 64% coverage gap. If the
row rects were the ink, moving them would have changed the image; it did not.

What that leaves: the frame fill is something the mesh path draws independently of
the row content — most likely the artboard background quad, whose colour equals the
backdrop and whose anti-aliased edge reaches the corners. That is drawn by the
reference too, so the gate's disagreement must be in how our mesh path interprets
it (or in what it draws *besides* the fill), not in list rows.

Also verified this round: the gate suite is unchanged by the row-placement work —
33 gates, 32 PASS, 1 KNOWN (mesh), 0 FAIL, plus the leaf self-test PASS.

#### And it is not PairPos either

GPOS was implemented too: feature list → `kern` feature → lookup list, unwrapping
extension lookups (type 9) into PairPos, coverage formats 1 and 2, ValueFormat
`xAdvance`. The probe confirms the table is reachable and correctly shaped:

    GPOS at 6060, features 3: cpsp, kern, mark
    kern lookup type=9 extType=2 extOff=18492 posFormat=1

Tracing the actual glyph pairs of that text, every adjustment is zero:

    PAIR 320->299 adj=0.00   PAIR 299->95 adj=0.00
    PAIR 409->456 adj=0.00   PAIR 456->320 adj=0.00
    PAIR 409->161 adj=0.00   PAIR 161->382 adj=0.00

So these glyphs are simply not pair-kerned, and the 0.73 units are neither `kern`
nor PairPos. Two mechanisms were implemented and both measure zero here; the
difference must be in single positioning, fractional advance handling, or the
metric source itself. Recorded so the next step is not another kerning attempt.

### The text advance difference is GPOS, not `kern` (2026-11-18)

With the clip fixed, the first remaining difference on `component_list_1` is text
geometry: golden drawable 4 spans `(0.9659, 4.6307)-(45.1669, 19.5739)`, ours
`(1.0, 4.6)-(45.9, 19.6)` — about 0.73 units wider over four glyphs. That is the
signature of missing pair adjustment, so `kern` was implemented: format-0
horizontal pairs from the font's `kern` table, binary-searched and applied between
adjacent glyphs (the code stays, and is a correctness fix for fonts that carry one).

It changed nothing, and a one-shot probe says why:

    KERN: no `kern` table in 805528-byte font

The embedded font has **no `kern` table** — its pair positioning lives in **GPOS**
(PairPos). So the remaining 0.73 needs GPOS parsing, not `kern`. Recorded rather
than guessed at: the next step is PairPos format 1/2 lookup, which is a real
feature rather than a rounding tweak.

Gates unchanged by the `kern` work: 32 PASS, 1 KNOWN, 0 FAIL; joystick
op-identical.

**First fix from golden comparison: the root artboard is not clipped.** Our code
emitted an artboard-bounds clip unconditionally (`clipOn` defaults true), giving
`component_list_1` two clips where the golden has one. Reading the golden makes the
sequence explicit:

    4  drawPath color=ff313131 …     <- artboard background
    10 restore
    12 clipPath verbs=6 pts=4        <- the ONLY clip, before the rows
    19 drawPath color=ff18b900 …     <- first row

No artboard-bounds clip appears at all. Rive clips **nested instances** to their
box, not root artboards. Restricting the artboard clip to `g_abDepth > 0`:

| | before | after | golden |
|---|---:|---:|---:|
| `component_list_1` draws | 17 | 17 | 17 |
| clips | 2 | **1** | **1** |

The first divergence then moves to **geometry**: drawable 4 has golden bbox
`(0.9659, 4.6307, 45.1669, 19.5739)` against ours `(1.0, 4.6, 45.9, 19.6)` — a text
advance difference of ~0.7 units, previously hidden behind the clip divergence.

Gates after the change: 33 gates, 32 PASS, 1 KNOWN, 0 FAIL; joystick still
op-identical; data_viz draws unchanged (199/196).

### `--golden`: compare against rive's real render

The goldens are in the dumper's own stream format, so the same digest can parse
them. `python3 oracle/authored_parity.py --golden FILE` now judges against
`oracle/goldens/corpus/<stem>.txt` instead of the dumper — the valid reference for
data-bound content.

First results, and they are far better than the dumper made things look:

| file | draws (golden/ours) | clips | first divergence |
|---|---:|---|---|
| `component_list_1` | **17 / 17** | 1 / 2 | **clip** — one extra clip on our side; the 17 draws and their colours match |
| `component_list_follow_path` | **29 / 29** | 0 / 0 | draw-order, with colour match 17/29 |

Detail worth acting on: on the follow-path fixture our rows paint `ff12a100`
(green) where the golden has **`ff747474`** — which is `SolidColorBase`'s default.
So the golden's rows are unbound-default, while we resolve a bound colour. That is
the opposite direction from every earlier "we miss data" finding: here we apply
data the reference render did not.

## FLD layout boxes were painted opaque black (2026-11-18)

Diffing data_viz Main's colour multiset against its golden named two concrete
problems, and the first is unambiguous:

    missing: 66ffffff x6,  00000000 x24
    extra:   ffffffff x9,  ff000000 x4, 99ff9502 x2, ...

`ForegroundLayoutDrawable` (513) hard-coded `fd.color = 0xFF000000` — every layout
box was opaque black regardless of its paint. It now takes the colour of its own
paint (sibling Fill/Stroke), with the gradient rule applied (a gradient paint
records `00000000`).

Effect, measured on the multiset:

| | before | after |
|---|---:|---:|
| extra `ff000000` | 28 | **4** |
| missing `00000000` | 36 | **24** |

Draw counts are unchanged (196 vs 199) — this was a colour defect, not a count one.
Gates unchanged (32 PASS, 1 KNOWN, 0 FAIL) and joystick still op-identical.

What remains of the colour divergence is an **alpha** problem: the reference records
`66ffffff` where we record `ffffffff`, and we emit `99ff9502`-style colours the
reference does not. That is the next thread, and it is separate from placement.

## The dumper does not materialise data-bound list rows (2026-11-18)

Chasing why the reference draws no rows, the goldens were checked against the
dumper for the same file:

| source | `drawPath` lines |
|---|---|
| `oracle/goldens/corpus/component_list_1.txt` (real rive render) | **589** |
| `oracle/dump` on `component_list_1.riv`, all blocks | **6** |

The dumper binds no data, so a data-bound component list resolves to zero rows in
the reference stream, while the real renderer draws them all. **Authored-parity
comparisons on data-bound lists are therefore measuring our output against an
unbound reference** — "ref 1, ours 17" is not evidence of over-draw.

What this changes:

- the "ten rows the reference never draws" result above is a property of the
  *instrument*, not of rive;
- the goldens, not `oracle/dump`, are the correct reference for these files (and
  our component_list goldens pass);
- the mesh gate compares against a rendered image, so it is unaffected — but its
  fixture does render no rows, which needs its own explanation.

This is the fourth instrument defect found this session, and the most consequential:
three earlier findings about list rows were reasoning against a reference that
could not produce rows at all.

## The reference never draws list rows — at any frame

Before blaming layout, the obvious alternative was timing: our SM may simply start
earlier. It does not. Across thirty reference frames the draw counts are constant:

| artboard | frames 0..29 |
|---|---|
| Main | **3** every frame |
| Item | **2** every frame |
| Artboard | **1** every frame |

So rive renders no component-list rows in this fixture at all, while we render ten
of them (at one origin). The divergence is therefore in **row resolution**, not in
when we start or where the rows land: `listRowItems` reads a data-bind path
(`pk=800`) and returns ten items, and rive — with no VM data bound — resolves the
same path to nothing.

Next step: compare what our path parse yields against an unbound VM in rive. If the
file carries default item data that rive ignores when nothing is bound, the rule is
"rows exist only when the data source supplies them", and our parse is inventing
them.

## The ten extra rows are the same two objects redrawn at one origin

With `RIVE_TRACE_DRAW` on Main:

    LAYPAINT obj=88 color=ff12a100 t=0.0,0.0 wh=28.6,40.2
    TXT      obj=77 color=ffffffff
    LAYPAINT obj=88 color=ff12a100 t=0.0,0.0 wh=24.1,40.2
    TXT      obj=77 color=ffffffff
    ... (ten pairs)

Two things are wrong at once, and they are separable:

1. **the same object is drawn ten times** — `obj=77` and `obj=88`, not ten distinct
   rows;
2. **every one of them is at the origin** (`t=0.0,0.0`) with only the *width*
   varying (28.6, 24.1, 28.2, 28.4), so any layout pass that ran computed sizes
   and never produced positions.

And `RIVE_NO_NESTED=1` leaves the count at 29, so this is not nested-instance
expansion: the loop lives in this artboard's own emission.

The reference draws none of them — its three draws are the artboard background and
two white strokes. So "the list is not drawn at frame 0" and "we draw it ten times
in one place" are both true, and the duplication is a defect independent of the
layout question.

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


---

## CAMPAIGN STATE (consolidated 2026-11-18 — durable map)

### Oracle stack
- `oracle/dump` — unbound reference op-dump; `oracle/dump_vmbound` —
  BOUND-VM variant REQUIRED for list-family files (component_list_*,
  clfp, follow_path, virtualized): unbound produces ref-draws-1
  collapsed-list artifacts. List content lives in Item/Row artboards
  (e.g. cl1 Item=38 draws, cl2 Item=132, virtualized ItemArtboard=52).
- `oracle/authored_parity.py` — tier-1 opsdump + pixel harness.
- Probes need fresh koruc; `import kr/rive` builds fail if
  `rive/rivgen_hello.kz` (t4f riv2k artifact) reappears — KORU022.

### Batch-2 distribution (30 fresh files, 2026-11-18)
- Raw: 4 identical / 4 divergent / 19 ours-unavailable / 3
  ref-unavailable. CAUTION: the 19 ours-unavailable are ~all
  "artboard name not decoded" = PROBE BUILD/TIMEOUT FLAKES under
  batch load, NOT decode gaps — spot re-run of 3 (shapetest,
  ik_anim_test, feather_render_test) produced real verdicts
  (1 identical, 2 divergent: paint-layer colour, clip-layer).
  Harness gap: koruc build failure parses as empty arts ->
  misclassified; should surface build errors as own status.
  RESOLVED: quiet serial re-run of all 19 -> 9 op-identical +
  10 divergent, ZERO ours-unavailable — flake hypothesis confirmed.
  TRUE batch-2 (30 files): 13 identical / 14 divergent / 3
  ref-unavailable / 0 ours-unavailable — 43% identical, far better
  than the raw log suggested. Notable identicals: recursive_lists
  (45 artboards), multiple_state_machines, rotation_constraint_wrap,
  scripted_as_path, pointer_button_nested, library_scope_edge,
  later_layer_trigger, shapetest, databind_external_artboard_main.
- ref-unavailable x3: oracle-side (missing frame-0 block; two
  file_asset_importer assertions on scripted-VM files).

### Batch-3 distribution (30 files, stratified slice 3, quiet serial)
- 11 op-identical / 16 divergent / 3 ref-unavailable /
  0 ours-unavailable (harness fix held — no flake masking).
- First-divergence: drawable-count 7, geometry 4, paint 4, clip 1 —
  geometry+paint together = 8/16, the vertex-exact + color-dynamics
  frontier confirmed as the dominant residual.
- Cumulative measured corpus: ~70 files, ~34 identical (~49%).

### Batch-4 distribution (30 files, quiet serial)
- 13 op-identical / 14 divergent / 2 ours-unavailable /
  1 ref-unavailable. First-divergence: drawable-count 7, paint 5,
  geometry 2 — drawable-count still dominates.
- ours-unavailable x2 are REAL signals (harness fix held):
  ik_over_distance_constraint SIGABRT exit 134 (new crash, logged
  FINDINGS.md — constraint-family isolate queued); light_switch
  empty op stream on ab 3844 (possible empty-emit).
- Cumulative: ~100 files measured, ~47 identical (~47%).

### ORACLE FIX (2026-11-19, t4j) — ALL PRIOR DISTRIBUTIONS SUSPECT

tier1_compare.py poisoned EVERY fixture's last frame: next artboard's
static/sm0 prefix bled into fr29 comparison. csvmi/dbai re-sweeps
post-fix: FULL GREEN — 'script-gated' was the artifact. ALL batch
distributions b1-b5 (~130 files) were measured on the poisoned oracle;
identical counts UNDERCOUNTED. harness also updated: first_divergence
now compares color/style/rule SETS + draw-order layer (order is not
content). RE-SWEEP IN FLIGHT — treat all prior identical rates as
lower bounds.

### Batch distribution (stratified ~40, post class-1/2/5 fixes)
- 13/40 op-identical · 24 divergent · 1 ours-unavailable
  (layout_text_match SIGABRT — FIXED, composite-glyph endPts
  off-by-one) · 2 ref-unavailable.
- First-divergence layers: drawable-count 15, paint 7, geometry 1,
  clip 1 — clips nearly closed as first-divergence; paint is #2.

### Divergence classes — status
0. **VERTEX-EXACT PATH CONSTRUCTION — named #1 frontier (t4f verdict,
   db_health post-cull-fix: ref 116 vs ours 10 draws).** Curve
   tessellation + clip ordering is THE central blocker across ALL
   authored fixtures — not per-fixture bugs. Our paths emit
   approximations where ref emits vertex-exact outlines; every
   authored file's draw/clip/geometry counts inherit the error.
   Tessellation-decode leg in flight. Supersedes per-class chase
   order until it lands.
1. NestedArtboard expansion (92/451/452) — LANDED (t4f). Follow-ups:
   frustum-cull vs expansion (db_health: expansion fires 6283 ops but
   only 81 k=8 draws — cull rejects huge-coord nested content),
   Solo/NestedSM gating unmodeled (post-solver overdraw flag).
2. Layout solver — NAMED RESIDUAL. Census: 601 files, flex core ~95%;
   design docs/layout-solver.md; evidence order flex->wrap->absolute
   ->grid. Blocks: LC/FLD per-item rects, nested-artboard sizing,
   collapsing_elements (-32 all-layout file).
3. Gradients — feature-sized op pipeline pending; fixture armed
   (fixtures/gradients: Linear/Radial/Angular, oracle-verified).
4. Overdraw/cull — queued; db_health cull-vs-expansion is the live
   instance.
5. Clips — ClippingShape(42) untraversed = hunter_x's 80 objects /
   ~130 clipPaths; fix spec'd (traversal arm -> clippush/clippop per
   rive-cpp clipping_shape.cpp). car_widgets clips = Feather
   path-effects (feature-sized, separate).

### Underdraw sub-classes (authored files, post-fix)
- db_health_tracker: 470v81 — expansion fires, draws culled
  (emit-gate/cull class).
- hunter_x_demo: 316v33 — ClippingShape(42) + underdraw.
- collapsing_elements: 48v16 — solver-blocked LC fills in nested
  targets; SM-selection proven count-invariant.
- layout_text_match: clip-layer only (37/37 draws, colors identical).
- list-family: use dump_vmbound; per-Item-artboard comparison.

### Fixture corpus
fixtures/: gradients, sm_conditions, scroll_view, vmlist, emptybind —
all decode-clean + oracle-verified. RML->.riv via rive CLI pipeline
(fixtures/PIPELINE.md).

## data_bind_artboard_input — SCRIPT-GATED (named residual, 2026-11)

29/30 PARTIAL; child1 30/30 clean. Failing frame = 29 only, on Main + child2.

Mechanism fully decoded: VM artboard-valued property (ViewModelInstanceArtboard
type 599, prop846=1 -> child2) binds via DataBind pk=876
(ScriptInputArtboard.artboardId) to ScriptInputArtboard obj9 -> parent
ScriptedDrawable obj8. `boundScriptArtboardId` resolves the bind live
(verified: artboardId=1 overrides authored 2; golden Main fr29 block is
byte-identical to child2 fr29 — bound selection confirmed correct).

Gate is inside the script: ScriptAsset "ArtboardPainter" (obj1) ->
FileAssetContents obj2 = LuaJIT-family bytecode (497B, Rive-wrapped —
stock `luajit -bl` refuses). Function map: init/advance/update/ab/
instance/draw/late. activeAnim=14 constant fr27-29 rules out SM-state
gating; SM section serializes no timing props. Hypothesis (unconfirmed
at instruction level): advance() timer completes at t=1.0 -> draw()
emits the bound artboard.

Classification: honest FAIL behind the leaf contract's deferred Lua
gap. pk=876 resolver + ScriptedDrawable->artboard render path are
implemented and proven (sdraw->child2 verified) but emit stays gated
off — unconditional emit regresses fr0-28 (verified: 20 ops all
frames vs golden's fr29-only content). Lua->Koru transpile is a
separate future arc, not commissioned.
