import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/component_list_1.riv")
| loaded r |> kr/rive:opsdump(r, ab: 24, frame: 0) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
