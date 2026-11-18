# Finding — data_viz_demo drawable-count: nested artboard instances are never expanded

Commission leg: name WHICH drawables `kr/rive:opsdump` drops on
data_viz_demo (reference 44 draws / 8 clips vs ours 3 / 1) and the rule
that drops them. Instrument: `probe_dv.k` (abnames + inspect + opsdump at
the name-resolved index, `ab:315` = `Main`), ref side `oracle/dump`.

## The drop rule

**Plain nested-artboard instances (`NestedArtboard` 92 /
`NestedArtboardLayout` 452 / `NestedArtboardLeaf` 451) participate in
transform composition but are never expanded into their target artboard's
drawable subtree.** `collectOps` expands exactly one instance mechanism —
`ArtboardComponentList` (559) rows — and nothing else.

Evidence:

- `Main` (772×1058) holds 3 direct `Shape` backgrounds
  (`ff190e25`, `ff11111b`, `ffffffff`) — ours emits exactly those 3 draws.
- Its remaining content is ~7 `NestedArtboard*` objects parented to
  `LayoutComponent`s, each carrying `artboardId` → the component
  artboards (`HorizontalBars`, `ColorGuide`, `VerticalBars`, `LineBars`,
  `Data`, `Pie Chart`, `Circles`) plus a `NestedStateMachine` child.
  (`/tmp/dv_probe.txt` inspect lines ~330-950; 30 NestedArtboard refs.)
- The reference `Main` block draws 44 paths / 8 `clipPath`s — the 41
  missing draws are the chart artboards' internals, including their
  clips (explains the clip divergence on this file too).
- `node_type_keys` (`rive/index.kz:1435`) already contains 92/451/452 —
  instances get correct world transforms — but no traversal arm emits
  the target artboard's children under that transform.
- Corpus 30/30 didn't catch it: the sweep compares artboard *sections*
  standalone, so each component artboard passes on its own; only the
  root-with-instances case exposes the missing expansion.

## What the fix side needs (t4f)

For each `NestedArtboard*` under the scoped artboard: resolve
`artboardId` (key 197) → target artboard object index, emit that
artboard's drawable subtree under the instance's composed transform.
Open sub-questions the file raises: `NestedArtboardLeaf.fit` (538) /
`fitToLayoutParent` (1098) sizing, `NestedStateMachine` (which SM/state
the instance runs), `dataBindPathIds` (582) / `isStateful` (1014) view-
model scoping, and recursion depth (artboards instancing artboards).

## Reproduce

    koruc run probe_dv.k        # then ./a.out <data_viz_demo.riv>
    ./oracle/dump rive-cpp/tests/unit_tests/assets/data_viz_demo.riv 1 0.008335
    python3 oracle/authored_parity.py   # names drawable-count first
```

`ab` is the object index — resolve by name via `abnames`, never ordinal.
`Main` = 315, component artboards = 390/653/927/1166/1537/1897/2066.
```

Status: mapped, not fixed. t4f owns the expansion arm.
EOF
for d in gradients sm_conditions scroll_view; do true; done
cd /Users/larsde/src/koru-rive && git add probe_dv.k oracle/FINDING_nested_artboard_drop.md && git commit -m "$(cat <<'EOF'
finding: data_viz drop-rule = NestedArtboard instances never expanded

probe_dv.k (abnames+inspect+opsdump @ab:315): Main's 3 direct shapes
draw; ~7 NestedArtboardLayout/Leaf instances (artboardId -> the 7 chart
artboards + NestedStateMachine children) contribute zero ops. Ref draws
44/8clips — the missing 41 are instance internals. node_type_keys has
92/451/452 for transforms but no traversal arm expands them; only
ArtboardComponentList rows get expansion. Corpus 30/30 missed it because
sections compare standalone. Fix side: t4f.
EOF
)" && git log --oneline -1