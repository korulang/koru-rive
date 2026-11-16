// Dump Main ops across a frame range in one binary, so pose can be matched
// against the golden's per-frame control points analytically.
import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/component_list_follow_path.riv")
| loaded r
    |> kr/rive:opsdump(r, ab: 18, frame: -1)
    |> kr/rive:opsdump(r, ab: 18, frame: 0)
    |> kr/rive:opsdump(r, ab: 18, frame: 2)
    |> kr/rive:opsdump(r, ab: 18, frame: 4)
    |> kr/rive:opsdump(r, ab: 18, frame: 6)
    |> kr/rive:opsdump(r, ab: 18, frame: 8)
    |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed")
