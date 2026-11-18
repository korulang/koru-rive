# Seam instrumentation — first slice

The Rive renderer is the instrument; Koru and the libraries are the product.
This document describes the instrumentation discipline that turns a pixel
difference into a **layer** and a **missing library surface**, instead of a
named residual.

## Two axes

**Vertical (pipeline seams) — where the pixels come from**

| seam | recorded fact | reference |
|---|---|---|
| scene | object graph, transforms, animation values, VM bindings, text runs | C++ `oracle/dump` |
| ops | op kind, path hash, paint, clip stack, text, mesh | C++ stream + ours |
| verbs | verb name, args, realization, variant, static/dynamic, fallback | compiler + backend tap |
| raster | coverage, clip mask, blend, glyph raster, edge pixels | native trace + images |
| oracle | region facts, envelope, ambiguity | browser + native backends |

The first slice instruments the **raster/clip seam** for `kn_clip`. The
compiler-realization seam is the next increment.

**Horizontal (realization choices) — whether the workload is forcing the
library**

For each op/verb: which realization and variant were selected, whether it
monomorphized to a static call, and whether it fell back to dynamic dispatch
or a predicate. A Rive op that forces a fallback is a library gap, and the
report should say so at build time, before pixels.

## First-divergence rule

For every gate, compare in order and stop at the first layer where ours
differs from the reference:

1. **Scene/ops** — if the command stream differs, fix the runtime first.
2. **Verb/raster** — if the commands match but the coverage/mask/edge differs,
   fix the backend/library surface.
3. **Pixels** — if the commands and masks match but the image differs, the
   residual is oracle or color-management class.

The report must name the layer, the evidence, and the missing surface. “Named
residual” without a layer is not an acceptable endpoint.

## Trace contract (v0)

The native canvas emits one JSONL line on stderr per path-clip push when
`KORU_TRACE_CLIP` is set:

```
KORUTRACE {"kind":"clip.push.path","idx":0,"w":500,"h":500,
           "eo":0,"inside":23094,"edge":483,"mid":0,
           "bbox":[274,146,445,317],"hash":"0x58e894d2e004fc4"}
```

- `mid` counts mask pixels with a value other than 0 or 255. A binary mask
  reports `mid=0`; a fractional-coverage mask reports `mid>0`.
- `edge` is the binary perimeter count; `inside` is the mask area; `bbox` and
  `hash` align the mask to the op stream.
- The line is stderr, so it works without filesystem access and can be
  captured by the probe runner.

The schema will grow by plane (`plane: "raster"`), a stable `id`/`parent`
chain, and a compiler realization record. Keep it small; instrument behind a
flag; zero-cost when off.

## First slice: `kn_clip`

Run:

```sh
PYTHON=/path/to/python-with-numpy-pillow ./oracle/trace_kn_clip.sh
# or let the script use: uv run --with numpy --with pillow python
```

The script captures four layers for the same fixture and writes
`oracle/first_divergence_kn_clip.md`:

1. C++ command stream (`oracle/dump clip_tests.riv`).
2. Our op stream (`opsdump_clip0.k`, ab=42, frame 0).
3. Native clip-mask trace (`KORU_TRACE_CLIP=1` on the native software surface).
4. Pixels (`oracle/images/kn_clip.bmp` vs `ref_clip_t1.png`).

Before the fix:

- Scene/ops: **MATCH** — 2 clip pushes, 1 draw, color `ff880000`, transform
  `258.9,176.3`; the C++ stream is `5/3` and `6/12`, draw `6/4`.
- Clip mask: **DIVERGES at coverage** — `mid=0`, `inside=23094`, `edge=483`,
  bbox `[274,146,445,317]`; reference edge has 394 blended px.
- Pixels: anti-aliasing `ours=0`, `ref=394`; frame-diff `0.000%`.

First divergence: **raster / clip coverage**. Missing surface: **fractional
clip-mask coverage** in `oshun/canvas/index.koru-native.kz`:
`rasterizeClipMask` wrote 255/0, and `clipCov` sampled `!= 0`.

After the fix (4×4 supersampled mask; `clipCov` multiplies the fractional
coverage):

- Clip mask: `mid=515`, `inside=23350`, `edge=486`, same bbox/hash.
- Pixels: anti-aliasing `ours=298`, `ref=394`, ratio `0.76`; frame-diff
  `0.000%`; registration `0.00`.
