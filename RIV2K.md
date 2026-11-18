# riv2k — build-time .riv → Koru module (static realization of LEAF_CONTRACT)

Status: IN PROGRESS, 2026-11-18. Commissioned under
`omni/commissions/rive-leaf.md` L2. Gate: ops-parity vs the dynamic
path (`kr/rive:open` + `ops`) — byte-identical OpRec streams on the
same (artboard, frame, VM values, inputs).

## Pipeline

```
file.riv ──build-time──> kr/rive:graphdump ──> canonical ASCII spec
                                                    │
                                              tools/riv2k.py emits
                                                    ▼
                              rivgen_<name>.kz  (static module)
                              - spec embedded as string literal
                              - open{} |zig -> fromgraph(spec) -> *Riv<loaded!>
                              - delegates: ops/vm.bind/abnames/... -> kr/rive:*
                                                    │
                                              koruc compiles
                                                    ▼
                              module.ops(ab, frame) ≡ dynamic ops(ab, frame)
```

The decode happens ONCE at build time. The generated module carries
the decoded graph as data; `fromgraph` materializes it into the same
`Riv` struct the eval already consumes — ONE eval implementation,
no drift, no second .riv parser.

## Canonical spec format (dumpGraph, landed e1d9…+)

Line-based ASCII, emitted by `kr/rive:graphdump`:

```
G <nobjects>
B <nbytes> <hex bytes>            # r.bytes — embedded assets
O <type_key> <slot> <parent> <parent_obj> <style_obj> <nprops>
P <key> <field> <kind> <value>    # per prop of preceding O
```

Prop kinds: `u`=uint dec, `d`=f32-as-u32-hex (bitCast, exact),
`c`=color hex, `b`=bool 0/1, `x`=<len> <hex bytes>.

Names are NOT serialized — `fromgraph` refills `type_name`/`prop.name`
from `typeName(key)`/`propEntry(key)` schema lookups (name-only
metadata; eval reads key/field/value). Assumption to verify: no
off-schema prop needs its decoded name for eval.

Measured on hello_world.riv: 19 objects, B=33413 (embedded TTF).
NOTE: the font bytes appear BOTH in `B` and inside a `P x` prop
(asset reference) — duplicated ~66KB hex each way. Acceptable for
MVP; dedupe is a named optimization.

## Remaining pieces

1. `kr/rive:fromgraph { spec: string } -> *Riv<loaded!>` — parses the
   spec into `Riv{bytes, objects}` (~80 lines zig; tokenizer + the
   five PropValue constructors; names via schema lookups; each object's
   `props` slice individually allocated — `free` discharges per-object).
2. `tools/riv2k.py` — run graphdump, embed spec, emit rivgen_*.kz.
3. Parity gate — script: same (ab, frame) through both paths,
   diff OpRec streams byte-for-byte. First artifact: hello_world.riv
   (already gated, goldens exist); then the L1 chosen artifact.

## Risks / open

- Spec size: hello_world spec ≈ 70KB text (font hex dominates). Koru
  string-literal limits unverified — if it refuses, chunk the spec or
  move bytes props to a sidecar table. Real authored files will be
  MBs — compression/dedupe is phase-2, named not hidden.
- `parent/parent_obj/style_obj/slot` semantics must survive
  materialization exactly — they drive hierarchy/style/slot lookup.
- VM/SM state is runtime (§3/§4 of contract): the static module
  inherits `vm.bind`/`RIVE_INPUTS` until L0 verbs land — parity gate
  runs pre-VM first, VM scenarios after.
