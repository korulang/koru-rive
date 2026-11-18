# L1 census — riv2k emitter coverage vs corpus needs (no-compiler prep)

Static inventory of what the pipeline covers today and where the
corpus demands more. Sources: `rive/index.kz` tables + dispatch sites,
`oracle/CORPUS_SWEEP.txt` (392 fixtures), `oracle/TIER1_DEEP.txt`,
`oracle/goldens/corpus/` (433 tier1 streams). Compiler-independent —
no `koruc` needed.

## Coverage stack

| layer | coverage | gap |
|---|---|---|
| decode schema | 364 type_keys, 681 prop_entries (generated tables) | schema is generated from rive-cpp — complete for known types; unknown type_keys decode but eval-skip |
| riv2k serialize (`graphdump`) | all `PropValue` kinds: u/d/c/b/x; all object fields | none — lossless by construction (verified: hello_world 19 objects + 33 KB font blob round-trip) |
| riv2k materialize (`fromgraph`/`fromfile`) | spec → `Riv{bytes,objects}` + schema name refill | none at this layer |
| eval dispatch (`collectOps`) | 50 type_keys compared; 33 node_type_keys; 9 vertex_type_keys; 171 comp_type_keys | eval-skips everything not dispatched — silent for unknown types |
| op emission (`OpRec`) | kinds 0,1,2,4,5,6,7,8,9,10,11 via `op0` | **kind 3 (quad) never emitted** — quads are elevated to cubics at path build (`index.kz:4459`); kind 3 is reserved/dead in the stream. Contract lists it; emitters should treat cubic as canonical |

## Sweep state (CORPUS_SWEEP.txt, 392 fixtures)

67 PASS / 27 PARTIAL / 297 FAIL. The 67 PASS are almost entirely
unit-test-shaped fixtures (constraints, listeners-on-simple-trees,
scripted-property paths, nested-artboard cycles, RTL lists) — plus a
handful of `scripted_*`/`script_*` names that pass because they exercise
non-Lua paths. **Every real authored demo is 0/30.**

## FAIL families (297, name-bucketed)

| cluster | ~count | what it needs | contract section |
|---|---|---|---|
| control plane: data_bind, viewmodel, stateful, listener, trigger, event, script | ~80 | `vm.set/get`, `input.fire`, VM instance materialization, SM input schedule as data | §3–§4 (missing verbs) |
| authored scene: nested, component_list, artboard, layout, constraint, follow_path, virtual | ~60 | nested-artboard eval completeness, list virtualization, layout solving | §2 (eval depth) |
| render features: text(18), image(9), mesh, gradient, dash, trim, blend | ~40 | text shaping runs, image decode path, mesh tessellation, gradient paints | §5 (op expressiveness) |
| misc/other | ~117 | per-fixture triage needed; many are multi-artboard files where one bad artboard fails all 30 frames | — |

## Op-kind usage (goldens + emit sites)

Kinds actually exercised by PASSing fixtures: path verbs (0–5),
transform stack (6–7), draw (8), clip (9–10), image (11). Kind 3
unreachable. Dash fields (`dash`,`dashOff`) exist on OpRec and print
in `opsdump` but no PASSing fixture exercises them — first dashed
fixture will be a new coverage cell.

## L1 artifact implications

The binding surface (§3–§4 verbs) is the highest-leverage gap: ~80
fixtures fail on control-plane features that have NOTHING to do with
pixels — they need `vm.set`, `input.fire`, and VM materialization.
That cluster is also exactly what the Omni leaf contract needs anyway.

Renderer-feature gaps (text/image/mesh/gradient) are real but
orthogonal — they don't block the binding demo.

**Candidate ranking for L1:**
1. `joystick_databound_keyframe_test.riv` (~4 KB) — VM + SM +
   databound keyframes in one tiny file; smallest file that exercises
   the full missing-verb cluster. Best forcing function per byte.
2. `inventory_demo_test_v2.riv` (~388 KB) — the product-shaped pick:
   nested artboards + parent/child VM contexts + listeners + enums.
   Correct long-term target; heavier first census.
3. `data_bind_artboard_input` (PARTIAL 29/30) — already nearest to
   passing; one-frame divergence suggests a narrow bug, good warm-up.

**Census still needed when `koruc` recovers:** run `census_inv.k`
(abnames/smdump/vmdump) on candidates 1–2 to confirm artboard/SM/VM
counts before committing the pick.

## Emitter next legs (scoped by this census)

- riv2k serialize/materialize: DONE for the graph layer; no known gap.
- The emitter's real next leg is NOT serialization — it's the
  typed-schema surface (VM property definitions → Koru params for
  `std/ctx` binding), which is contract §4 work, gated on the
  control-plane verbs existing first.
- ops-parity harness generalizes: `parity_*.k` pattern works for any
  fixture — emitter + two probes + diff. Cheap to replicate per
  artifact once the L1 pick lands.
