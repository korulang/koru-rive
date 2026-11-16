import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/clipping_and_draw_order.riv")
| loaded r |> kr/rive:abnames(r) |> kr/rive:free(r)
| failed _ |> std/io:print.ln("open failed")
