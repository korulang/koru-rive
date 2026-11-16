import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/early_exit_reversal_blend.riv")
| loaded r |> kr/rive:abnames(r) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
