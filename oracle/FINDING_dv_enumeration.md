# Finding — data_viz_demo drawable enumeration (evidence side, 2026-11-18)

Per-artboard opsdump (`probe_dv8.k`, name-resolved indices) vs
`oracle/dump` frame-0 blocks. Every dropped drawable class, with counts.

## Instrument bug found en route (affects prior parity rows)

`authored_parity.py`'s `ref_blocks` keys blocks by marker text
(`--- frame 0 t=0.0083 ---`) — identical across all 8 artboards, so the
dict keeps only the LAST artboard's block (Circles, 44 draws). The
"Main ref 44 vs ours 3" row actually compared **Main-ours vs
Circles-ref**. True Main-vs-Main is **199 vs 3**. Fix: key blocks by
artboard order, not marker text.

## Per-artboard frame-0 draws (ref vs ours)

| artboard | obj idx | ref | ours | delta | ref clips | ours clips |
|---|---:|---:|---:|---:|---:|---:|
| Main | 315 | 199 | 3 | **-196** | 38 | 1 |
| HorizontalBars | 390 | 40 | 21 | -19 | 12 | 0 |
| ColorGuide | 653 | 38 | 38 | 0 | 6 | 0 |
| VerticalBars | 927 | 31 | 20 | -11 | 7 | 0 |
| LineBars | 1166 | 20 | 20 | 0 | 1 | 1 |
| Data | 1537 | 45 | 46 | **+1** | 6 | 0 |
| Pie Chart | 1897 | 16 | 16 | 0 | 2 | 0 |
| Circles | 2066 | 44 | 44 | 0 | 8 | 1 |

## Dropped drawable classes

**1. NestedArtboard instance content — Main, -196 draws.**
Main holds zero Shape/geometry objects: 12 `LayoutComponent`s, 6
`NestedArtboard*` instances (`artboardId` → the 7 chart artboards, each
with `NestedStateMachine`), 3 Fill+SolidColor backgrounds, 1 Text. The
196 missing draws are the instances' internals — every chart's bars,
labels, gradients — plus their clips (38 vs 1). Same rule as
FINDING_nested_artboard_drop; now quantified: it is ~78% of the file's
missing draws.

**2. `ForegroundLayoutDrawable` (type 513) — HorizontalBars -19,
VerticalBars -11.** These artboards contain ZERO `Shape` objects; their
geometry is 12 `ForegroundLayoutDrawable` nodes (props=1, parented to
`LayoutComponent`) plus Fills/gradients/Text. 513 is in `node_type_keys`
(transform-aware) but no draw arm emits it — its paint/geometry model
is layout-computed, not ShapePaint children. The missing `000000` draws
(25 and 12) are consistent with these items' paints and/or their text
labels.

**3. Paint colour resolution — `000000` → `747474`, ~72 same-count
swaps.** ColorGuide 19, LineBars 7, Data 19, Pie Chart 8, Circles 18 —
in each, draw COUNT matches but our colour is the `SolidColorBase`
default where ref has black. The ea94934 fix covered four SolidColor
read sites; these files still default, so a fifth site remains —
candidates: `TextStylePaint`→text path (`index.kz:~3015`), Stroke paint
colour, or gradient-stop colour reads. Per-artboard object census says
Text=6 per artboard but black-draw counts are 7-19 — so the black is
probably not only text; likely stroke/axis paints or layout-drawable
paints read through an unhandled key.

**4. Overdraw — Data +1.** We emit one extra `ffffff` draw the ref
culls. Missing cull rule candidate: `isVisible`(41) on a non-Fill
parent, opacity-0 node, or clip-bounds rejection. Small but real —
means our cull set is narrower than rive-cpp's.

**5. Clips — everywhere.** ref 38/12/6/7/1/6/2/8 vs ours ~1 per
artboard. Already named; this enumeration shows it is not one file's
problem — every artboard with content clips drops them.

## Evidence pointers

- `/tmp/dv_probe.txt` — abnames+inspect+opsdump @315 (regenerate:
  `koruc run probe_dv.k`; `./a.out <riv>`)
