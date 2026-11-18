# Interactive-input stack — design note (joystick_databound_keyframe_test scope)

Status: design only, no implementation. Reversible — every layer below can
land independently behind the same ops contract.

## What the forcing file actually exercises

`joystick_databound_keyframe_test.riv` (4 KB, 46 objects) is driven in
rive-cpp by exactly one call per frame:

```cpp
stateMachine->pointerMove(Vec2D(artboard->width() * i / frames, 250.0f));
stateMachine->advanceAndApply(0.2f);
```

No `pointerDown`, no `pointerUp`, no `pointerExit` — the test exercises the
**move-only** path. That bounds the first slice hard.

## The mechanism, traced through rive-cpp sources

1. **SM listener dispatch.** `StateMachineInstance::pointerMove`
   (`state_machine_instance.hpp:237`) routes the point through the SM's
   listener tree. This file has one listener: obj52 type114
   `StateMachineListenerSingle`, name `Rectangle`, props `{138:name,
   224:5, 225:4}`. Our eval has zero listener dispatch today.

2. **Handle source.** The listener feeds a handle source (the drag/hover
   target). `Joystick::update` (`joystick.cpp:62`) reads
   `m_handleSource->worldTranslation()`.

3. **Joystick normalization.** `Joystick::update` maps the handle's world
   position through `m_inverseWorldTransform` then
   `localBounds.factorFrom(pos)` → normalized `(x, y)` ∈ [0,1]² using
   `width()`, `height()`, `originX()`, `originY()` (props 305–308). Result
   lands on `Joystick.x`/`Joystick.y`.

4. **Animation scrub, not trigger.** `Joystick::onAddedClean`
   (`joystick.cpp:35`) resolves `m_xAnimation =
   artboard()->animation(xId())`, `m_yAnimation =
   artboard()->animation(yId())` — direct animation references by id
   (props 301/302; obj21 carries 302). `apply()` scrubs each animation's
   playhead to the normalized value. **The animations are position→value
   remaps**: playhead time selects which bound keyframe value lands.

5. **Data-bound keyframe values.** `yAnim` (obj31) / `xAnim` (obj38) own
   the pk=70-bound `KeyFrameDouble`s. `boundKfValue` (implemented,
   verified correct-by-construction) resolves VM scalar → keyframe value
   once the animations actually play. The VM props are named
   `xStartPos`/`xEndPos`/`yStartPos`/`yEndPos` (type431 defs, objs 2–5) —
   the animation endpoints ARE the VM data. This is the "bind at comp
   time against our store" pattern Lars described, exercised by the
   reference fixture itself.

6. **The SM's own animation** (`joystickAnim`, obj26, active per
   `smActiveAnimIdx`) animates `Joystick.y` (prop300, slot10/key300
   keyframes, objs 27–30) — SM-driven motion layered under the
   pointer-driven scrub.

## Contract surface needed

- **`pointer.move {r, ab, x, y, frame[, id]}`** — scheduled positional
  event, same latest-event-at-or-before-frame semantics as
  `RIVE_INPUTS`/`input.fire`. Per-Riv event list (the control-block
  migration already recommended for `g_smInputs` applies here too).
- **Listener dispatch** — point → owning listener. Needs world-space hit
  testing: `effectiveWorld` + bounds exist; `ListenerAlignTarget`
  (type126) alignment semantics are a later refinement.
- **Handle/joystick state** — per-artboard mutable component state
  (handle position, joystick x/y). Today all eval state is globals or
  pure functions of (graph, frame); this is the first genuinely
  stateful-per-artboard surface. Smallest honest form: a per-`Riv`
  control block keyed by (artboard, component slot), populated by the
  input schedule at eval time — deterministic, replayable, and it makes
  ops a pure function of `(file, event-log, frame)` again.
- **Animation scrub at fractional time** — joystick positions are
  continuous; `keyframedValue` takes `i64` frames. Needs an f32-time
  variant (interpolation math already exists, just widen the input).

## Smallest honest slice (ordered)

1. `pointer.move` verb + per-Riv scheduled-event log + env-seeded
   `RIVE_POINTERS="x,y@frame;..."` for probes.
2. Move-event → listener hit dispatch for `StateMachineListenerSingle`
   (bounds check only; no drag state machine yet).
3. Handle position → `Joystick.update` normalization (props 301–308).
4. `apply()` scrub: `keyframedValueF32(time)` variant; feed
   `boundKfValue`-resolved values.
5. Verify: `ops` diff baseline vs `vm.set(prop:0,"200")` at frame 30 —
   the diff that has been pending since the verbs landed. Then
   `pointer.move` sweep reproduces the knob trajectory vs the
   rive-cpp silver frames.

## Explicit non-goals this note does not cover

- `pointerDown`/`Up`/`Exit`/`Miss`, drag-state semantics, multi-pointer.
- Gamepad/keyboard/semantic listeners (types 155+).
- Listener *actions* firing SM transitions (ListenerAction type125) —
  needed only if a fixture exercises them; joystick's listener appears
  to feed the handle directly.
- Nested-artboard pointer routing (`pointerMiss` hosted-machine rules).

## Risks

- **Hit-testing correctness** — listener bounds vs artboard bounds vs
  nested transforms; get it wrong and events land on the wrong listener.
  Mitigate: this file has exactly one listener; generalize after proof.
- **Timebase** — rive advances in seconds (`advanceAndApply(0.2f)`);
  our frames are 1/30 s ticks. The scrub needs the file's fps/timebase,
  not assumed 30 — check `frameRate` prop on the artback/SM before
  hardcoding.
- **Statefulness creep** — per-artboard mutable state is new; keep it
  inside the per-Riv control block, never globals, or replay parity
  dies.
- **VM write timing** — `vm.set` is eager-mutate; joystick scrubbing
  reads VM values per frame. Ordering (set-then-eval per frame) must be
  part of the scenario contract, not implicit.

## Evidence anchors

- Test driver: `rive-cpp/tests/unit_tests/runtime/data_binding_keyframes_test.cpp:272`
  (`"Data binding keyframes animated by joysticks"`).
- Joystick scrub: `rive-cpp/src/joystick.cpp:35-110`.
- Listener object: spec obj52 (type114, `Rectangle`).
- Bound keyframes: objs 34/36 (yAnim, key14) and 41/43 (xAnim, key13),
  all type447 pk=70 paths `[0,0]`–`[0,3]`.
- Existing pieces: `vm.set`/`input.fire`/`vm.bind` verbs,
  `boundKfValue`, `RIVE_INPUTS` schedule, `smActiveAnimIdx`,
  `keyframedValue`, `effectiveWorld`.
EOF
echo done; wc -l /Users/larsde/src/koru-rive/INPUT_STACK.md 2>/dev/null; ls /Users/larsde/src/koru-rive/INPUT_STACK.md 2>/dev/null || echo "MISSING"