import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/custom_image_name.riv")
| loaded r |> kr/rive:opsdump(r, ab: 3, frame: -1) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
