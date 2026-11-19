// riv2k probe: canonical graph serialization of a decoded .riv.
// Usage: graphdump_probe.k <path-override via RIVE_PROBE env?> — path is
// fixed per file; copy/edit for other fixtures.
import kr/rive
import std/io

kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/component_stateful_vm_instance_2.riv")
| loaded r |> kr/rive:graphdump(r) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed: {{ e:s }}")
