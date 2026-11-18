# RUNBOOK — feeding this package to DeepSeek

## Package layout

```
eyeball_package/
  README.md        — audit protocol + verdict contract (give this to the model)
  RUNBOOK.md       — this file
  gates.json       — 33 gates: name, oracle verdict, failed checks, pair path
  images/          — pair_<gate>.png composites (ours | ref), self-contained
  extras/          — 5 superseded intermediate tick pairs, NOT part of the audit
  verdicts.jsonl   — validated first vision pass (33 lines, README schema)
  validate_verdicts.py — contract check + duplicate-composite report
  AUDIT_NOTES.md   — readiness assessment, resolved edge cases, first-pass triage
  ../verdicts_swe2_ascii.jsonl — baseline verdicts from an ASCII-grid pass
                     (SWE-2, no image input); diff your verdicts against it
```

## How to run

1. Give the model `README.md` as the system/task prompt.
2. Feed each `images/pair_*.png` one at a time (or in batches if the
   harness supports multi-image turns) alongside `gates.json` for the
   metric verdicts.
3. Collect `verdicts.jsonl` — one JSON object per gate, schema in README.
4. Validate: `python3 validate_verdicts.py`. It checks 33 lines, enums,
   one line per gate, and reports the exact-duplicate pair composites
   (26 unique of 33) so the triage does not double-count them.

## After the run

`verdicts.jsonl` is the tightening-pass input: every MINOR/MISMATCH line
names a gate + diff_kind + region. Triage order: MISMATCH first, then
MINOR clustered by diff_kind (a systematic `edge-aa` across gates = one
rasterizer fix; scattered = per-fixture bugs). Diff against
`verdicts_swe2_ascii.jsonl` (same schema, ASCII-instrumented baseline):
agreement = high confidence; disagreement = look again carefully.

## Regenerating

Pairs regenerate from `../gallery.py` (`uv run --with pillow --with numpy
python gallery.py`) — re-copy `images/pair_*.png` here after any gate
update, and regenerate `gates.json` from `../gate_verdicts.json` +
`../gates.json` (verdicts are computed by `../run_gates.py`, never typed).

## What this is NOT

Not a reproduction task (unlike `6digit-vision/deepseek_package`) — no
HTML to write, no iteration loop. Pure perception audit: look, classify,
report. The measured facts live in `gates.json`; the eyes supply the
judgment the metrics can't.