- `/tmp/dv_all_ops.txt` — probe_dv8.k, all 8 artboards one run
- `/tmp/dv_ref.txt` — `oracle/dump <riv> 1 0.008335`
- Object census: artboard ranges partition by object index
  (315-389 Main … 2066+ Circles); type histograms in this session's
  notes — Shape-having artboards (ColorGuide/LineBars/Data/Pie/Circles)
  draw count-exact; Shape-less ones (HorizontalBars/VerticalBars) lose
  draws to class 2.

Status: evidence complete for t4f. Classes 1+2 are traversal gaps;
class 3 is a decode/read-site gap; class 4 is a cull-rule gap; class 5
is clip emission. Suggested fix order by draws recovered: 1 (196) →
2 (~30) → 3 (~72 colour-corrected, count-neutral) → 5 → 4.
EOF
for d in gradients sm_conditions scroll_view; do true; done
cd /Users/larsde/src/koru-rive && git add probe_dv8.k oracle/FINDING_dv_enumeration.md && git commit -m "$(cat <<'EOF'
finding: data_viz drawable enumeration — 5 dropped classes with counts

Per-artboard frame-0 opsdump vs oracle/dump: Main -196 (NestedArtboard
instances unexpanded), HorizontalBars -19 / VerticalBars -11
(ForegroundLayoutDrawable 513 never emitted), ~72 same-count colour
swaps 000000->747474 (a fifth paint-colour read site still defaults),
Data +1 overdraw (cull rule missing), clips dropped everywhere.
Also found: authored_parity.py ref_blocks keys blocks by marker text —
identical across artboards, keeps only last (Circles) — prior 'Main
ref 44' row was Circles-vs-Main-ours; true Main is 199 vs 3.
EOF
)" && git log --oneline -1 && git status --short | head -5
## Class-3 verdict (2026-11-18, measured): NOT a colour read site — it is gradient paints

Premise falsified. The ~72 `000000`→`747474` swaps are **gradient-filled
draws**. Proof chain:

- `oracle/dump` frame-0 blocks carry `shader=N(...)` per drawPath.
  `shader=1` counts per artboard equal the missing-black counts EXACTLY:
  ColorGuide 19=LG19, LineBars 7=LG7, Data 19=LG19, VerticalBars 12=LG12,
  Pie 8=LG2+RG6, Circles 18=LG18, HBars 24=LG24 (+1 other black).
- Gradient draws in the reference emit `color=ff000000` — the colour
  field is a placeholder when a shader paint is active. Ours emits the
  `SolidColorBase` default `747474` because the Fill/Stroke paint child
  is `LinearGradient`(22)/`RadialGradient`(17), not `SolidColor`(18) —
  the `g.type_key == 18` paint lookup finds nothing and defaults.
- Object census: Shape-less artboards (HBars/VBars) lose *counts* to
  class 2; Shape-ful ones lose only colour fidelity to this class.

So class 3 = **gradient paint resolution**, the named ops-kinds-11+
gap. Not a fifth read site. Real fix scope: paint-child lookup must
accept gradient types → new op kind carrying axis+stops (image-op
side-table pattern exists) → canvas `draw.gradient`/`.radial` are
two-stop only (multi-stop needs shader work) → digest already aligns
if gradient ops carry the ref's `000000` placeholder convention.
Deferred to its own leg — feature-sized, not a read-site patch.

## Class-2 scope (ForegroundLayoutDrawable 513) — blocked on layout solving

`rive schema`: FLD extends `Drawable > Node > TransformComponent` —
node transform + `blendModeValue` + `drawableFlags`, and **zero paint or
geometry children** (30 FLD objects in data_viz, 0 children). All
geometry props are `computed*` (derived, key 806-811) — the file stores
no bounds; the layout solver computes them.

So class 2 is not a traversal patch: emitting an FLD means (a) solving
the parent `LayoutComponent` flex layout to get its computed rect —
the same named layout gap as class 1's instance sizing — then (b)
resolving its paint, whose source is still unidentified (no children;
candidates: parent LayoutComponent's Fill children — the "layout-box
pass" already emits those — the LayoutComponentStyle, or the 12
DataBindContexts binding per-item colors). Next evidence step: read
rive-cpp's `foreground_layout_drawable.cpp` render path or export a
minimal .rev to see which object owns the paint.

