# LEAF CONTRACT — the consume surface for authored .riv content

Status: DRAFT v0, 2026-11-18 — commissioned under
`omni/commissions/rive-leaf.md` (L0). This document is the interface
BOTH realizations must satisfy: the dynamic path (`kr/rive:open` +
control verbs on a runtime-decoded file) and the static path (`riv2k`
build-time codegen module). Omni/oshun consumes only this contract;
nothing below names a backend, a decode strategy, or a file format.

A leaf is a loaded `.riv` file acting as a bounded surface: Omni owns
placement, z-order, layout, and the clock; the leaf owns scene
evaluation and emits renderer-neutral ops.

## 1. Handle model

```
leaf.open { path }            | ready *Leaf<ready!>
                              | failed string
leaf.free { leaf: *Leaf<!ready> }
```

Custody-tracked phantom ladder, same shape as `*Riv<loaded!>` today.
All mutable binding state (VM context, input schedule) lives ON the
leaf — never in module globals. (Today's `g_vm_*`/`g_smInputs` globals
are the named violation this contract exists to retire: one binding at
a time, env-var-only inputs, non-reentrant.)

## 2. Artboard selection

```
leaf.artboards { leaf }  -> names/indices   (today: abnames)
leaf.select    { leaf, ab }                 (today: ab: i64 param on ops)
```

`ab` is an index into the file's artboard list; name→index resolution
is a convenience, not a second identity. Selection may be per-ops-call
(the current `(r, ab, frame)` shape) or sticky — contract requires
only that ops accept an explicit artboard each call.

## 3. View-model binding

```
leaf.vm.instance { leaf, vm: i64 }        -> *VmInst
leaf.vm.set      { inst, path, value }
leaf.vm.get      { inst, path }           -> value
```

- `vm` identifies the file's ViewModel definition (index today via
  `vm.bind{r, vm, inst}` — vmId + instance ordinal).
- `path` is the Rive VM property path inside that instance
  (dotted/indexed — exact grammar pinned by the L1 census of real
  files; nested instances and lists are in scope, enums map to their
  declared members).
- `value` types: bool, i64, f64, string, color(u32), enum, list —
  the Rive VM property type set. Type mismatches refuse loudly.
- Values are RUNTIME state: a `riv2k` module declares the schema as
  typed params; `std/ctx(store)` injects at compile time for static
  content, `vm.set` drives live leaves. Same contract, two feeders.

## 4. State-machine inputs

```
leaf.input.fire { leaf, name, value, at_frame? }
```

- `name` = the SM input's declared name; `value` = bool today, number
  and trigger named extensions (number inputs were scoped out on
  corpus census 2026-11; trigger = fire-once semantics).
- Schedule semantics (existing, kept): a bool input holds its latest
  value at-or-before the render frame; events are ordered by frame.
- `at_frame` omitted → takes effect from the next ops call's frame
  (live-input semantics for pointer-driven leaves); explicit frame →
  deterministic scenario scripting (oracle use).
- Replaces `RIVE_INPUTS` env parsing as the ONLY input path; env stays
  as a probe convenience, never the contract.

## 5. Time

```
leaf.advance is NOT a verb — the playhead is a parameter:
ops { leaf, ab, frame }
```

`frame: i64` in the file's own keyframe-time units (the runtime reads
keyframe times as integer frames today — `keyframedValue` compares
`frame` directly against stored key times). OPEN: pin the unit
semantics against rive-cpp (seconds×fps vs frame indices) during L1 —
the contract fixes the *parameter*, the unit ruling lands with the
first scenario gate.

## 6. The ops stream — the actual product

```
ops { leaf, ab, frame }  ! op OpRec  | done usize
```

Pull-stream of `OpRec` records — the renderer-neutral contract canvas
verbs already consume:

| kind | meaning |
|---|---|
| 0 | open contour |
| 1 | moveTo (x1,y1) |
| 2 | lineTo (x1,y1) |
| 3 | quadTo (x1,y1)(x2,y2) |
| 4 | cubicTo (x1,y1)(x2,y2)(x3,y3) |
| 5 | close |
| 6 | pushMat — affine in (a,b,c,d,e,g) |
| 7 | popMat |
| 8 | draw — style/color/thick/join/cap/eo + path verbs in stream |
| 9 | clipPush — path clip geometry |
| 10 | clipPop |
| 11 | image — embedded asset blob draw (FileAssetContents bytes) |

`OpRec` fields as of HEAD: `kind, x1,y1,x2,y2,x3,y3: f64; style,
color:u32, thick: f64, join,cap,eo: i64, a,b,c,d,e,g: f64,
dash,dashOff: f64` (mat stack + paint params + stroke dash pattern —
renderer-lane additions; `opsdump` prints all of them). World-bbox
fields (`wx0..wy1`) were named for t4f but are NOT present in `OpRec`
at this revision — recorded as absent, not assumed. Exact per-kind
field usage is the canvas-verb contract's business, not redefined
here.

**Determinism rule (the conformance test):** identical
(file, artboard, frame, VM values, input schedule) → byte-identical
ops stream, on BOTH realizations. riv2k parity = diff of the two
streams, not pixels.

## 7. Realization seam

```
produce(leaf-state, ab, frame) -> OpRec stream
```

- DYNAMIC: `kr/rive:open` decodes bytes → object graph → eval.
- STATIC: `riv2k file.riv` emits a Koru module carrying the decoded
  graph as typed static data + the same eval → identical verbs.
- The contract names the SEAM, not the strategy: anything that
  satisfies §1–§6 is a legal realization. Specialized per-file codegen
  is a permitted optimization of the static path, never a contract
  change.

## 8. Refusal discipline

- Unknown artboard / VM id / property path / input name → loud
  refusal naming the missing key. No silent defaults.
- Unsupported feature (script-dependent file, unimplemented op kind)
  → named gap at load or first-ops, never degraded pixels.
- Both realizations refuse identically — a feature the static path
  can't express is a riv2k gap, surfaced by ops-parity, not hidden.

## 9. Audit — exists vs missing (2026-11-18)

| contract item | dynamic path today | static path |
|---|---|---|
| open/free custody | `open`/`free` on `*Riv<loaded!>` | n/a — module is compile-time |
| artboard select | `ab: i64` param; `abnames` lists | same |
| VM bind | `vm.bind{vm:i64,inst:i64}` — GLOBAL, one at a time | schema-as-params (L2) |
| VM set/get by path | MISSING | MISSING (params are the set surface) |
| input.fire | `RIVE_INPUTS` env only, bool only | same schedule, injected |
| ops stream | `ops`/`opsdump`/`collectOps` — OpRec kinds 0–10 | must match byte-identical |
| state per leaf | globals `g_vm_*`, `g_smInputs`, eval ctx | must not regress to globals |

## 10. Non-goals (inherited from rive-leaf.md)

No Lua interpreter or transpiler; no i915; no pixel-parity with
rive-cpp's rasterizer; no scene-level layout authority; no window
management. The leaf renders inside its allotted rect.
