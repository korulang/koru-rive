import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/joystick_databound_keyframe_test.riv")
| loaded r |> kr/rive:vm.bind(r, vm: 0, inst: 0) |> kr/rive:opsdump(r, ab: 11, frame: 30) |> kr/rive:free(r)
| failed e |> std/io:print.ln("failed {{ e:s }}")
