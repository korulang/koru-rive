import kr/rive
import std/io
kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/trim_path_linear.riv")
| loaded r |> kr/rive:graphdump(r) |> kr/rive:free(r)
| failed e |> std/io:print.ln("open failed {{ e:s }}")
