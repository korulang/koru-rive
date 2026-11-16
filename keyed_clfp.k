import kr/rive
import std/io
import std/args

std/args:all(): _av
|> kr/rive:open(path: "/Users/larsde/src/koru-rive/rive-cpp/tests/unit_tests/assets/component_list_follow_path.riv")
| loaded r
    |> kr/rive:keyed(r)
    |> kr/rive:free(r)
| failed e
    |> std/io:print.ln("open failed")
