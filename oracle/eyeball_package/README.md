# Koru-Rive eyeball audit — DeepSeek vision pass

## What this project is (context that matters for your verdicts)

This is a **Koru-native Rive runtime** — a from-scratch renderer for
`.riv` animation files, built as a forcing function for the Koru
language's GPU pipeline. Rive files decode into object graphs, evaluate
animations/state-machines/view-models, and emit renderer-neutral draw
ops that replay through Koru's own Metal GPU backend (plus a software
scanline arm for verification). The `kn_*` pairs are the software arm,
`knm_*` are Metal, unprefixed pairs are the macOS canvas path.

The stakes: these renders exercise Koru's realization and variant
systems — every visual defect you find is either a renderer bug or a
missing realization surface. "Close enough" is not the bar; the project
ships on pixel-honest gates. Your verdicts feed a tightening pass where
MINOR/MISMATCH findings become new gate criteria or bug reports. Full
charter: `SCENE.md` in the repo root.

**Sequencing:** this audit runs AFTER the fidelity-tier oracle lands (`../FIDELITY_BRIEF.md`) — verdicts triage against hardened gates, and every confirmed visual mismatch the metrics still miss becomes a candidate new oracle check. The oracle grows by audit.

## The audit task

You are auditing rendered output from a Koru-native Rive runtime against
browser-rendered references. Each image in `images/` is a side-by-side
composite: **left = ours (Koru renderer output), right = reference (real
Rive runtime in a browser)** — each half is labelled in the image itself. `gates.json` lists every gate with its
metric verdict and known caveats.

## Why this exists

Every gate carries an oracle verdict (PASS/FAIL, with the failed checks
named) computed by `../run_gates.py`. Those metrics are blind to
some visual differences — antialiasing quality, stroke joins, subtle
color shifts, misplaced small elements, texture scaling. Human-grade eyes
catch what the metrics miss. Your job is to find where the metrics lied.

## Task — per image, produce one verdict line

For EVERY `pair_*.png` in `images/` (33 total), look at both halves and
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
- FAIL gates: audit them too — an oracle FAIL may hide a second bug,
  or confirm the named caveat.

## Resolved edge cases (2026-11-17)

These were under-specified in the first version of this contract and are
fixed here so a cold run does not have to guess. `AUDIT_NOTES.md` records
the reasoning and the first vision pass.

- **`vacuous: true` gates.** `gates.json` marks gates where both sides
  are blank by design (oracle-limitation fixtures). Judge what is
  visible, not the missing content. Same frame colour on both sides →
  `MATCH`, `diff_kind: none`, note "vacuous". Different frame colour →
  `MISMATCH`, `diff_kind: backdrop`, note "vacuous" — a white-vs-dark
  frame is a visible whole-frame difference even with no ink. Do not use
  `UNREADABLE` for a deliberately empty fixture.
- **Text.** Rasterization-only differences (AA, hinting, stroke weight,
  sub-pixel phase) are `MINOR`, `diff_kind: text` or `edge-aa`. Text
  **placement**, **scale**, or **content** differences are `MISMATCH`,
  `diff_kind: text` or `transform`. This resolves the earlier conflict:
  `cl2`'s digit is the same glyph in the wrong place, so it is a
  MISMATCH, not a font difference.
- **Duplicate composites.** 33 gates use 26 unique images — some gates
  share a byte-identical pair (e.g. `clv`/`kn_clv`/`knm_clv`,
  `iba`/`hff`, `kn_clip`/`knm_clip`). Emit one line per gate as required,
  but name the shared composite in `note`; the tightening pass must not
  count duplicates as independent confirmations.
- **Too small to judge.** `dcpo` is 64×64 per side and both sides are
  uniform. Judge it vacuously (`MATCH`, low confidence) rather than
  `UNREADABLE`; flag the resolution in `note`.

## Deliverable

`verdicts.jsonl` — exactly 33 lines, one per gate, valid JSON each.
This feeds a tightening pass: MISMATCH/MINOR verdicts become new gate
criteria or bug reports. A validated first vision pass is already in
this directory; run `python3 validate_verdicts.py` to check the schema,
completeness, and the duplicate-composite map.

## Context

- Renderers under test: software scanline raster, Metal GPU raster —
  `kn_*` pairs are software, `knm_*` pairs are Metal, unprefixed pairs
  are the macOS canvas path.
- Backgrounds differ by fixture; dark/colored regions are intentional.
- Small text rasterization may legitimately differ — use the resolved
  text rule above: rasterization-only is MINOR, but placement/scale/
  content differences are MISMATCH.
- Pair images are composites — left half is always ours, right half the reference.

Runbook for the harness: `RUNBOOK.md`.
Source repo: `/Users/larsde/src/koru-rive` — `oracle/gallery.py` generates
these pairs; `STATE.md` documents what each gate pins.
