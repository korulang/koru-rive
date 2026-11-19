# Authored-file parity

`oracle/authored_parity.py` runs the reference rendering and our `kr/rive:opsdump`
on the same authored file, digests both, and names the first layer that differs.

    python3 oracle/authored_parity.py FILE              # one artboard, dumper reference
    python3 oracle/authored_parity.py --all-artboards FILE
    python3 oracle/authored_parity.py --golden FILE      # real-render reference
    python3 oracle/authored_parity.py --attribute AB FILE # per-class draws + skip reasons
    python3 oracle/authored_parity.py --save-baseline    # always with --all-artboards

Verdicts: `op-identical`, `divergent` (first layer named), `ref-unavailable`,
`ref-incomplete` (the reference cannot produce the content — see below).

This file is the state of record. Superseded findings were removed; git history
holds them.

## Current status (2026-11-19)

| file | artboard | draws ref/ours | verdict | remaining cause |
|---|---|---:|---|---|
| joystick_databound_keyframe_test | Main | 2/2 | **op-identical** | — |
| car_widgets_v01 | Main_Artboard | 612/628 | divergent | +16, layout-driven over-draw |
| | TIRE PRESSURE | 68/73 | divergent | +5 |
| | COMPASS | 413/417 | divergent | +4 |
| | G_Meter | 69/66 | divergent | −3, keyframe slot match |
| data_viz_demo | Main | 199/196 | divergent | −3 |
| | HorizontalBars | 40/34 | divergent | −6, per-run text |
| | ColorGuide | 38/38 | draw-order | order only (identity-set 38/38) |
| | VerticalBars | 31/33 | divergent | +2 |
| | LineBars | 20/20 | draw-order | placement |
| | Data | 45/46 | divergent | +1 |
| | Pie Chart | 16/16 | draw-order | placement |
| | Circles | 44/44 | draw-order | placement |
| jellyfish_test | Jellyfish | 2/1, 1/0 | divergent | mesh |
| inventory_demo_test_v2 | — | — | ref-unavailable | importer assert (`file_asset_importer.cpp:25`) |
| component_list_1 | Main | **17/17** golden | geometry | text advance only |
| component_list_follow_path | Main | **29/29** golden | draw-order | row colour + order |

Gate suite: **33 gates, 32 PASS, 1 KNOWN (mesh), 0 FAIL**, plus the leaf
self-test PASS (`oracle/run_gates.py`). `KNOWN` = a gate whose manifest label is
LIMIT/NOTE; only an unlabelled or PASS-labelled failure fails the suite.

## What is verified today

| capability | evidence |
|---|---|
| path geometry, fills, strokes, fill rule, blend mode | joystick op-identical |
| nested artboard expansion, instance clipping | nested fixtures byte-exact |
| colour animation, ancestor opacity culling | reproduces the reference's drawn set |
| data-bound component lists (rows, follow-path placement, list SMs) | draw counts equal the goldens exactly: 17 and 29 |
| root-artboard clipping | golden has one layout clip, never an artboard-bounds clip |
| per-handle leaf state (vm binding, input schedule, pointer channel) | `selftest.handles` passes on three fixtures |

## Open work

Each item carries the measurement that identifies it and the step that follows.
None is a missing predicate; all four are structural or blocked.

### 1. Clip grouping — smallest, best understood

car_widgets Main_Artboard emits **276 clips against the reference's 25**. Every one
comes from the `ClippingShape` (type 42) site: disabling that push drops the count
to 0.

The file has **17** `ClippingShape` components, and rive pushes one clip per
component, wrapping its subtree. Measured matches per component form **contiguous
runs** in stream order — 15 runs total, the largest covering 176 shapes.

**Next:** hold the clip open while the matched component is unchanged. The attempt
was made twice: the first landed in the wrong shape loop (this file has two
near-identical ones — anchor on the clipping block itself), the second declared the
held-component state *inside* the loop so it reset every iteration. The corrected
form was not finished: declare `activeCs` before the shape loop, pop when it changes,
pop once after the loop. Expect ~15 clips.

