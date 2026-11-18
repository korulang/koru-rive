import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/joystick_databound_keyframe_test.riv")
| loaded r
    |> kr/rive:inspect(r)
    |> kr/rive:bindump(r)
    |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