Our HBars=21/VBars=20 draws are the layout-box fill pass + text; the
-19/-11 deltas are the FLD items themselves (bar segments/labels).

## Note — emptybind fixture emit gap (from t42 cross-val)

`fixtures/emptybind` at correct ab shows ours ~1 draw vs ref 8: the
NuRive-branding `NestedArtboard` content does not expand — same class-1
rule, now observed on an RML-authored file too (not just corpus demos).

## Class-2 paint owner — NAMED (rive-cpp source evidence)

`rive-cpp/src/foreground_layout_drawable.cpp:45-95`:
`ForegroundLayoutDrawable::draw` iterates **`m_ShapePaints`** — the FLD's
OWN Fill/Stroke children — and draws them over **the parent
LayoutComponent's outline at the layout's transform**
(`parent()->as<LayoutComponent>()`; comment: "it has no box of its own:
it paints the parent layout's outline, at the layout's transform, with
its own paints"). `paintedWorldBounds` confirms: bounds = parent's.

So paint owner = FLD's own shape-paint children; geometry owner = parent
LayoutComponent's computed layout rect. NOT LayoutComponentStyle, NOT
DataBindContext directly (binds may feed the paints' props).

Open linkage check for the fix side: my object census found 0 children
under the 30 data_viz FLDs — either those particular FLDs are unpainted
(invisible items) or the Fill/Stroke→FLD parent edge resolves via a
slot/id path the census regex missed. Verify by grepping inspect output
for fills whose resolved parent is a 513 before writing the emit arm.

## Class-2 anomaly RESOLVED + verdict complete (fills→513 edges verified)

**Zero edges confirmed.** All 30 data_viz FLDs have no Fill/Stroke
children — the earlier census was correct, not a regex miss. In
rive-cpp terms their `m_ShapePaints` is empty, so `FLD::draw` is a
no-op for this file even in the reference. FLD is a layout-item
*marker*; the paint that actually renders lives one level up.

**Paint owner (final):** `LayoutComponent`-parented Fill(20)/Stroke(24)
children — 40 such objects in HorizontalBars alone, parented to LCs
(`->394:LayoutComponent` etc.), never to FLDs. `pickPath(parentLayout)`
in the cpp is how shape paints acquire layout geometry.

**Our emit state** (`emitArtboardPaints` layout-box pass, ~index.kz:4984):
per-409, computes lw/lh (style units 607/608 fill-parent resolution,
corner radii 640-643) then emits **one rounded-rect per type-20 Fill
child at the LC's whole box**. Three residual gaps vs ref:

1. **Type-24 Stroke children of LCs are skipped** (`c.type_key != 20
   continue`) — small counts here (1/artboard) but real.
2. **Per-item geometry**: every LC-fill paints the LC's entire box;
   ref paints at *computed item rects* (FLD sub-regions). Needs the
   flex solver — the feature-sized blocker.
3. Fills parented to non-409/non-artboard/non-shape nodes (e.g. nested
   layout nodes) may fall between the passes — unmeasured.

**Class-2 verdict: NAMED RESIDUAL** — paint owner = LC-child
Fill/Stroke; blocker = layout solver for per-item rects (feature-sized,
same family as class-1 instance sizing). Cheap sub-fix available now:
emit LC-parented Stroke(24) in the layout-box pass.

## emptybind NestedArtboard gap — RESOLVED: probe artifact, not emit gap

CLI-injected branding nests DIFFERENTLY than data_viz but same type
keys: EmptyBind(11) has ZERO NestedArtboard children — branding is
SIBLING artboards. Watermark(935) holds 2 NestedArtboardLeaf
(artboardId 1,2 = ORDINALS -> Wordmark 28 / Brandmark 642) +
NestedStateMachine children. t42's "ab:9 ~1 draw" was a wrong-index
probe: obj[9] is a ViewModelInstanceNumber, not an artboard — same
ab-object-index confusion class as the original ours=0 bug. Correct
indices: 11/28/642/935. opsdump_eb.k on all four: 22 draw ops total —
expansion reaches RML nesting fine (t4f's fix covers it).
