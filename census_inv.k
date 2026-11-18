import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/inventory_demo_test_v2.riv")
| loaded r |> kr/rive:abnames(r) |> kr/rive:smdump(r) |> kr/rive:vmdump(r) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
