#!/usr/bin/env python3
"""riv2k — build-time .riv -> Koru module emitter (static leaf realization).

Pipeline: graphdump probe -> canonical spec -> rivgen_<name>.kz carrying
the decoded graph as an embedded string literal; the module's open{}
delegates to kr/rive:fromgraph. Ops-parity vs the dynamic path is the gate
(oracle/parity*.k probes).

Usage: tools/riv2k.py <file.riv> [out.kz]
"""
import re, subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RIVE = "rive-cpp/tests/unit_tests/assets"
KORU_BACKEND = pathlib.Path.home() / "src/oshun/canvas/koruos-darwin"

def spec_for(riv_path: str) -> str:
    probe = ROOT / "graphdump_tmp.k"
    probe.write_text(
        'import kr/rive\nimport std/io\n'
        f'kr/rive:open(path: "{riv_path}")\n'
        '| loaded r |> kr/rive:graphdump(r) |> kr/rive:free(r)\n'
        '| failed e |> std/io:print.ln("open failed {{ e:s }}")\n')
    env = dict(__import__("os").environ, KORU_BACKEND_LIBPATH=str(KORU_BACKEND))
    out = subprocess.run(["koruc", "run", str(probe)], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout
    probe.unlink()
    m = re.search(r"^G ", out, re.M)
    if not m:
        sys.exit("graphdump produced no spec — tail of koruc output:\n" + "\n".join(out.splitlines()[-15:]))
    # spec is whitespace-tokenized; collapse to one line for embedding
    return " ".join(out[m.start():].split())

def emit(spec: str, out_path: pathlib.Path):
    # spec-vending module: the decoded graph as data; consumers materialize
    # via kr/rive:fromgraph and drive the shared leaf verbs. Typed-schema
    # params (VM binding surface) land with L2 proper.
    out_path.write_text(
        "// riv2k generated — static realization of LEAF_CONTRACT.\n"
        "// Decode happened at build time; spec is the decoded object graph.\n"
        "~import kr/rive\n\n"
        "~pub tor spec {} -> string\n"
        "~proc spec|zig {\n"
        "    return \"" + spec + "\";\n"
        "}\n")

if __name__ == "__main__":
    riv = sys.argv[1]
    if not pathlib.Path(riv).is_absolute():
        riv = str(ROOT / RIVE / riv)
    name = pathlib.Path(riv).stem
    out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "tools/out" / f"rivgen_{name}.kz"
    out.parent.mkdir(parents=True, exist_ok=True)
    emit(spec_for(riv), out)
    print(f"emitted {out} ({out.stat().st_size} bytes)")
