# Koru-Rive eyeball audit — DeepSeek vision pass

You are auditing rendered output from a Koru-native Rive runtime against
browser-rendered references. Each image in `images/` is a side-by-side
composite: **left = reference (real Rive runtime in a browser), right =
ours (Koru renderer output)**. `gates.json` lists every gate with its
metric verdict and known caveats.

## Why this exists

Every gate carries a numeric verdict (PASS/LIMIT/NOTE) computed from ink
mass, bounding box, and pixel-diff thresholds. Those metrics are blind to
some visual differences — antialiasing quality, stroke joins, subtle
color shifts, misplaced small elements, texture scaling. Human-grade eyes
catch what the metrics miss. Your job is to find where the metrics lied.

## Task — per image, produce one verdict line

For EVERY `pair_*.png` in `images/` (38 total), look at both halves and
emit one JSONL line to `verdicts.jsonl`:

```json
{"gate":"cl2","verdict":"MATCH|MINOR|MISMATCH|UNREADABLE","diff_kind":"none|edge-aa|stroke|fill-color|transform|missing-elem|extra-elem|backdrop|text|scale|other","region":"where the difference is, e.g. top-left glyph edges","confidence":"high|med|low","note":"one sentence, what you actually see"}
```

Rules:

- **Do not rationalize.** A gate marked PASS can still be a visual
  MISMATCH — that is the entire point of this audit. Report what you see,
  not what the label claims.
- MINOR = differences a viewer would notice but that don't change the
  content's meaning (AA fringe, 1px offsets, slight color shift).
- MISMATCH = content visibly different (missing shapes, wrong colors,
  wrong layout, garbage regions).
- UNREADABLE = image broken/blank/corrupt on either side.
- `region` should name the location concretely — "bottom row, third cell"
  not "throughout".
- LIMIT/NOTE gates: audit them too — a LIMIT verdict may hide a real bug,
  or confirm the named caveat.

## Deliverable

`verdicts.jsonl` — exactly 38 lines, one per gate, valid JSON each.
This feeds a tightening pass: MISMATCH/MINOR verdicts become new gate
criteria or bug reports.

## Context

- Renderers under test: software scanline raster, Metal GPU raster —
  `kn_*` pairs are software, `knm_*` pairs are Metal, unprefixed pairs
  are the macOS canvas path.
- Backgrounds differ by fixture; dark/colored regions are intentional.
- Small text may legitimately differ if font rasterization differs —
  note it as `text` diff_kind rather than MISMATCH unless content differs.
- Pair images are composites — left half is always the reference.

Runbook for the harness: `RUNBOOK.md`.
Source repo: `/Users/larsde/src/koru-rive` — `oracle/gallery.py` generates
these pairs; `STATE.md` documents what each gate pins.
