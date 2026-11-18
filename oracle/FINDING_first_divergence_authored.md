# Finding — first divergence on authored content (2026-11-18)

Probe run for the rive-leaf commission (L1 evidence, before any binding work).
Question: on a *real authored* file, is the 0/30 corpus verdict explained by the
missing timeline model (pointer/dt), or by something earlier?

Answer: **earlier.** The divergence is structural, reproducible at `t=0` with
**no inputs and no time**.

## Asset

`joystick_databound_keyframe_test.riv` — 708 bytes, one artboard `Main`
(500×500), VM + SM + keyframes. The commission's "minimal companion".

    oracle/dump <asset> 3 0.008335            # reference, rive-cpp recording renderer
    koruc run probe_joy.k                     # ours, kr/rive:opsdump ab=11 frame=0

## The streams

| | reference (`t=0`, and every frame) | ours (frame 0) |
|---|---|---|
| ops | save, transform(identity), save, transform(identity), **drawPath** ff282828, restore, save, transform(identity), **drawPath** ff747474, restore, restore | save, move(0,0), line(500,0), line(500,500), line(0,500), close, pushmat, **draw** ff282828, popmat — 9 ops |
| drawables | 2 | 1 |
| clip | 0 | 0 |

Ours is missing the second drawable (the 100×100 knob). First divergence is
therefore at traversal/paint, not at state or input.

(An earlier reading of this probe called the artboard-bounds path a clip op —
it is not: kinds 1/2/5 are move/line/close, and the correct-ab stream emits no
`clippush` at all. The digest in `authored_parity.py` gets this right; the
hand-read of the raw stream did not.)

## Prime suspect: one property fails to decode

`kr/rive:inspect` on the asset:

    obj[15] SolidColor parentId=13% ->24:Fill props=1     <-- no colour property
    obj[18] SolidColor parentId=14% ->25:Fill props=2  colorValue=0x00747474
    obj[20] SolidColor parentId=12% ->23:Fill props=2  colorValue=0xff282828

`obj[15]` is the fill of the knob shape (`Shape 13` → `Rectangle` 100×100 →
`Fill 24` → `SolidColor 15`). It carries only `Component.parentId`: the colour
property is absent from the decoded graph, while the two solid colours that *do*
draw decode normally at key 37. A shape whose fill has no paint appears to be
dropped rather than drawn with a default.

Not yet discriminated: paint-decode gap (this) vs traversal not reaching
`Shape 13`. Test that distinguishes them: `RIVE_FRAME=0` with a fixed
`dumpDrawOps` (it currently prints nothing for this asset — an instrument gap in
its own right), or count visited shapes in `transforms`.

## Instrument traps found (do not re-learn these)

1. **`ab` is an object index from `abnames`, not an ordinal.** A wrong `ab`
   does not error — it emits a plausible-looking 10-op degenerate skeleton
   (save/transform/clip/draw/restore with zero payloads). Two different assets
   produced *identical* streams this way. Any ops probe must print `abnames`
   first, or assert that the index names the intended artboard.
2. **`inventory_demo_test_v2.riv` cannot be dumped by rive-cpp's own tooling
   here**: `oracle/dump` asserts in `file_asset_importer.cpp:25`
   (`onFileAssetContents`, `!m_content`). The primary candidate is therefore not
   yet usable as a reference target until the dumper handles multiple file
   assets — the minimal companion is the correct first target.
3. `dumpDrawOps` emits nothing on this asset; `opsdump` is the working stream.

## Consequence for the plan

The 0/30 verdicts do not need the timeline model to explain them — a
static, zero-input ops comparison against authored files is a cheap and
legitimate L1 gate, and it is the one that should be built first. The fold
model (contract R3/R4) is not exercised, and therefore neither confirmed nor
contradicted, by this finding.

That gate is now `oracle/authored_parity.py`: it resolves the artboard by name
(never by ordinal), runs both streams, digests them, and names the first
divergent layer per file. `python3 oracle/authored_parity.py` for the demo set,
`--json` for machine use.
