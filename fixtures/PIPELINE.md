# Fixture pipeline: RML → CLI → .riv → decode → oracle

Hand-authored fixtures for coverage classes the rive-cpp corpus lacks.
Author in Rive Markup Language (text, diffable), compile with the official
Rive CLI, gate through the existing decoder + two-renderer oracle.

## Toolchain

- Rive CLI 1.9.2 at `~/.rive/bin/rive` (Homebrew: `brew install --cask rive-app/rive-cli`).
  Logged in as cocporn — `--publish` writes `build/<name>.riv`.
  No scripts in a project → **unsigned** .riv (the pure dialect test).
- Project shape: `rive.yaml` (`name`, `version: "1"`) + `scene.rml`
  (`<Rive version="1" kind="fragment">` … `</Rive>`).
- Useful commands: `rive . --verify` (compile check), `rive inspect . --json`
  (resolved scene — oracle artifact), `rive . --screenshot=x.png --advance=1`
  (official render), `rive . --publish` (.riv to `build/`).
- RML reference: `rive docs <topic>`, `rive schema <Type>`,
  `~/.rive/versions/1.9.2/docs/*.md` (format/state-machines/data/easing).

## Loop

```bash
cd fixtures/<name>
rive . --verify && rive . --publish          # → build/<name>.riv
cp build/<name>.riv ./<name>.riv             # commit the .riv too
cd ../..
./a.out fixtures/<name>/<name>.riv           # decode dump (inspect_arg.k)
./a.out fixtures/<name>/<name>.riv /tmp/x.bmp # render ops (render_arg.k)
RIVE_FIXTURE=fixtures/<name>/<name>.riv \
  node oracle/render_browser.mjs rive_canvas 1 /tmp/ref.png 500 "<Artboard>" ""
```

`inspect_arg.k` / `render_arg.k` are argv probes — compile once via
`koruc run <probe>.k`, then `./a.out <args>` (avoids `koruc run`'s
StderrStreamTooLong on verbose decoder output).

## What each fixture targets (recon 2026-11-18)

Corpus sweep: 433 assets + vmlist → 274 distinct types, 201,898 instances.
Decoder knows ~359 type names; **89 never appear in the corpus**.

| fixture | never/under-covered types | notes |
|---|---|---|
| `vmlist` | ViewModel list binding path (`ArtboardComponentList`, `ViewModelInstanceList*`) | corpus has VM objects but our ops path doesn't bind/layout — decode PASS, render FAIL(expected) |
| `gradients` | `AngularGradient` (never), Linear/Radial gradient *draw* (objects decode, ops ignores) | 4 gradient fills/strokes; ops path has no gradient kind |
| `sm_conditions` | `TransitionBoolCondition`, `TransitionNumberCondition`, `TransitionTriggerCondition` — zero condition types in corpus | input-driven SM (`StateMachineBool/Number/Trigger`) |
| `scroll_view` | `ScrollConstraint`, `ClampedScrollPhysics`, `ScrollPhysics` | viewport + 1200px content column |

Other never-seen, authoring-easy candidates for later fixtures:
`NestedStateMachine`/`NestedSimpleAnimation`, `IKConstraint`,
`DistanceConstraint`, `TransformConstraint`, `ElasticScrollPhysics`,
`TextInput*` (drawable/cursor/selection), `DataConverterRangeMapper`
(bind converters — corpus binds have none), `KeyFrameInt`,
`SelectionStyle`, `StringTemplateArgument`, `ScrollPhysics` variants,
`ScriptedTransitionCondition`, `TransitionViewModelCondition` family.

## Verified so far

- vmlist: decode 997 objs / 0 fails; oracle lit-px 107,200 both backends;
  ours 0 content px (layout+VM gaps) — commit `58470bd`.
- gradients/sm_conditions/scroll_view: decode ~980 objs / 0 fails each;
  oracle renders non-empty (see git log for pixel census).
- Corpus type histogram method: `./a.out <riv>` per asset → `obj[N] Type`
  lines → awk histogram (`/tmp/typepairs.tsv` regenerable).

## Known limits

- `band.py` is square-only (size→WxH equal); non-square artboards need
  the pixel census or a harness tweak.
- `rive login` required for `--publish`; watch/screenshot stay in-memory.
- `.rev` export needs the desktop editor (installed: Rive.app 0.9.642);
  `rive create --from-rev` converts editor files back to RML projects.
- RML is `version="1"`, CLI is technical preview — pin CLI version.
- scroll_view content column is authored but rows are not instanced yet
  (NestedArtboard placement is the next iteration).
