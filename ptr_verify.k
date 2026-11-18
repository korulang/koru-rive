import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/joystick_databound_keyframe_test.riv")
| loaded r |> kr/rive:vm.bind(r, vm: 0, inst: 0) |> kr/rive:pointer.move(r, ab: 11, x: 0.0, y: 250.0, frame: 6, id: 0) |> kr/rive:pointer.move(r, ab: 11, x: 100.0, y: 250.0, frame: 12, id: 0) |> kr/rive:pointer.move(r, ab: 11, x: 200.0, y: 250.0, frame: 18, id: 0) |> kr/rive:pointer.move(r, ab: 11, x: 300.0, y: 250.0, frame: 24, id: 0) |> kr/rive:pointer.move(r, ab: 11, x: 400.0, y: 250.0, frame: 30, id: 0) |> kr/rive:opsdump(r, ab: 11, frame: -1) |> kr/rive:free(r)
| failed e |> std/io:print.ln("failed {{ e:s }}")
