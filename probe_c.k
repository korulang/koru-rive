import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/car_widgets_v01.riv")
| loaded r |> kr/rive:opsdump(r, ab: 90, frame: 0) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed")
