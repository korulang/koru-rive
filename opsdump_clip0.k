// First-divergence slice: clip_tests op stream at frame 0 (the pose the
// browser reference captures). Paired with oracle/trace_kn_clip.sh and
// oracle/first_divergence.py — this is the command-plane half of the trace.
import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/clip_tests.riv")
| loaded r |> kr/rive:opsdump(r, ab: 42, frame: 0) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
