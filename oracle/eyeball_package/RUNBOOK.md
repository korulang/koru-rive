# RUNBOOK — feeding this package to DeepSeek

## Package layout

```
eyeball_package/
  README.md        — audit protocol + verdict contract (give this to the model)
  RUNBOOK.md       — this file
  gates.json       — 38 gates: name, metric verdict, known caveat, pair path
  images/          — pair_<gate>.png composites (ref | ours), self-contained
```

## How to run

1. Give the model `README.md` as the system/task prompt.
2. Feed each `images/pair_*.png` one at a time (or in batches if the
   harness supports multi-image turns) alongside `gates.json` for the
   metric verdicts.
3. Collect `verdicts.jsonl` — one JSON object per gate, schema in README.

## After the run

`verdicts.jsonl` is the tightening-pass input: every MINOR/MISMATCH line
names a gate + diff_kind + region. Triage order: MISMATCH first, then
MINOR clustered by diff_kind (a systematic `edge-aa` across gates = one
rasterizer fix; scattered = per-fixture bugs).

## Regenerating

Pairs regenerate from `../gallery.py` (`uv run --with pillow --with numpy
python gallery.py`) — re-copy `images/pair_*.png` here after any gate
update, and refresh `gates.json` verdicts from the GATES table.

## What this is NOT

Not a reproduction task (unlike `6digit-vision/deepseek_package`) — no
HTML to write, no iteration loop. Pure perception audit: look, classify,
report. The measured facts live in `gates.json`; the eyes supply the
judgment the metrics can't.
