# Rive runtime — gap analysis + roadmap

Written against `omni/commissions/rive-runtime.md` (phases 0–4 + falsifiers,
decided 2026-11-16). Every item carries `<check> → <verdict>`; nothing below
is "verified" by adjective. Tier-1 = command-stream equality vs the
recording-Renderer goldens (`oracle/goldens/`); Tier-2 = pixel spread,
calibration only.

## Phase 0 — canvas vector verbs

| item | status | evidence |
|---|---|---|
| `draw.path` fill+stroke, transform stack, `clip.push.path`, path-handle custody | DONE — pre-existing in `libs/canvas` (`index.macos.kz`), exercised by riveprobe all session | <check> probe replay compiles+runs → <verdict> PASS |
| koru-native rasterizer part declares identical signatures | NOT-STARTED | <check> `index.koru-native.kz` path coverage → <verdict> unmeasured — phase-4 scope |
| stroke/fill channel routing in replay | DONE+gate-verified | <check> opsdump style=0 → stroke channels; RMSE 142.3→48.7 (calibration) → <verdict> PASS |

## Phase 1 — decoder

| item | status | evidence |
|---|---|---|
| header/ToC/object stream → typed graph | DONE+gate-verified | <check> `inspect`/`paths`/`transforms`/`pathops`/`abnames`/`keyed` probes on 4 fixtures → <verdict> PASS |
| schema from generated headers | DONE | prop table covers keys used; `PropValue` union measured |
| `riv:inspect` verb | DONE | `inspect*.k` probes banked |

## Phase 2 — player subset

| item | status | evidence |
|---|---|---|
| transform hierarchy eval | DONE+gate-verified | <check> Tier-1 frame-0 transforms vs clfp golden → <verdict> MATCH (≤0.0003) |
| path stream → canvas path (lines/cubics/close, rounded-rect/ellipse/polygon/star params) | DONE+gate-verified | <check> V-coords vs golden frame-0 → <verdict> MATCH at print precision; contour-truncation fix (`30a5e2d`) |
| solid fills + strokes + colors | DONE+gate-verified | <check> style/color/thick/join/cap/fillRule headers → <verdict> MATCH |
| linear-animation keyframe interpolation | DONE+gate-verified | <check> propFAnim/keyframedValue on transform+vertex keys → <verdict> PASS; animated color (`propColorAnim`) + opacity(18) eval added `f372fd8` — zero-effect on clfp, semantically owed |
| gradients / image paints | NOT-STARTED | <check> ops kinds 11+ → <verdict> unmeasured — no fixture gated on them yet |
| draw traversal / z-order | DONE-unverified | <check> stroke draw-order swap vs golden (cosmetic, non-overlapping) → <verdict> named, not blocking |
| Tier-1 gate coverage | PARTIAL | <check> frame-0 only on clfp Main → <verdict> full-frame sweep NOT RUN |
| Tier-2 pixel calibration | DONE (band.py, selftest 19+6, verify_harness 8/8) | calibration only per regime |

## Phase 3 — state machines / inputs / view models / assets

| item | status | evidence |
|---|---|---|
| SM selection/timing in ops path | NAMED-GAP | <check> `hasKeyframed(so.slot,18)` → 0 hits on clfp Main; no SM-state/layer eval reachable from `collectOps` — linear keyframe interp only → <verdict> SM-gated visibility unimplemented |
| inputs (pointer/keyboard → SM) | NOT-STARTED | display-only leaf by design |
| ViewModel list binding | NAMED-GAP | <check> dsm pair UNVERIFIED — ours 40k px full-width vs ref 25k px left-column (bound rows) → <verdict> §6.1 |
| layout solving (LayoutComponent positions/flex/clip) | NAMED-GAP | <check> component_list_1 pair divergent (9,761 vs 47,557 green px) → <verdict> §6.2 |
| embedded fonts → glyph paths | DONE+gate-verified | glyph-path emission committed earlier; HVAR/gvar parity parked |
| embedded images | NOT-STARTED | unmeasured |

## Phase 4 — stretch

| item | status |
|---|---|
| koru-native rasterizer path coverage | NOT-STARTED |
| i915 thin-subset | NOT-STARTED (scoped in `gpu-render-path.md`) |

## Named defects / open questions

- **Flicker-then-disappear (live surface)** — NAMED, undiagnosed. Candidates: per-frame open/free churn, ops empty past SM range (offscreen-disproven fr≤500), transform stack imbalance, path-handle lifecycle. Banked in `oracle/SIDE_BY_SIDE.md`.
- **gallery_live vs canvas/tests surface** — BOTH exist: `omni/rough/gallery_live.k` committed (`omni@e70139f`, live-verified); `canvas/tests/gallery.k` retired by regime but still in tree. Lars rules whether to delete or keep as offscreen harness.
- **595-fixture corpus coverage** — only ~4 fixtures gated (clfp, dsm, hello_world, cl_1 partial). Corpus sweep NOT-STARTED.
- **Tier-1 full-frame sweep** — frame-0 PASS only; per-frame V-coord diff across golden sections NOT RUN.
- **Package home** — `~/src/koru-rive` standalone (current); open question in commission stands.

## Suggested order (Lars rules)

1. Flicker-then-disappear diagnosis (live surface is the product surface).
2. Full-frame Tier-1 sweep on the 4 gated fixtures (cheap, widens the gate's teeth).
3. component_list_1 ViewModel-binding → layout (unblocks the biggest named gap).
4. SM-state selection in ops path (phase-3 core).
5. Corpus sweep (595 fixtures) once 1–4 land.
6. Phase-4 stretch (koru-native + i915) last.