- `kn_clip` **PASS** and `knm_clip` **PASS**; full gate table **23 PASS /
  10 FAIL**.

First divergence after the fix: **none at the instrumented seams**. The clip
seam is closed; keep this trace as the regression instrument.

Next action: the compiler-realization seam (`koruc` build report: verb,
variant, static/dynamic, fallback).

## Follow-on slices (2026-11-18)

The same discipline closed four more findings:

- **`dsm` — pose/probe layer.** The probe opened `ab: 9` at 1:1 while the
  reference is the row (`ab: 20`) at 2.5×. The scene/pose divergence was in
  the probe, not the renderer; fixing the probe made the gate PASS.
- **`kn_hw` — fill coverage.** The glyph-edge notches came from the 2×2
  supersampler in `fillContours`; 4×4 coverage moved `ink-coverage` from the
  notch defect to 1.33% and the gate PASSes (AA 968/1097, frame-diff 0.000%).
- **`cl1_item` — VM binding.** `boundRunText` fell back to the first
  ViewModel instance when there was no row scope, so a standalone item
  rendered a row value (`THREE`) instead of the template (`text`). The
  fallback is gone; a data-bound run keeps its template unless a row scope
  or explicit `kr/rive:vm.bind` is active. `cl1_item` PASSes; the `clfp_item`
  probes bind VM 2 instance 0 explicitly and stay PASS.
- **`kn_clip` / `knm_clip`** — fractional clip-mask coverage, above.

Full table: **26 PASS / 7 FAIL**. Remaining are the deliberate residuals:
`iba`/`deam`/`hff` vacuous backdrops, `knm_cl1`/`knm_cl2`/`knm_hw` Metal
text/AA, and `mesh` (NOTE, dashed stroke). The next seam is the compiler
realization report.

## Work split

**Visual / raster judgement (this agent):** oracle image analysis, coverage
and AA interpretation, first-divergence report reading, ensemble/envelope
classification.

**Non-visual handoff (SWE-2 or another text/code model):** trace-schema and
parser work, op-stream alignment, C++/ours event matching, harness/build
plumbing, test scaffolding, and code review. SWE-2 is not registered as a
subagent provider in this harness at the moment; when it is exposed, these
tasks are the clean handoff boundary.

## Files

- `oracle/first_divergence.py` — layer parser + report generator
- `oracle/trace_kn_clip.sh` — end-to-end slice runner
- `oracle/first_divergence_kn_clip.md` — generated report
- `opsdump_clip0.k` — command-plane probe for `clip_tests`
- `oshun/canvas/index.koru-native.kz` — `KORU_TRACE_CLIP` clip-mask trace

## Stale-artifact trap (2026-11-18)

A first-divergence report is only as good as the artifact it reads. The
`iba`/`deam`/`hff` ruling initially named a verb/raster bug because the
committed `ours_*_t1.bmp` files were 100% white. Fresh renders produced
the spec backdrop and all three gates passed; the macOS clip trace showed
a full 504×504 mask, so the fill was realized. The divergence was the
**artifact**, not the renderer. Rule: refresh the render, record its hash
and mtime in the report, and only then attribute a layer. A stale
`ours_*` file is indistinguishable from a real renderer bug in a
first-divergence walk.

## Metal text seam (2026-11-18)

The text fill is forced evenodd so the Metal stencil-parity passes
subtract glyph counters (the old per-contour ear-clip filled them). The
per-call EO path renders at 4× and box-downsamples for geometric AA.
`knm_cl1`'s blobs are gone and `knm_hw`'s ink-coverage drops to 2.65%,
but both still fail `anti-aliasing` (0.38/0.39 of ref) and `ink-colour`:
the browser font AA/hinting spreads ink over more edge pixels than the
outline-glyph raster. 8× supersampling did not improve the count, so the
lever is font rasterization, not path-fill samples. This is the named
text-raster residual; the hole/coverage part of the seam is closed.

## Metal text seam closed (2026-11-18)

The text seam is closed: glyph fills are evenodd (counters subtracted),
both per-call Metal paths render at 4× and box-downsample, and the
composite uses the straight fill colour instead of the premultiplied
readback. `knm_cl1`/`knm_cl2`/`knm_hw` PASS; full table 32/1. The
window close now flushes the pending batch; the batch optimisation stays
disabled (`g_metal_batch=false`, named delta) because its command buffer
errors. A blur was tested and rejected (AA vs local-fidelity/ink-colour).
The only remaining failure is the `mesh` NOTE.
