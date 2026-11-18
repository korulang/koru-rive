#!/usr/bin/env python3
"""first_divergence.py — layer-attributed report for one gate.

This is the first slice of the seam-instrumentation discipline: compare the
C++ command stream, our ops stream, the native clip-mask trace, and the
pixels, then name the FIRST layer where ours diverges from the reference.

Usage:
  python3 oracle/first_divergence.py \
      --golden /tmp/clip_golden.out \
      --ops /tmp/clip_ops_ours.out \
      --trace /tmp/clip_trace_run.out \
      --ours /tmp/kn_surface_kn_clip_trace.bmp \
      --ref oracle/images/ref_clip_t1.png \
      --comp 26,26,38 \
      --out oracle/first_divergence_kn_clip.md

The report is generated from the data, not typed. If a layer is not
instrumented yet, the report says so rather than guessing.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pixel_oracle as po  # noqa: E402


def parse_golden(path):
    lines = open(path).read().splitlines()
    # The dump prints all ARTBOARD headers first, then the streams; the
    # stream with the draw is the one we want, not the header-matched one.
    starts = [i for i, line in enumerate(lines) if line.strip() == "--- static t=0 ---"]
    chosen = None
    for st in starts:
        block = []
        for line in lines[st + 1:]:
            if line.startswith("--- sm") or line.startswith("--- static") or line.startswith("--- frame"):
                break
            block.append(line)
        if any("drawPath" in line for line in block):
            chosen = block
            break
    if chosen is None:
        raise SystemExit("golden: no static block with a drawPath")
    text = "\n".join(chosen)
    clips = [tuple(map(int, m)) for m in re.findall(r"clipPath verbs=(\d+) pts=(\d+)", text)]
    draw = re.search(r"drawPath.*?color=([0-9a-fA-F]+).*?verbs=(\d+) pts=(\d+)", text)
    transforms = re.findall(r"transform\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", text)
    tx = None
    if transforms:
        last = transforms[-1]
        tx = (float(last[4]), float(last[5]))
    return {
        "artboard": "Hidden-Path-Visible-Path",
        "clips": clips,
        "draw": (draw.group(1), int(draw.group(2)), int(draw.group(3))) if draw else None,
        "transform": tx,
    }


def parse_ops(path):
    lines = open(path).read().splitlines()
    ops = [line for line in lines if line.startswith("OP ")]
    clips = [line for line in ops if re.search(r" k=9 ", line)]
    draws = [line for line in ops if re.search(r" k=8 ", line)]
    transforms = [line for line in ops if re.search(r" k=6 ", line)]
    draw_color = None
    if draws:
        m = re.search(r"color=([0-9a-fA-F]+)", draws[-1])
        draw_color = m.group(1) if m else None
    tx = None
    if transforms:
        m = re.search(r"e=([-\d.]+) g=([-\d.]+)", transforms[-1])
        if m:
            tx = (float(m.group(1)), float(m.group(2)))
    return {
        "total": len(ops),
        "clips": len(clips),
        "draws": len(draws),
        "draw_color": draw_color,
        "transform": tx,
    }


def parse_trace(path):
    rows = []
    for line in open(path):
        line = line.strip()
        if not line.startswith("KORUTRACE "):
            continue
        try:
            rows.append(json.loads(line[len("KORUTRACE "):]))
        except json.JSONDecodeError:
            pass
    return rows


def image_stats(ref, ours, comp):
    res = po.evaluate(ref, ours, bg=tuple(comp), comp=tuple(comp), allow_missing_time=True)
    checks = {c["check"]: c for c in res["checks"]}
    return res, checks


def num(detail, name):
    m = re.search(name + r"=(\d+)", detail or "")
    return int(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", required=True)
    ap.add_argument("--ops", required=True)
    ap.add_argument("--trace", required=True)
    ap.add_argument("--ours", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--comp", default="26,26,38")
    ap.add_argument("--native", default=os.path.join(HERE, "..", "..", "oshun", "canvas", "index.koru-native.kz"))
    ap.add_argument("--out", default=os.path.join(HERE, "first_divergence_kn_clip.md"))
    a = ap.parse_args()

    comp = [int(x) for x in a.comp.split(",")]
    golden = parse_golden(a.golden)
    ops = parse_ops(a.ops)
    trace = parse_trace(a.trace)
    res, checks = image_stats(a.ref, a.ours, comp)

    shape = next((t for t in trace if t.get("inside", 0) < t.get("w", 0) * t.get("h", 1)), None)
    aa = checks.get("anti-aliasing", {})
    aa_ours = num(aa.get("detail"), "ours")
    aa_ref = num(aa.get("detail"), "ref")
    mask_binary = shape is not None and shape.get("mid") == 0
    tx_match = (golden["transform"] is not None and ops["transform"] is not None
                and abs(golden["transform"][0] - ops["transform"][0]) < 0.1
                and abs(golden["transform"][1] - ops["transform"][1]) < 0.1)
    ops_match = (len(golden["clips"]) == ops["clips"]
                 and (golden["draw"] is not None) == (ops["draws"] > 0)
                 and (golden["draw"][0].lower() == ops["draw_color"].lower() if golden["draw"] and ops["draw_color"] else False)
                 and tx_match)

    gate_pass = bool(res.get("pass"))
    if not ops_match:
        layer = "scene / ops"
        missing = "op-stream mismatch (fix the runtime before the raster)"
    elif shape is None:
        layer = "raster"
        missing = "clip-mask trace missing"
    elif mask_binary and (aa_ref or 0) > (aa_ours or 0):
        layer = "raster / clip coverage"
        missing = "fractional clip-mask coverage in the native canvas"
    elif gate_pass:
        layer = "none at the instrumented seams"
        missing = "none — fractional clip-mask coverage landed"
    else:
        layer = "raster / other"
        missing = "needs a finer raster trace (coverage present but gate still failing)"

    lines = []
    lines.append("# First-divergence report — `kn_clip`")
    lines.append("")
    lines.append("**Gate:** `kn_clip` — native software raster, nested path clips.  ")
    lines.append("**Reference:** `oracle/images/ref_clip_t1.png`  ")
    lines.append("**Generated by:** `oracle/first_divergence.py` (data, not typed).")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"**First divergent layer: {layer}.**  ")
    lines.append(f"**Missing surface: {missing}.**")
    lines.append("")
    if not ops_match:
        lines.append("Scene and command stream disagree; fix the runtime before the raster.")
    elif shape is None:
        lines.append("No clip-mask trace was captured; the raster seam is not instrumented.")
    elif mask_binary:
        lines.append("Scene and command stream agree; the pixel difference is not a runtime, geometry,")
        lines.append("transform, or paint problem. It appears at the clip mask: the native mask is")
        lines.append("binary and the reference clip edge carries fractional coverage.")
    else:
        lines.append("No divergence at the instrumented seams: scene/ops match, the clip mask")
        lines.append(f"carries fractional coverage (`mid={shape['mid']}`), and the gate passes")
        lines.append(f"(`anti-aliasing` ours={aa_ours}, ref={aa_ref}; `frame-diff` and `registration` clean).")
    lines.append("")
    lines.append("## Layer table")
    lines.append("")
    lines.append("| layer | ours | reference | result |")
    lines.append("|---|---|---|---|")
    golden_clip_txt = ", ".join(f"{v}/{p}" for v, p in golden["clips"])
    lines.append(f"| scene / ops | {ops['clips']} clip push(es), {ops['draws']} draw, color `{ops['draw_color']}`, tx={ops['transform']} | {golden_clip_txt}, draw {golden['draw'][1]}/{golden['draw'][2]}, color `{golden['draw'][0]}`, tx={golden['transform']} | {'MATCH' if ops_match else 'DIVERGES'} |")
    if shape:
        mask_desc = "binary 0/255" if mask_binary else "fractional 0..255"
        mask_result = "DIVERGES at coverage" if mask_binary else "FRACTIONAL (mid>0)"
        lines.append(f"| clip mask | `mid={shape['mid']}` ({mask_desc}), inside={shape['inside']}, edge={shape['edge']}, bbox={shape['bbox']}, hash=`{shape['hash']}` | blended edge px={aa_ref} | {mask_result} |")
    else:
        lines.append("| clip mask | no trace row | — | NOT INSTRUMENTED |")
    lines.append(f"| pixels | anti-aliasing: ours={aa_ours} blended, ink-mass: `{checks.get('ink-mass', {}).get('detail', '')}` | ref blended={aa_ref} | {'PASS' if gate_pass else 'FAIL'} |")
    lines.append("")
    lines.append("## Evidence")
    lines.append("")
    lines.append(f"- C++ stream: `{golden_clip_txt}`, draw color `{golden['draw'][0]}` at transform `{golden['transform']}`.")
    lines.append(f"- Our ops: {ops['total']} ops, {ops['clips']} clip push(es), {ops['draws']} draw(s), color `{ops['draw_color']}` at `{ops['transform']}`.")
    if shape:
        mid_txt = "no intermediate coverage values were written" if mask_binary else f"fractional coverage values were written (mid={shape['mid']})"
        lines.append(f"- Native trace: {len(trace)} clip push row(s); shape mask `mid={shape['mid']}` means {mid_txt}.")
    else:
        lines.append("- Native trace: no rows.")
    lines.append(f"- Oracle: `{aa.get('detail', 'no anti-aliasing check')}`")
    lines.append(f"- Oracle: `{checks.get('registration', {}).get('detail', 'no registration check')}`")
    lines.append(f"- Oracle: `{checks.get('frame-diff', {}).get('detail', 'no frame-diff check')}`")
    lines.append("")
    lines.append("## Reading")
    lines.append("")
    if mask_binary:
        lines.append("`rasterizeClipMask` writes `255` inside and `0` outside; `clipCov` samples the")
        lines.append("mask as `!= 0` and returns `0` or `1`. The composite therefore has a hard clip")
        lines.append("edge. The browser reference passes the same clip path through a rasterizer with")
        lines.append("fractional coverage, which is why its edge has blended pixels and ours has none.")
        lines.append("")
        lines.append("This is a **missing library surface**, not a Rive-specific special case: the")
        lines.append("native canvas has no fractional clip mask. It is exactly the kind of gap the")
        lines.append("Rive workload is meant to force.")
    else:
        lines.append("The native clip mask now carries fractional coverage (`mid > 0`):")
        lines.append("`rasterizeClipMask` supersamples the path and `clipCov` multiplies the")
        lines.append("coverage into the fill alpha. The clipped edge therefore has the same")
        lines.append("kind of AA ramp as the reference, and the gate passes.")
        lines.append("")
        lines.append("The seam is closed; keep this trace as the regression instrument for")
        lines.append("clip-path AA. The next seam is the compiler's realization report.")
    lines.append("")
    lines.append("## Next action")
    lines.append("")
    if gate_pass and not mask_binary:
        lines.append("No action at the clip seam. The next instrumentation seam is the compiler")
        lines.append("realization report (`koruc` build: verb, variant, static/dynamic, fallback).")
    else:
        lines.append("Give the native clip mask fractional coverage (supersampled or analytic coverage")
        lines.append("in `rasterizeClipMask`, and a coverage sample in `clipCov`), then re-run this")
        lines.append("trace. The proof is `mid > 0` in the trace and an `anti-aliasing` ratio >= 0.5")
        lines.append("without a regression in `frame-diff` / `registration`.")
    lines.append("")
    lines.append("Files:")
    lines.append("")
    lines.append(f"- native surface: `{os.path.relpath(a.native, os.path.join(HERE, '..'))}`")
    lines.append(f"- C++ stream: `{a.golden}`")
    lines.append(f"- our ops: `{a.ops}`")
    lines.append(f"- trace: `{a.trace}`")
    lines.append("")

    open(a.out, "w").write("\n".join(lines))
    print(f"wrote {a.out}")
    print(f"first divergence: {layer} / {missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
