import kr/rive
import std/io

kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/follow_path_shapes.riv")
| loaded r |> kr/rive:inspect(r) |> kr/rive:paths(r) |> kr/rive:transforms(r) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed: {{ e:s }}")
