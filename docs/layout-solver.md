# Layout solver — design (evidence-scoped)

Status: DESIGN ONLY — implementation assigned to t4f after its
list-binding leg. Evidence base: `oracle/FINDING_layout_census.md`
(601 .riv files, prop-key tally, commit 64a0193).

## Why this exists

Three named divergences share one root: we never solve layout, we
approximate it.

- **Class 2** (per-item rects): `ForegroundLayoutDrawable` and
  LC-child paints need each child's *computed* rect; today every
  LC-fill paints the LC's whole box (`emitArtboardPaints` layout-box
  pass, `rive/index.kz` ~4984).
- **Class 1** (instance sizing): `NestedArtboard` instances need
  intrinsic sizing (fit/fill) resolved through the same layout pass.
- **FLD bounds**: `paintedWorldBounds` = parent LC's computed outline
  (rive-cpp `foreground_layout_drawable.cpp:95`).

## Coverage justification (census, 601 files)

| feature | files | tier |
|---|---:|---|
| flexDirection (598) | 104 | P0 |
| layoutAlignmentType (632) | 67 | P0 |
| gapH/V (498/499) | 57/62 | P0 |
| padding (512-515) | 56-59 | P0 |
| flexWrap (604) | 32 | P1 |
| positionType absolute (597) | 31 | P1 |
| position offsets (516-519) | 11-23 | P1 |
| margins (508-511) | 5-11 | P2 |
| NodeStyle fixed w/h (1066/7) | 5/7 | P2 |
| direction RTL (599) | 6 | defer |
| basisUnits (705) | 5 | defer |
| flexBasis (523) | 1 | defer |
| aspectRatio (546) | 1 | defer |
| min/max sizing (500-503) | ~0 | defer |
| borders (504-507) | ~0 | defer |
| justifyItems (1045) | ~0 | defer |
| overflow (605) | ~0 | defer |
| GridTrack/Item/Participant | 14/7/21 | P3 (real, minority) |

P0+P1 ≈ 95% of authored usage. Everything below P1 is evidence-deferred.

## Object model (what the solver reads)

- `LayoutComponent` (409): `width`(7), `height`(8),
  `fractionalWidth/Height`(706/707), `clip`(196), `styleId`(494).
- `LayoutComponentStyle` (420): flexDirection 598, flexWrap 604,
  gapH/V 498/499, padding 512-515, margin 508-511, position 516-519 +
  units 621+, positionType 597, layoutAlignmentType 632, corner radii
  640-643, width/height units 607/608.
- `LayoutNodeStyle` (1057): per-child width 1066/height 1067,
  fractionalWidth/Height 1057/1058, min/max + units.
- `LayoutSizingStyle` (1056): min/max w/h 500-503 + units 627-629.
- `ForegroundLayoutDrawable` (513): marker node; paint = own
  m_ShapePaints (empty in corpus — see FINDING_dv_enumeration).
- `NestedArtboard*` (92/451/452): instance sizing via
  `NestedArtboardLeaf.fit`(538), `fitToLayoutParent`(1098),
  `NestedArtboardLayout.instanceWidth/Height*`(663-668).

## Solver phases

### Phase A — measure (bottom-up)

For each layout item compute its *intrinsic* size:

- Shape/Text/FLD leaf: geometry bounds (path bbox, text advance,
  image pixel size) — most already have bbox code.
- NestedArtboard: the target artboard's intrinsic size
  (`artboardIntrinsicSize` exists) scaled by fit mode:
  `fit`(538) contain/cover/none/fill semantics, `fitToLayoutParent`
  (1098), fractionalWidth/Height weights.
- LC child: its own authored w/h (7/8) unless style units say
  fill/hug → defer to parent distribution.

Output: per-node `{minW, minH, maxW, maxH, basisW, basisH, fracW, fracH}`.

### Phase B — flex line breaking (wrap, P1)

Main axis = direction 598 (row/column; RTL 599 deferred). Collect
items' outer sizes (basis + gap). If wrap 604 == noWrap: one line.
Else greedy-fill lines at container main size; wrapReverse flips order.

### Phase C — main-axis distribution

Per line, distribute free space:

