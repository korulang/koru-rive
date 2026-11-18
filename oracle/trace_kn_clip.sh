#!/bin/sh
# trace_kn_clip.sh — run the first seam-instrumentation slice for kn_clip.
#
# Captures four layers for the same fixture:
#   1. C++ command stream (oracle/dump, linked against rive-cpp)
#   2. our op stream (kr/rive:opsdump, ab=42)
#   3. native clip-mask trace (KORU_TRACE_CLIP, software surface)
#   4. pixels (native surface + browser reference)
# then writes oracle/first_divergence_kn_clip.md.
#
# Requires: koruc, the oshun native canvas, oracle/dump, numpy+pillow.
set -eu

cd "$(dirname "$0")/.."

KORUC=${KORUC:-/Users/larsde/src/koru/zig-out/bin/koruc}
LIB=${KORU_BACKEND_LIBPATH:-/Users/larsde/src/oshun/canvas/koruos-darwin}
if [ -n "${PYTHON:-}" ]; then
  PY_CMD="$PYTHON"
elif command -v uv >/dev/null 2>&1; then
  PY_CMD="uv run --with numpy --with pillow python"
else
  PY_CMD=python3
fi

export ZIG_GLOBAL_CACHE_DIR="$PWD/.zig-global"
export KORU_BACKEND_LIBPATH="$LIB"

echo "[1/4] C++ command stream"
./oracle/dump rive-cpp/tests/unit_tests/assets/clip_tests.riv 1 > /tmp/clip_golden.out

echo "[2/4] our op stream"
"$KORUC" run opsdump_clip0.k > /tmp/clip_ops_ours.out 2>&1

echo "[3/4] native clip-mask trace"
"$KORUC" build render_kn_clip.k --build=koru-native -o /tmp/render_kn_clip_trace > /tmp/build_kn_clip_trace.log
KORU_TRACE_CLIP=1 KN_TAG=kn_clip_trace /tmp/render_kn_clip_trace > /tmp/clip_trace_run.out 2>&1
cp /tmp/kn_surface_kn_clip_trace.bmp /tmp/kn_clip_trace.bmp

echo "[4/4] first-divergence report"
$PY_CMD oracle/first_divergence.py \
  --golden /tmp/clip_golden.out \
  --ops /tmp/clip_ops_ours.out \
  --trace /tmp/clip_trace_run.out \
  --ours oracle/images/kn_clip.bmp \
  --ref oracle/images/ref_clip_t1.png \
  --comp 26,26,38 \
  --out oracle/first_divergence_kn_clip.md

echo "done: oracle/first_divergence_kn_clip.md"
