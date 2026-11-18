# Gated-reveal / SM-materialization — design note

Two specimens, one class: content that exists in the file but only
materializes under a runtime gate our static expansion never fires.

## Specimens

**A — `data_bind_artboard_input` (script-gated, classified).**
`ArtboardPainter` LuaJIT bytecode (497B, `init/advance/update/ab/
instance/draw/late`) accumulates a timer; `draw()` emits the bound
artboard at t≈1.0. Verified: pk=876 resolver + 603→artboard render path
are correct (`sdraw→child2` byte-matches golden); `activeAnim=14`
constant rules out SM-state gating. Needs Lua→Koru transpile or a
script VM — **feature-sized, separate arc**, already logged in
`oracle/AUTHORED_PARITY.md`.

**B — `component_stateful_vm_instance [ParentArtboard]` fr29
(RETRACTED — parser artifact, not a reveal).** The "third draw /
default-VM instance / no position ancestor" was `tier1_compare.py`'s
last-frame bleed: each artboard's final frame body ran past its own
section into the next artboard's `--- static t=0 ---`/`--- sm0 ---`
prefix. With boundaries corrected, ParentArtboard is **30/30** and
`data_bind_artboard_input` is **30/30 on all three artboards** — the
"script-gated frame-29" was the same artifact. The gated-reveal
class currently has **zero confirmed specimens** in the corpus.

## What the gate probably is — candidates, evidence-ranked

> Post-retraction: candidates 1–3 below were ranked against specimen
> B's phantom evidence. Keep for the NEXT gated-reveal candidate, but
> no corpus file currently demands any of them.

1. **ViewModel state transition.** Rive VM property defs include a
   `state` kind (csvmi_2 obj7 tk448 "state"; enum value objects
   tk433 carry `561="Star"`). `deferred_viewmodel_instance_body.cpp`
   in rive-cpp exists for exactly this: an instance's *state* selects
   a different property-value set. If ParentArtboard's SM/input flips
   a VM state at t=1.0, a *state-variant* instance body could carry
   the third draw. **Cheapest to falsify**: dump the 437 instances'
   state fields + the SM transition's condition props (obj37-41 raw).
2. **SM-state content block.** The golden's own marker is
   `--- static t=0 ---` — the harness emits a *static* sub-block
   inside frame 29. If SM LayerStates can carry static draw content
   (a state that "freezes" a layer's pose), the third draw may be an
   SM state revealing a *default-bound* component — i.e. the same
   two 92-nodes re-evaluated with instance scope dropped to the
   artboard default VM. Explains "no position ancestor": a
   state-level draw, not a node transform.
3. **ArtboardComponentList / runtime list materialization.**
   `artboard_component_list.cpp` builds list rows at runtime; a
   state-gated list could instantiate the component with the
   artboard's *default* ViewModelInstance (obj4) — matching the
   82×79 values exactly. Heavier machinery; only if 1–2 falsify.

## Bounded vs feature-sized

**Bounded (this arc's reach):**
- SM transition *schedule* decode: which transition fires at
  frame 29, its condition (timer? bool input? state exit?), and
  which LayerState/AnimationState it enters. Our `smActiveAnimIdx`
  already walks states/transitions — extend trace to fr28→29.
- Default-VM instance resolution: `findVmInstance(vmId, ord)` with
  `ord=-1` already returns the artboard's default 437 (obj4) — the
  value side is solved; only the *trigger* is missing.
- If candidate 2 holds: gate the third emit on the resolved SM
  state — same pattern as `computeScrubOverrides` (state → emit
  delta), no new renderer machinery.

**Feature-sized (name, don't build):**
- Full SM semantics: transition conditions (bool/number/compare
  listeners), blend durations, state stacking, `ListenerAction`
  fire/advance — the input stack covers pointer only.
- ViewModel state bodies: deferred instance materialization,
  per-state property sets, state-transition events — needed if
  candidate 1 holds.
- Runtime component-list rows: list scope, focus, row recycling —
  needed if candidate 3 holds.
- Lua/script VM (specimen A) — orthogonal arc.

## Proposed slice order

1. Trace `smActiveAnimIdx` + state walk for ab15 at fr28 vs fr29 —
   name the firing transition and target state. (hours, bounded)
2. Dump SM section raw props (obj37-41 untruncated) + the 437s'
   state/variant fields — discriminate candidates 1 vs 2 vs 3.
   (bounded)
3. If candidate 2: implement state-gated emit for the default-VM
   instance — the render path already exists (nested expansion +
   `g_vm_bound` default scope). Verify fr29 closes to 30/30 without
   regressing 0-28 (the dbai lesson: unconditional emit costs 29
   frames to fix 1).
4. If candidate 1 or 3: write the feature-sized spec and hand to
   the fleet — do NOT half-build VM-state or list machinery inside
   this arc.

## Non-goals

- No Lua transpile (specimen A's arc).
- No general SM-condition evaluator beyond what step 1-2 need.
- No runtime VM instance *creation* — only resolution of instances
  already serialized in the file.
EOF
echo written; wc -l GATED_REVEAL.md 2>/dev/null || wc -l /Users/larsde/src/koru-rive/GATED_REVEAL.md