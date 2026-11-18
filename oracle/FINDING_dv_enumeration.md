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
