// First-divergence probe: the minimal authored companion
// (joystick_databound_keyframe_test.riv — VM + SM + keyframes).
// Reference side: oracle/dump on the same asset. Ours: opsdump per frame.
import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/joystick_databound_keyframe_test.riv")
| loaded r
    |> kr/rive:abnames(r)
    |> kr/rive:smdump(r)
    |> kr/rive:vmdump(r)
    |> kr/rive:opsdump(r, ab: 11, frame: 0)
    |> kr/rive:opsdump(r, ab: 11, frame: 1)
    |> kr/rive:opsdump(r, ab: 11, frame: 2)
    |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
