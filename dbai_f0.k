import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/data_bind_artboard_input.riv")
| loaded r |> kr/rive:vm.bind(r, vm: 0, inst: 0) |> kr/rive:opsdump(r, ab: 7, frame: 0) |> kr/rive:opsdump(r, ab: 7, frame: 15) |> kr/rive:opsdump(r, ab: 7, frame: 29) |> kr/rive:free(r)
| failed e |> std/io:print.ln("failed {{ e:s }}")
