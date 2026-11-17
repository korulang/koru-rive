# SCENE — koru-rive

## What this is

A **Koru-native Rive runtime** — not a wrapper around `rive-native`, and
not a CPU rasterizer. `.riv` files decode into typed object graphs,
evaluate (artboards, animations, state machines, view models, layouts,
assets, clipping, nested content, inputs), and emit **renderer-neutral
operation streams** (`kr/rive:ops`). Consumers replay those streams
through Koru-native verbs — path, mesh, image, text, transform, clip —
on whatever surface realization selects.

## Why it exists — the forcing function

This repo exists to exercise **Koru's realization and variant systems**
through a real, demanding workload. The consuming interface must be
**uniform**: one ops contract, implemented first on **Metal**, written so
that variant/realization surfaces **monomorphize it to static calls**
tomorrow. i915 is the named second arm. If the renderer needed dynamic
dispatch, boxing, or per-backend special-casing to work, the
realization layer failed — the workload is the instrument that proves it.

Every rendering decision is therefore also a toolchain decision: a verb
that can't express a Rive op is a missing realization surface; a backend
that can't batch is a variant gap. Defects found here land in `koru`,
`oshun`, or this repo — never routed around in consumers.

## The oracle contract

Claims are pixel claims, verified against **browser-rendered Rive
references** — never self-referential. Gates measure ink mass, ink bbox,
coverage gap, and exact pixels. `oracle/gallery.html` + `oracle/images/`
are the standing eyeball surface: **metric PASS is not visual identity** —
the human (or a vision-model audit, `oracle/eyeball_package/`) is the
taste-gate the metrics can't replace. Named residuals are documented,
never hidden.

## What it says no to

- No `rive-native` wrapping, no vendored C++ runtime as the renderer.
- No CPU-only rasterizer as the destination — software scanline exists
  as a forcing/verification surface, not the architecture.
- No "good enough" gates — a fixture that can't be honestly verified
  stays LIMIT/NOTE until it can.
- No building machinery without a motivating fixture (number inputs,
  triggers: scoped out on census evidence, not oversight).
- No degraded fallbacks — real surface or loud failure.

## State of the world

`STATE.md` is the running ledger; `PHASE4_SCOPE.md` the phase plan.
Software raster 5/5 native gates, Metal 5/5 gates, image pipeline live
on darwin. Named deltas: CPU clip masks, round-only stroke joins,
per-eo-seg stencil sub-passes, cin rect-semantics residual, i915 future.

## Fleet

Workers run under arbiter posture (`hc`), autonomous between receipts.
Commits are the receipts; galleries are for eyeballs.

---

*Installed as a charter file. Full ADD methodology (skills, challenges,
reconcile) available via `arbiters-init` if wanted — SCENE.md stands
alone either way.*
