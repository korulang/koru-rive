import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/data_bind_artboard_input.riv")
| loaded r |> kr/rive:tessdump(r, ab: 7, frame: 0) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
