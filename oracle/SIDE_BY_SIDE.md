# Side-by-side: ours vs reference

Each row is `OURS | REF` at matched frames. REF = `render_browser.mjs`
(rive_canvas 2.37.0, headless Chromium, deterministic tick pump — the
decided backend; `rive_webgl` available via the same script).
OURS = `render_*.k` offscreen probes (magenta clear, `probe:step` replay).

Frame mapping (STATE.md §8): clfp `frame = 2*(tick-1)`; dsm/hw `frame = tick-1`.

## component_list_follow_path — artboard Main (500×500)

| tick | ours frame | pair |
|---|---|---|
| 1 | 0 | ![clfp t1](images/pair_clfp_t1.png) |
| 5 | 8 | ![clfp t5](images/pair_clfp_t5.png) |
| 10 | 18 | ![clfp t10](images/pair_clfp_t10.png) |

- <check> Tier-1 frame-0 transforms/styles/colors/V-coords vs golden → <verdict> MATCH (≤0.0003 scale delta; stroke draw order swapped — cosmetic, non-overlapping).
- <check> live gallery_live window → <verdict> PASS (160k nonzero px, 0 fallback, ~1,200 frames).
- <check> pixel-level RMSE vs ref → <verdict> calibration-only (142.3 → 48.7 after stroke-channel fix; residual = bg-source/transform details).

## hello_world — artboard New Artboard (500×500)

| tick | ours frame | pair |
|---|---|---|
| 1 | 0 | ![hw t1](images/pair_hw_t1.png) |

- <check> static-shape parity vs ref tick 1 → <verdict> see image; hello_world has no SM gating — coverage should match closely.

## component_list_default_state_machine — artboard Main (500×500)

| tick | ours frame | pair |
|---|---|---|
| 1 | 0 | ![dsm t1](images/pair_dsm_t1.png) |

- <check> ref SM name → <verdict> FIXED — the file's SM is "Main Machine" (not "State Machine 1"); earlier render was unbound+wrong-SM → transparent right half. Correct invocation: `BIND_VM=1` + `sm="Main Machine"`.
- <check> coverage parity → <verdict> DIVERGENT — ref nonzero-alpha 25,000 px bbox x[0,249] y[0,99] (left column of bound rows); ours 40,000 px bbox x[0,499] y[0,79] (full-width band). The named ViewModel-binding + layout gaps (§6.1/§6.2) — pair is UNVERIFIED, not a pass.

## Named live-surface defect (banked, undiagnosed)

**Flicker-then-disappear** on the live gallery surface — candidates:
per-frame `kr/rive:open`+`free` churn, ops empty past SM range
(disproven offscreen at fr≤500 — stable), transform stack imbalance in
the shared live canvas, or path-handle lifecycle under sustained replay.
Diagnose after this doc lands.
