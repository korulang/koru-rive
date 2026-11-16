import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/custom_property_trigger.riv")
| loaded r |> kr/rive:tessdump(r, ab: 8, frame: 0) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
