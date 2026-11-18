import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/hunter_x_demo.riv")
| loaded r |> kr/rive:opsdump(r, ab: 0, frame: 8) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
