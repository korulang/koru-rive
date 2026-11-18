import kr/rive
import std/io
kr/rive:fromfile(path: "/tmp/hw.spec")
| loaded r |> kr/rive:opsdump(r, ab: 3, frame: -1) |> kr/rive:free(r)
| failed e |> std/io:print.ln("fromfile failed {{ e:s }}")