1. Fixed/basis items take their size.
2. `fractionalWidth/Height` (fill) items split remaining space
   proportionally — this is the dominant sizing mode in corpus files
   (component lists, dashboards).
3. hug items take measured intrinsic size.
4. min/max clamps (1056/1057) applied last — deferred props still
   honored when present (cheap clamps, not a feature).

### Phase D — cross-axis alignment + spacing

- `layoutAlignmentType` (632): align items within line cross axis
  (start/center/end/stretch — stretch resizes cross size).
- gapH/V (498/499) between items; padding (512-515) insets the
  content box; margin (512-515→508-511) outsets items.
- `justifyItems`/justifyContent deferred (unused).

### Phase E — absolute items (P1)

`positionType`(597)==absolute: skip flex flow; position from
position offsets (516-519) + units against the padding box.

### Phase F — grid (P3)

GridTrack(1058)/GridItemPlacement(1068)/LayoutParticipant(1066):
track sizing + placement. Minority (14-21 files) — implement after
flex core is green; can reuse Phase A measures.

## Output contract

The solver produces, per layout item, a **computed rect**
`{x, y, w, h}` in the parent's content space plus the world transform
chain already handled by `effectiveWorldRaw`. Consumers:

1. `emitArtboardPaints` layout-box pass — replace whole-box paint
   with per-item rect (class-2 fix).
2. `ForegroundLayoutDrawable` emission — item rect + own paints.
3. `NestedArtboard*` expansion — instance rect from Phase A/C sizing
   (class-1 fix); `artboardId` target subtree drawn into it.
4. Text/layout-bound content — text measures feed Phase A.

Solver runs once per `collectOps` frame evaluation (values may be
keyframed/bound — re-solve when inputs change; P0 ignores animation
of layout props, which census shows is rare).

## Deferred (evidence: ~0-6 files each)

flexBasis, aspectRatioAxis, min/max sizing (beyond cheap clamps),
borders-as-layout, justifyItems, overflow, direction RTL,
basisUnits, grid (P3 — real but minority).

## Non-goals

- No constraint solving (IK/scroll constraints are separate classes).
- No text shaping inside the solver — text measure is an input.
- No animated-layout interpolation — static solve per frame.

## Risks

- **Units**: position/padding/margin/border have `*UnitsValue`
  siblings (points/percent/flex) — percent resolves against parent
  box; must read units, not just values.
- **styleId indirection**: LC→style is by id (494), NodeStyle by
  child — resolution tables needed (same id→index machinery as
  artboardId).
- **Nested layout**: LCs inside LCs — solver must recurse bottom-up;
  depth bounded by file nesting (~3 observed).
- **Intrinsic text measure**: requires font metrics — the
  FontAsset/FileAssetContents path exists (emptybind proved bytes
  decode); glyph advance may need the canvas text measure or a
  cached approximation. Flag: measure can start as bbox-of-runs.
EOF
cd /Users/larsde/src/koru-rive && git add docs/layout-solver.md && git commit -m "design: layout solver — evidence-scoped phases for t4f

Measure->wrap->main-axis->cross-axis->absolute->grid; per-item rect
contract feeds class-2 paints, FLD bounds, class-1 instance sizing.
Census-justified P0/P1/P2/P3 tiers; deferred list + risks (units,
styleId indirection, nested recursion, text measure)." && git log --oneline -1 && hc send t42 "LAYOUT SOLVER DESIGN DOC COMMITTED — docs/layout-solver.md ($(git rev-parse --short HEAD)). Phases: A measure (intrinsic sizes incl NestedArtboard fit/fitToLayoutParent) -> B wrap line-breaking -> C main-axis distribution (fractional fill dominant) -> D cross-axis align+gap+padding+margin -> E absolute position -> F grid (P3). Output contract: per-item computed rect consumed by LC-paint pass (class-2), FLD bounds, NestedArtboard expansion (class-1). Census numbers embedded as coverage justification; deferred list explicit (flexBasis/aspectRatio/minmax/borders/justifyItems/overflow/RTL ~0-6 files each). Risks named: units siblings, styleId indirection, nested-LC recursion, text measure needs font metrics. Design only — implementation is t4f's after list-binding."