(Commit `61e9037`'s message says the matched component "alternates per shape" —
that was concluded before the matches were traced properly, and the run data above
supersedes it. The code in that commit was reverted either way.)

### 2. Layout placement — the largest

FLD rects, constraint targets and text clip rects sit at uncomputed positions.
LineBars' bars are a constant `+20 x / −118 y` off; Circles differs in y only;
`TransformConstraint` targets resolve correctly but the target's own position is
wrong by `(30.29, 57.66)` on a 25x110 box.

Three positioning regimes coexist in one artboard (explicit `Node.x`, bone-attached
content, nested layout components with direction/gap/padding), so a single stacker
does not sweep it. This is a layout pass, not a predicate.

### 3. Draw ordering — blocked on the reference

ColorGuide's 38 drawables are **identical** by (composed CTM, colour, style) and
ordered differently. Stream, reversed, DFS pre-order and row-major orders all fail;
ordering is material (703/703 draw pairs overlap on ColorGuide).

Getting further needs a stable drawable id in the reference stream. The recording
dumper exposes none on components, and it cannot be relinked here: `librive.a`
carries no `rive::Renderer` typeinfo, there is no renderer archive, and the shader
headers the renderer sources need are generated by a target the repo does not
record. The rebuild itself works (`rsync --exclude out`, patch, premake); only the
dumper's link recipe is missing.

### 4. Mesh

The gate's headline failure is a **496-pixel magenta seam** along the artboard
quad's shared triangle edge (the probe's clear colour showing through one pixel),
not our path data: the reference draws the same `ff313131` fill and our ops for it
are correct. The remaining colour/coverage disagreements are separate and unresolved.

### Smaller, named

- **text advance**: `component_list_1` drawable 4 is 0.73 units wider than the
  golden. Not `kern` (the font has no such table) and not PairPos (every pair
  adjustment for those glyphs traces zero). Next: single positioning or fractional
  advances.
- **G_Meter −3**: keyframe groups are matched by derived slot because the file
  carries no object ids.
- **per-run text**: the reference's text-draw counts differ between artboards with
  identical run structure, so the rule needs reference identity.
- **script VM (Lua)**: `scripted_*` fixtures need a Lua→Koru transpile or a script
  VM — feature-sized and separate; see `GATED_REVEAL.md`.
- **facade globals**: `g_activeAnim`, `g_blendFrom/T`, `g_cframe`, `g_rowVmid`,
  `g_instVmid`, `g_rowInstOrd` are still module-global; the restore is a `defer` so
  they cannot be left dirty, but they belong on the handle.

## Instrument truths

Every one of these was a way the harness lied; each changed a conclusion when fixed.

| truth | what it hid |
|---|---|
| draws are compared as **sets**, not positions | four artboards looked like paint failures and were ordering only |
| colours compare **8 digits** | we recorded gradient paints as opaque black for many rounds: `FF000000` where the reference has `00000000` |
| the **dumper binds no data** | data-bound lists render empty there: 1 vs 17 and 3 vs 29 draws. Use `--golden`; `ref-incomplete` flags it automatically |
| the baseline must be **regenerated** (`--all-artboards`) | an 11x clip divergence went unreported while drift compared against a months-old state |
| probes build to **unique paths** | `koruc run` writes a shared `./a.out`; a concurrent session swapped the measured binary |
| `oracle/dump FILE <frames> <dt>` | the second argument is a frame count, not an artboard index |
| the triangle trace used the **full affine** | it reported every triangle as a degenerate line |

Guards now in the harness: `ref-incomplete` fires only when the reference is under
half the golden (so a regression that reduces our draws cannot hide behind it), and
the leaf self-test fails when a probe produces no output (so a broken toolchain
cannot read as a pass).
