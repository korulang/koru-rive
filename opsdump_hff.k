import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/hosted_font_file.riv")
| loaded r |> kr/rive:opsdump(r, ab: 2, frame: -1) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
